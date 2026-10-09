"""Full-resolution grouping of bright, locally uniform regions inside DMEF wells.

This is image segmentation. A highlighted region is not a verified colony.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy import ndimage as ndi

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
REGION_FIELDS = ["image_id", "well_id", "region_id", "kind", "area_px", "center_x_px", "center_y_px",
                 "centroid_pixel_x_px", "centroid_pixel_y_px",
                 "mean_R_0_255", "mean_G_0_255", "mean_B_0_255",
                 "centroid_R_0_255", "centroid_G_0_255", "centroid_B_0_255",
                 "integrated_R", "integrated_G", "integrated_B", "integrated_RGB_total",
                 "ratio_R_to_G", "ratio_B_to_G", "mean_brightness_0_255",
                 "mean_local_color_std", "sample_hex", "sample_id", "dilution"]
PALETTE = [(255, 74, 83), (64, 211, 240), (139, 234, 85), (219, 122, 247),
           (255, 184, 63), (57, 121, 255), (245, 103, 180), (97, 233, 181)]


def read_rgb(path: Path) -> np.ndarray:
    """Return decoded, EXIF-oriented source RGB without profile conversion.

    Converting Display P3 JPEGs to sRGB can clip a small blue component to zero
    in saturated yellow areas. Measurements must preserve the source channels.
    """
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source)
            image.load()  # Refuse truncated photos; filling missing pixels would corrupt measurements.
            return np.asarray(image.convert("RGB"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Image could not be decoded completely: {path.name}: {exc}") from exc


def interior_mask(shape: tuple[int, int], roi: dict, inset: float) -> np.ndarray:
    y, x = np.ogrid[:shape[0], :shape[1]]
    angle = np.deg2rad(roi["angle"])
    dx, dy = x - roi["cx"], y - roi["cy"]
    u = dx * np.cos(angle) + dy * np.sin(angle)
    v = -dx * np.sin(angle) + dy * np.cos(angle)
    return (u / roi["rx"]) ** 2 + (v / roi["ry"]) ** 2 <= (1 - inset) ** 2


def detect_wells(rgb: np.ndarray) -> list[dict]:
    """Find four colored well interiors using the original image pixels."""
    hsv = np.asarray(Image.fromarray(rgb).convert("HSV"))
    h, w = hsv.shape[:2]
    colored = ((hsv[:, :, 0] >= 17) & (hsv[:, :, 0] <= 68)
               & (hsv[:, :, 1] >= 60) & (hsv[:, :, 2] >= 130))
    colored = ndi.binary_closing(colored, structure=np.ones((15, 15), bool))
    labels, _ = ndi.label(colored)
    counts = np.bincount(labels.ravel())
    boxes = ndi.find_objects(labels)
    wells = []
    for index in np.where((counts > .01 * h * w) & (counts < .05 * h * w))[0]:
        if index == 0:
            continue
        sy, sx = boxes[index - 1]
        bh, bw = sy.stop - sy.start, sx.stop - sx.start
        fill = counts[index] / (bh * bw)
        if not (.72 < bh / bw < 1.28 and .55 < fill < .9):
            continue
        yy, xx = np.nonzero(labels[sy, sx] == index)
        xx = xx.astype(float) + sx.start
        yy = yy.astype(float) + sy.start
        covariance = np.cov(np.stack((xx, yy)))
        values, vectors = np.linalg.eigh(covariance)
        order = np.argsort(values)[::-1]
        major, minor = np.maximum(values[order], 1)
        direction = vectors[:, order[0]]
        wells.append({"cx": float(xx.mean()), "cy": float(yy.mean()),
                      "rx": float(2 * np.sqrt(major)), "ry": float(2 * np.sqrt(minor)),
                      "angle": float(np.rad2deg(np.arctan2(direction[1], direction[0])))})
    wells.sort(key=lambda r: r["cy"])
    if len(wells) == 4:
        wells = sorted(wells[:2], key=lambda r: r["cx"]) + sorted(wells[2:], key=lambda r: r["cx"])
    return wells


def segment_well(rgb: np.ndarray, roi: dict, *, inset: float = .12,
                 brightness_percentile: int = 75, uniformity_percentile: int = 80,
                 min_area_fraction: float = .0007) -> tuple[np.ndarray, list[dict], np.ndarray, dict]:
    """Find broad bright areas, brighter cores, and small local peaks separately.

    Each pass has its own connected components. A core or peak may overlap a
    broad region; its area is measured independently and must not be summed.
    """
    if not 0 <= inset < .5 or not 0 < brightness_percentile < 100 or not 0 < uniformity_percentile < 100:
        raise ValueError("Invalid segmentation settings")
    x0 = max(0, int(roi["cx"] - max(roi["rx"], roi["ry"]) - 5))
    y0 = max(0, int(roi["cy"] - max(roi["rx"], roi["ry"]) - 5))
    x1 = min(rgb.shape[1], int(roi["cx"] + max(roi["rx"], roi["ry"]) + 6))
    y1 = min(rgb.shape[0], int(roi["cy"] + max(roi["rx"], roi["ry"]) + 6))
    crop = rgb[y0:y1, x0:x1].copy()
    local_roi = {**roi, "cx": roi["cx"] - x0, "cy": roi["cy"] - y0}
    inside = interior_mask(crop.shape[:2], local_roi, inset)
    if not inside.any():
        raise ValueError("Empty well interior")
    smooth = np.stack([ndi.gaussian_filter(crop[:, :, i].astype(np.float32), 2) for i in range(3)], axis=2)
    brightness = smooth @ np.array([.2126, .7152, .0722], dtype=np.float32)
    local_means = [ndi.uniform_filter(smooth[:, :, i], size=21) for i in range(3)]
    variances = [np.maximum(ndi.uniform_filter(smooth[:, :, i] ** 2, size=21) -
                            local_means[i] ** 2, 0) for i in range(3)]
    color_std = np.sqrt(sum(variances) / 3)
    values = brightness[inside]
    median = float(np.median(values))
    span = float(np.percentile(values, 98)) - median
    region_map = np.zeros(brightness.shape, dtype=np.uint8)  # union, not unique IDs
    regions = []

    def add_components(selected: np.ndarray, kind: str, minimum: int, limit: int) -> None:
        selected = ndi.binary_opening(selected, iterations=1)
        selected = ndi.binary_closing(selected, iterations=2) & inside
        labels, _ = ndi.label(selected, structure=np.ones((3, 3), bool))
        areas = np.bincount(labels.ravel())
        eligible = [i for i in range(1, len(areas)) if areas[i] >= minimum]
        eligible.sort(key=lambda i: (-areas[i], i))
        added = 0
        for label_id in eligible:
            if added >= limit:
                break
            pixels = labels == label_id
            # A near-identical mask from another pass is redundant; nested
            # cores and distinct local peaks remain separate annotations.
            if any(abs(int(areas[label_id]) - r["area_px"]) < .08 * r["area_px"]
                   and np.count_nonzero(pixels & r["mask"]) / max(1, int(areas[label_id])) > .88
                   for r in regions):
                continue
            ys, xs = np.nonzero(pixels)
            mean_rgb = crop[pixels].mean(axis=0)
            center_x, center_y = float(xs.mean()), float(ys.mean())
            nearest = np.argmin((xs - center_x) ** 2 + (ys - center_y) ** 2)
            centroid_x, centroid_y = int(xs[nearest]), int(ys[nearest])
            centroid_rgb = crop[centroid_y, centroid_x]
            integrated = crop[pixels].sum(axis=0, dtype=np.uint64)
            region_id = len(regions) + 1
            region_map[pixels] = 1
            regions.append({"region_id": region_id, "kind": kind, "area_px": int(areas[label_id]),
                            "center_x_px": round(center_x + x0, 1),
                            "center_y_px": round(center_y + y0, 1),
                            "centroid_pixel_x_px": centroid_x + x0,
                            "centroid_pixel_y_px": centroid_y + y0,
                            "mean_R_0_255": round(float(mean_rgb[0]), 2),
                            "mean_G_0_255": round(float(mean_rgb[1]), 2),
                            "mean_B_0_255": round(float(mean_rgb[2]), 2),
                            "centroid_R_0_255": int(centroid_rgb[0]),
                            "centroid_G_0_255": int(centroid_rgb[1]),
                            "centroid_B_0_255": int(centroid_rgb[2]),
                            "integrated_R": int(integrated[0]),
                            "integrated_G": int(integrated[1]),
                            "integrated_B": int(integrated[2]),
                            "integrated_RGB_total": int(integrated.sum()),
                            "ratio_R_to_G": round(float(integrated[0] / integrated[1]), 4) if integrated[1] else "",
                            "ratio_B_to_G": round(float(integrated[2] / integrated[1]), 4) if integrated[1] else "",
                            "mean_brightness_0_255": round(float(brightness[pixels].mean()), 2),
                            "mean_local_color_std": round(float(color_std[pixels].mean()), 2),
                            "sample_hex": "#" + "".join(f"{int(round(v)):02X}" for v in mean_rgb),
                            "pixels_rgb": crop[pixels], "mask": pixels})
            added += 1

    def threshold(percentile: int, uniform_percentile: int) -> tuple[np.ndarray, float, float]:
        cutoff = max(float(np.percentile(values, percentile)), median + max(2., .12 * span))
        bright = inside & (brightness >= cutoff)
        variation = float(np.percentile(color_std[bright], uniform_percentile)) if bright.any() else 0.
        return bright & (color_std <= variation), cutoff, variation

    broad, bright_cut, uniform_cut = threshold(brightness_percentile, uniformity_percentile)
    add_components(broad, "broad", max(100, int(min_area_fraction * inside.sum())), 20)
    core, _, _ = threshold(min(97, brightness_percentile + 15), min(95, uniformity_percentile + 5))
    add_components(core, "bright core", max(55, int(.0003 * inside.sum())), 12)
    local_contrast = brightness - ndi.gaussian_filter(brightness, 18)
    contrast_cut = max(2., float(np.percentile(local_contrast[inside], 92)))
    peak = inside & (brightness >= median + max(2., .05 * span)) & (local_contrast >= contrast_cut)
    add_components(peak, "local peak", max(60, int(.0003 * inside.sum())), 16)
    settings = {"brightness_cut_0_255": round(bright_cut, 2),
                "uniformity_cut": round(uniform_cut, 2), "interior_pixels": int(inside.sum()),
                "selected_fraction": round(float(np.count_nonzero(region_map) / inside.sum()), 4),
                "crop_origin": [x0, y0]}
    return crop, regions, region_map, settings


def save_overlay(path: Path, crop: np.ndarray, region_map: np.ndarray,
                 regions: list[dict], origin: tuple[int, int], kind: str | None = None) -> None:
    regions = [region for region in regions if kind is None or region["kind"] == kind]
    overlay = crop.astype(np.float32).copy()
    for region in regions:
        mask = region["mask"]
        color = np.asarray(PALETTE[(region["region_id"] - 1) % len(PALETTE)], dtype=np.float32)
        overlay[mask] = .70 * overlay[mask] + .30 * color
    marked = np.clip(overlay, 0, 255).astype(np.uint8)
    for region in regions:
        mask = region["mask"]
        boundary = ndi.binary_dilation(mask, iterations=2) ^ ndi.binary_erosion(mask, iterations=2)
        marked[boundary] = PALETTE[(region["region_id"] - 1) % len(PALETTE)]
    image = Image.fromarray(marked)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    occupied = []
    for region in regions:
        x = region["center_x_px"] - origin[0]
        y = region["center_y_px"] - origin[1]
        width = 32 if region["region_id"] >= 10 else 24
        for dx, dy in ((0, 0), (0, -27), (27, 0), (-27, 0), (0, 27),
                       (29, -29), (-29, -29), (29, 29), (-29, 29)):
            nx, ny = np.clip(x + dx, 20, image.width - 20), np.clip(y + dy, 20, image.height - 20)
            box = (nx - width / 2, ny - 13, nx + width / 2, ny + 13)
            if not any(box[0] < other[2] and box[2] > other[0] and
                       box[1] < other[3] and box[3] > other[1] for other in occupied):
                break
        occupied.append(box)
        draw.text((nx, ny), str(region["region_id"]), fill="white", stroke_width=3,
                  stroke_fill="black", anchor="mm", font=font)
    image.save(path)


def save_color_key(path: Path, regions: list[dict], image_id: str, well_id: str) -> None:
    if not regions:
        image = Image.new("RGB", (900, 180), "white")
        ImageDraw.Draw(image).text((25, 75), f"{image_id} / {well_id}: no bright, uniform region met the settings", fill="black")
        image.save(path)
        return
    fig, axes = plt.subplots(len(regions), 2, figsize=(10, 1.1 * len(regions) + .7),
                             gridspec_kw={"width_ratios": [1.1, 2.5]})
    axes = np.atleast_2d(axes)
    fig.suptitle(f"{image_id} / {well_id}: source RGB values by highlighted region", fontsize=12)
    for region, (key_ax, hist_ax) in zip(regions, axes):
        color = np.array([region[f"mean_{c}_0_255"] for c in "RGB"]) / 255
        key_ax.add_patch(plt.Rectangle((0, .18), (.3), .64, color=color))
        key_ax.text(.37, .64, f"Region {region['region_id']} ({region['kind']})  ·  {region['area_px']:,} px", fontsize=9)
        key_ax.text(.37, .34, "RGB (" + ", ".join(
            f"{region[f'mean_{channel}_0_255']:.2f}" for channel in "RGB") + ")",
                    fontsize=10)
        key_ax.set_xlim(0, 1.8)
        key_ax.set_ylim(0, 1)
        key_ax.axis("off")
        for channel, color_name in enumerate(("red", "green", "blue")):
            counts = np.bincount(region["pixels_rgb"][:, channel], minlength=256)
            hist_ax.fill_between(np.arange(256), counts, step="mid",
                                 color=color_name, alpha=.42, label="RGB"[channel])
        hist_ax.set_xlim(0, 255)
        hist_ax.set_yticks([])
        if region["region_id"] == len(regions):
            hist_ax.set_xlabel("Source image RGB channel value (0–255)")
        if region["region_id"] == 1:
            hist_ax.legend(loc="upper left", ncol=3, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, .97))
    fig.savefig(path, dpi=115)
    plt.close(fig)


def analyze_folder(input_dir: Path, output_dir: Path, *, rois_path: Path | None = None,
                   plate_map_path: Path | None = None, brightness_percentile: int = 75,
                   uniformity_percentile: int = 80, inset: float = .12) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    overrides = json.loads(rois_path.read_text()) if rois_path else {}
    plate_map = {}
    if plate_map_path:
        with plate_map_path.open(newline="") as file:
            reader = csv.DictReader(file)
            if not {"image_id", "well_id", "sample_id", "dilution"}.issubset(reader.fieldnames or []):
                raise ValueError("Plate map needs image_id,well_id,sample_id,dilution")
            for row in reader:
                key = row["image_id"], row["well_id"]
                if key in plate_map:
                    raise ValueError(f"Duplicate plate map entry: {key}")
                plate_map[key] = row
    records, summary, found = [], [], {}
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        image_id = path.stem
        try:
            rgb = read_rgb(path)
        except ValueError as exc:
            summary.append({"image_id": image_id, "well_id": "", "status": str(exc)})
            continue
        rois = overrides.get(image_id)
        if rois is None:
            rois = detect_wells(rgb)
        found[image_id] = rois
        if len(rois) != 4:
            summary.append({"image_id": image_id, "well_id": "", "status": f"review_well_count_{len(rois)}"})
            continue
        for index, roi in enumerate(rois, 1):
            well_id = f"W{index:02d}"
            crop, regions, region_map, settings = segment_well(
                rgb, roi, inset=inset, brightness_percentile=brightness_percentile,
                uniformity_percentile=uniformity_percentile)
            destination = output_dir / image_id
            destination.mkdir(exist_ok=True)
            save_overlay(destination / f"{well_id}_bright_regions.png", crop, region_map,
                         regions, tuple(settings["crop_origin"]))
            for kind, suffix in (("broad", "broad"), ("bright core", "cores"),
                                 ("local peak", "peaks")):
                save_overlay(destination / f"{well_id}_{suffix}.png", crop, region_map,
                             regions, tuple(settings["crop_origin"]), kind=kind)
            save_color_key(destination / f"{well_id}_color_key.png", regions, image_id, well_id)
            labels = plate_map.get((image_id, well_id), {})
            for region in regions:
                records.append({"image_id": image_id, "well_id": well_id,
                                **{key: region[key] for key in REGION_FIELDS if key in region},
                                "sample_id": labels.get("sample_id", ""),
                                "dilution": labels.get("dilution", "")})
            summary.append({"image_id": image_id, "well_id": well_id, "status": "needs_review",
                            "regions": len(regions), "sample_id": labels.get("sample_id", ""),
                            "dilution": labels.get("dilution", ""), **{k: v for k, v in settings.items()
                                                                       if k != "crop_origin"}})
    with (output_dir / "regions.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REGION_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    fields = ["image_id", "well_id", "status", "regions", "sample_id", "dilution",
              "brightness_cut_0_255", "uniformity_cut", "interior_pixels", "selected_fraction"]
    with (output_dir / "well_summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in summary:
            writer.writerow({key: row.get(key, "") for key in fields})
    (output_dir / "rois.json").write_text(json.dumps(found, indent=2))
    (output_dir / "run.json").write_text(json.dumps({
        "brightness_percentile": brightness_percentile,
        "uniformity_percentile": uniformity_percentile, "inset": inset,
        "processed_images": len(found), "wells": sum(bool(r["well_id"]) for r in summary),
        "regions": len(records), "skipped_images": [r["image_id"] for r in summary if not r["well_id"]],
        "interpretation": "Source encoded RGB (without ICC gamut conversion); regions are not verified colonies or calibrated fluorescence"
    }, indent=2))
    return {"images": len(found), "wells": sum(bool(r["well_id"]) for r in summary),
            "regions": len(records), "skipped": [r["image_id"] for r in summary if not r["well_id"]]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("bright-results"))
    parser.add_argument("--rois", type=Path)
    parser.add_argument("--plate-map", type=Path)
    parser.add_argument("--brightness-percentile", type=int, default=75)
    parser.add_argument("--uniformity-percentile", type=int, default=80)
    parser.add_argument("--inset", type=float, default=.12)
    args = parser.parse_args()
    print(json.dumps(analyze_folder(args.input, args.output, rois_path=args.rois,
                                    plate_map_path=args.plate_map,
                                    brightness_percentile=args.brightness_percentile,
                                    uniformity_percentile=args.uniformity_percentile,
                                    inset=args.inset)))


if __name__ == "__main__":
    main()
