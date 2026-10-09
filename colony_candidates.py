"""Full-resolution, reviewable spot candidates inside DMEF wells.

These are optical contrast candidates, not confirmed bacterial colonies. A
supervised colony model needs independently annotated colony locations.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageCms, ImageOps
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
FIELDS = ["image_id", "well_id", "sample_id", "dilution", "candidate_id", "x_px", "y_px", "region", "area_px",
          "type", "contrast_0_255", "local_rgb_r", "local_rgb_g", "local_rgb_b"]


def read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        icc = source.info.get("icc_profile")
        image = ImageOps.exif_transpose(source)
        if icc:
            image = ImageCms.profileToProfile(
                image, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                ImageCms.createProfile("sRGB"), outputMode="RGB")
        return np.array(image.convert("RGB"))


def detect_wells_full_resolution(rgb: np.ndarray) -> list[dict]:
    """Fit the four colored interiors without resizing any image pixels."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    binary = cv2.inRange(hsv, np.array([12, 60, 130]), np.array([48, 255, 255]))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = rgb.shape[:2]
    wells = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not .002 * height * width < area < .09 * height * width or len(contour) < 5:
            continue
        perimeter = cv2.arcLength(contour, True)
        (cx, cy), (major, minor), angle = cv2.fitEllipse(contour)
        if perimeter == 0 or 4 * np.pi * area / perimeter**2 < .7:
            continue
        if min(major, minor) / max(major, minor) < .72:
            continue
        wells.append(dict(cx=float(cx), cy=float(cy), rx=float(major / 2),
                          ry=float(minor / 2), angle=float(angle)))
    wells.sort(key=lambda r: r["cy"])
    if len(wells) == 4:
        wells = sorted(wells[:2], key=lambda r: r["cx"]) + sorted(wells[2:], key=lambda r: r["cx"])
    return wells


def interior_mask(shape: tuple[int, int], roi: dict, inset: float = .12) -> np.ndarray:
    y, x = np.ogrid[:shape[0], :shape[1]]
    angle = np.deg2rad(roi["angle"])
    dx, dy = x - roi["cx"], y - roi["cy"]
    u = dx * np.cos(angle) + dy * np.sin(angle)
    v = -dx * np.sin(angle) + dy * np.cos(angle)
    return (u / roi["rx"]) ** 2 + (v / roi["ry"]) ** 2 <= (1 - inset) ** 2


def measure_well_rgb(rgb: np.ndarray, roi: dict, inset: float) -> dict:
    """Measure stored 0–255 RGB pixels in the same inner ellipse."""
    x0 = max(0, int(roi["cx"] - roi["rx"] - 2))
    y0 = max(0, int(roi["cy"] - roi["ry"] - 2))
    x1 = min(rgb.shape[1], int(roi["cx"] + roi["rx"] + 3))
    y1 = min(rgb.shape[0], int(roi["cy"] + roi["ry"] + 3))
    crop = rgb[y0:y1, x0:x1]
    mask = interior_mask(crop.shape[:2], {**roi, "cx": roi["cx"] - x0,
                                               "cy": roi["cy"] - y0}, inset)
    pixels = crop[mask]
    if not len(pixels):
        raise ValueError("Empty well interior for RGB measurement")
    median = np.median(pixels, axis=0)
    iqr = np.percentile(pixels, 75, axis=0) - np.percentile(pixels, 25, axis=0)
    return {**{f"{channel}_median_0_255": round(float(median[i]), 2)
               for i, channel in enumerate("RGB")},
            **{f"{channel}_iqr_0_255": round(float(iqr[i]), 2)
               for i, channel in enumerate("RGB")},
            "rgb_pixel_count": int(len(pixels))}


def save_rgb_scale(path: Path, measurements: dict, title: str) -> None:
    """Save an explicitly bounded RGB channel chart for one well."""
    values = [measurements[f"{channel}_median_0_255"] for channel in "RGB"]
    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(["Red", "Green", "Blue"], values,
                  color=["#D64A4A", "#47A967", "#4B79CD"])
    ax.set_ylim(0, 255)
    ax.set_yticks([0, 50, 100, 150, 200, 255])
    ax.set_ylabel("Stored RGB value (0–255)")
    ax.set_title(title)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, min(value + 4, 251),
                f"{value:.1f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def find_candidates(rgb: np.ndarray, roi: dict, sigma: float = 10,
                    threshold: float = 4.5, inset: float = .12,
                    min_area: int = 4, max_area: int = 350) -> tuple[list[dict], np.ndarray]:
    """Find compact bright/dark departures from a smooth local background.

    Threshold is estimated independently inside each well. No image is resized.
    This is a transparent unsupervised detector, not a fitted biological model.
    """
    if not 0 <= inset < .5 or sigma <= 0 or threshold <= 0 or min_area < 1 or max_area < min_area:
        raise ValueError("Invalid candidate detector settings")
    height, width = rgb.shape[:2]
    pad = int(4 * sigma + 6)
    x0 = max(0, int(roi["cx"] - roi["rx"] - pad))
    y0 = max(0, int(roi["cy"] - roi["ry"] - pad))
    x1 = min(width, int(roi["cx"] + roi["rx"] + pad + 1))
    y1 = min(height, int(roi["cy"] + roi["ry"] + pad + 1))
    crop = rgb[y0:y1, x0:x1]
    local_roi = {**roi, "cx": roi["cx"] - x0, "cy": roi["cy"] - y0}
    inside = interior_mask(crop.shape[:2], local_roi, inset)
    if not inside.any():
        raise ValueError("Empty well interior")
    # Stored sRGB values are image intensities, not calibrated fluorescence.
    intensity = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY).astype(np.float32)
    background = cv2.GaussianBlur(intensity, (0, 0), sigmaX=sigma)
    residual = intensity - background
    center = np.median(residual[inside])
    noise = 1.4826 * np.median(np.abs(residual[inside] - center))
    noise = max(float(noise), 1.0)
    valid = inside & (crop.max(axis=2) < 250)
    candidates = []
    for sign, kind in ((1, "bright"), (-1, "dark")):
        binary = ((sign * (residual - center) > threshold * noise) & valid).astype(np.uint8)
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
        for index in range(1, count):
            area = int(stats[index, cv2.CC_STAT_AREA])
            if not min_area <= area <= max_area:
                continue
            pixels = labels == index
            mean_rgb = crop[pixels].mean(axis=0)
            candidates.append(dict(x_px=round(float(centroids[index, 0] + x0), 1),
                                   y_px=round(float(centroids[index, 1] + y0), 1),
                                   area_px=area, type=kind,
                                   contrast_0_255=round(float(np.mean(sign * (residual[pixels] - center))), 2),
                                   local_rgb_r=round(float(mean_rgb[0]), 2),
                                   local_rgb_g=round(float(mean_rgb[1]), 2),
                                   local_rgb_b=round(float(mean_rgb[2]), 2)))
    candidates.sort(key=lambda item: (item["y_px"], item["x_px"], item["type"]))
    return candidates, inside


def find_dark_patches(rgb: np.ndarray, roi: dict, inset: float = .12,
                      threshold: float = 1.5) -> list[tuple[dict, np.ndarray]]:
    """Flag broad dark regions using contrast at a second, larger scale.

    Returns descriptors and original-pixel outlines. Broad shadows, staining,
    and lighting gradients can produce these, so they require manual review.
    """
    if not 0 <= inset < .5 or threshold <= 0:
        raise ValueError("Invalid dark patch settings")
    height, width = rgb.shape[:2]
    radius = min(roi["rx"], roi["ry"])
    small_sigma = max(4.0, .03 * radius)
    large_sigma = max(20.0, .23 * radius)
    pad = int(3 * large_sigma + 6)
    x0 = max(0, int(roi["cx"] - roi["rx"] - pad))
    y0 = max(0, int(roi["cy"] - roi["ry"] - pad))
    x1 = min(width, int(roi["cx"] + roi["rx"] + pad + 1))
    y1 = min(height, int(roi["cy"] + roi["ry"] + pad + 1))
    crop = rgb[y0:y1, x0:x1]
    local_roi = {**roi, "cx": roi["cx"] - x0, "cy": roi["cy"] - y0}
    inside = interior_mask(crop.shape[:2], local_roi, inset)
    intensity = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY).astype(np.float32)
    dark_contrast = (cv2.GaussianBlur(intensity, (0, 0), large_sigma)
                     - cv2.GaussianBlur(intensity, (0, 0), small_sigma))
    values = dark_contrast[inside]
    center = float(np.median(values))
    noise = max(float(1.4826 * np.median(np.abs(values - center))), 1.0)
    binary = ((dark_contrast > center + threshold * noise) & inside
              & (crop.max(axis=2) < 250)).astype(np.uint8)
    size = max(5, int(.025 * radius) | 1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((size, size), np.uint8))
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
    patches = []
    min_area = max(100, int(.001 * inside.sum()))
    max_area = int(.15 * inside.sum())
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        if not min_area <= area <= max_area:
            continue
        pixels = labels == index
        mean_rgb = crop[pixels].mean(axis=0)
        contours, _ = cv2.findContours(pixels.astype(np.uint8), cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        outline = max(contours, key=cv2.contourArea).copy()
        outline[:, 0, 0] += x0
        outline[:, 0, 1] += y0
        descriptor = dict(x_px=round(float(centroids[index, 0] + x0), 1),
                          y_px=round(float(centroids[index, 1] + y0), 1),
                          area_px=area, type="dark_patch",
                          contrast_0_255=round(float(np.mean(dark_contrast[pixels] - center)), 2),
                          local_rgb_r=round(float(mean_rgb[0]), 2),
                          local_rgb_g=round(float(mean_rgb[1]), 2),
                          local_rgb_b=round(float(mean_rgb[2]), 2))
        patches.append((descriptor, outline))
    return patches


def analyze_folder(input_dir: Path, output_dir: Path, rois_path: Path | None = None,
                   threshold: float = 4.5, inset: float = .12,
                   plate_map_path: Path | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    overrides = json.loads(rois_path.read_text()) if rois_path else {}
    plate_map = {}
    if plate_map_path:
        with plate_map_path.open(newline="") as file:
            reader = csv.DictReader(file)
            if not {"image_id", "well_id", "sample_id", "dilution"}.issubset(reader.fieldnames or []):
                raise ValueError("Plate map requires image_id,well_id,sample_id,dilution columns")
            for item in reader:
                key = (item["image_id"], item["well_id"])
                if key in plate_map:
                    raise ValueError(f"Duplicate plate map row: {key}")
                plate_map[key] = item
    rows, summaries, found = [], [], {}
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        rgb = read_rgb(path)
        image_id = path.stem
        rois = overrides.get(image_id, detect_wells_full_resolution(rgb))
        found[image_id] = rois
        if len(rois) != 4:
            summaries.append(dict(image_id=image_id, well_id="", candidates="", status=f"review_well_count_{len(rois)}"))
            continue
        for number, roi in enumerate(rois, 1):
            well_id = f"W{number:02d}"
            labels = plate_map.get((image_id, well_id), {})
            rgb_measurements = measure_well_rgb(rgb, roi, inset)
            candidates, _ = find_candidates(rgb, roi, threshold=threshold, inset=inset)
            patches = find_dark_patches(rgb, roi, inset=inset)
            candidates.extend(item for item, _ in patches)
            overlay = rgb.copy()
            cv2.ellipse(overlay, ((roi["cx"], roi["cy"]),
                         (2 * roi["rx"] * (1 - inset), 2 * roi["ry"] * (1 - inset)),
                         roi["angle"]), (0, 220, 0), 3)
            for candidate_id, item in enumerate(candidates, 1):
                item["region"] = ("top" if item["y_px"] < roi["cy"] else "bottom") + "_" + (
                    "left" if item["x_px"] < roi["cx"] else "right")
                rows.append(dict(image_id=image_id, well_id=well_id,
                                 sample_id=labels.get("sample_id", ""), dilution=labels.get("dilution", ""),
                                 candidate_id=candidate_id, **item))
                if item["type"] != "dark_patch":
                    cv2.circle(overlay, (round(item["x_px"]), round(item["y_px"])),
                               max(4, min(13, int(np.sqrt(item["area_px"])))),
                               (255, 0, 255) if item["type"] == "bright" else (0, 220, 255), 2)
            for _, outline in patches:
                cv2.drawContours(overlay, [outline], -1, (255, 80, 80), 3)
            x0 = max(0, int(roi["cx"] - roi["rx"] - 30))
            y0 = max(0, int(roi["cy"] - roi["ry"] - 30))
            x1 = min(rgb.shape[1], int(roi["cx"] + roi["rx"] + 31))
            y1 = min(rgb.shape[0], int(roi["cy"] + roi["ry"] + 31))
            image_dir = output_dir / image_id
            image_dir.mkdir(exist_ok=True)
            Image.fromarray(overlay[y0:y1, x0:x1]).save(image_dir / f"{well_id}_candidates.png")
            save_rgb_scale(image_dir / f"{well_id}_rgb_scale.png", rgb_measurements,
                           f"{image_id} / {well_id}")
            summaries.append(dict(image_id=image_id, well_id=well_id,
                                  sample_id=labels.get("sample_id", ""), dilution=labels.get("dilution", ""),
                                  candidates=len(candidates), small_spots=len(candidates)-len(patches),
                                  dark_patches=len(patches), status="needs_colony_review",
                                  **rgb_measurements))
    with (output_dir / "candidates.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "candidate_review_template.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS + ["is_colony", "review_notes", "experiment_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "is_colony": "", "review_notes": "", "experiment_id": ""})
    with (output_dir / "well_summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["image_id", "well_id", "sample_id", "dilution", "candidates",
                                                  "small_spots", "dark_patches", "status",
                                                  "R_median_0_255", "G_median_0_255", "B_median_0_255",
                                                  "R_iqr_0_255", "G_iqr_0_255", "B_iqr_0_255",
                                                  "rgb_pixel_count"])
        writer.writeheader()
        for row in summaries:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    with (output_dir / "region_summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["image_id", "well_id", "sample_id", "dilution", "region", "candidates"])
        writer.writeheader()
        for summary in summaries:
            if not summary["well_id"]:
                continue
            for region in ("top_left", "top_right", "bottom_left", "bottom_right"):
                writer.writerow(dict(image_id=summary["image_id"], well_id=summary["well_id"],
                                     sample_id=summary["sample_id"], dilution=summary["dilution"],
                                     region=region, candidates=sum(
                                         row["image_id"] == summary["image_id"] and
                                         row["well_id"] == summary["well_id"] and row["region"] == region
                                         for row in rows)))
    (output_dir / "rois.json").write_text(json.dumps(found, indent=2))
    (output_dir / "run.json").write_text(json.dumps({
        "images": len(found), "wells_reviewed": sum(bool(r["well_id"]) for r in summaries),
        "candidate_regions": len(rows), "original_pixel_dimensions_used": True,
        "threshold_mad": threshold, "inset_fraction": inset,
        "interpretation": "Unverified optical candidates; no supervised colony model trained."
    }, indent=2))
    return {"images": len(found), "wells": sum(bool(r["well_id"]) for r in summaries),
            "candidates": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("colony-results"))
    parser.add_argument("--rois", type=Path, help="Optional reviewed well outlines from rois.json")
    parser.add_argument("--plate-map", type=Path, help="CSV: image_id,well_id,sample_id,dilution")
    parser.add_argument("--threshold", type=float, default=4.5, help="Contrast threshold in robust noise units")
    parser.add_argument("--inset", type=float, default=.12, help="Fraction of well radius excluded at edge")
    args = parser.parse_args()
    print(json.dumps(analyze_folder(args.input, args.output, args.rois, args.threshold, args.inset,
                                    args.plate_map)))


if __name__ == "__main__":
    main()
