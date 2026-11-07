"""Local upload interface for bright, uniform DMEF image regions."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

import pandas as pd
import streamlit as st

from bright_regions import IMAGE_SUFFIXES, analyze_folder


st.set_page_config(page_title="DMEF bright region analysis", layout="wide")
st.title("DMEF bright region analysis")
st.write("Upload original images to find broad light regions, brighter cores, and smaller local peaks inside each well.")
st.info("Highlighted regions describe image appearance. They still need biological review before being called colonies.")

uploads = st.file_uploader("Photos or a ZIP of photos", type=["jpg", "jpeg", "png", "tif", "tiff", "zip"],
                           accept_multiple_files=True)
plate_map = st.file_uploader("Optional plate map (CSV with image_id, well_id, sample_id, dilution)",
                             type=["csv"])
brightness = st.slider("Broad-region brightness cutoff (percentile within each well)", 60, 90, 75, 5,
                       help="Brighter cores and local peaks use their own stricter thresholds.")
uniformity = st.slider("Allowed local color variation (percentile among bright pixels)", 40, 90, 80, 5,
                       help="Lower values require more uniform neighboring pixels.")
inset = st.slider("Exclude the reflective edge (% of radius)", 5, 25, 12, 1) / 100
target_patch_intensity = st.number_input(
    "Target fluorescence patch intensity (green channel)", min_value=1.0, max_value=255.0,
    value=147.0, step=1.0,
    help="Applies one shared scale factor so the pixel-weighted broad-region green average matches this reference. Raw values remain unchanged.")

if st.button("Analyze wells", disabled=not uploads, type="primary"):
    with st.spinner("Analyzing original pixels..."):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "raw"
            output = Path(folder) / "results"
            source.mkdir()
            used = set()
            for upload in uploads:
                if Path(upload.name).suffix.lower() == ".zip":
                    with ZipFile(BytesIO(upload.getvalue())) as archive:
                        members = [entry for entry in archive.infolist()
                                   if not entry.is_dir() and Path(entry.filename).suffix.lower() in IMAGE_SUFFIXES]
                        originals = [entry for entry in members if "data/raw/" in entry.filename.replace("\\", "/")]
                        if originals:
                            members = originals
                        else:
                            generated = {"results", "pilot-results", "colony-results", "bright-results"}
                            members = [entry for entry in members
                                       if not generated.intersection(Path(entry.filename).parts)]
                        if sum(entry.file_size for entry in members) > 500_000_000:
                            st.error("ZIP exceeds the 500 MB image limit.")
                            st.stop()
                        for entry in members:
                            name = Path(entry.filename).name
                            if name in used:
                                st.error(f"Duplicate image filename: {name}")
                                st.stop()
                            used.add(name)
                            (source / name).write_bytes(archive.read(entry))
                else:
                    name = Path(upload.name).name
                    if name in used:
                        st.error(f"Duplicate image filename: {name}")
                        st.stop()
                    used.add(name)
                    (source / name).write_bytes(upload.getvalue())
            if not used:
                st.error("No supported image files were found.")
                st.stop()
            map_path = None
            if plate_map:
                map_path = Path(folder) / "plate_map.csv"
                map_path.write_bytes(plate_map.getvalue())
            try:
                report = analyze_folder(source, output, brightness_percentile=brightness,
                                        uniformity_percentile=uniformity, inset=inset,
                                        plate_map_path=map_path,
                                        target_patch_intensity=target_patch_intensity)
            except (ValueError, OSError) as error:
                st.error(f"Analysis could not finish: {error}")
                st.stop()
            summary = pd.read_csv(output / "well_summary.csv")
            details = pd.read_csv(output / "regions.csv")
            outside = pd.read_csv(output / "outside_areas.csv")
            previews = [(p.relative_to(output).as_posix(), p.read_bytes())
                        for p in sorted(output.glob("*/*_bright_regions.png"))]
            layer_images = {p.relative_to(output).as_posix(): p.read_bytes()
                            for suffix in ("broad", "cores", "peaks")
                            for p in sorted(output.glob(f"*/*_{suffix}.png"))}
            color_keys = {p.relative_to(output).as_posix(): p.read_bytes()
                          for p in sorted(output.glob("*/*_color_key.png"))}
            outside_overlays = {p.parent.name: p.read_bytes()
                                for p in sorted(output.glob("*/outside_areas.png"))}
            outside_keys = {p.parent.name: p.read_bytes()
                            for p in sorted(output.glob("*/outside_color_key.png"))}
            buffer = BytesIO()
            with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
                for path in sorted(output.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(output))
            st.session_state["analysis"] = (report, summary, details, outside, previews,
                                            layer_images, color_keys, outside_overlays,
                                            outside_keys, buffer.getvalue())

if "analysis" in st.session_state:
    (report, summary, details, outside, previews, layer_images, color_keys,
     outside_overlays, outside_keys, bundle) = st.session_state["analysis"]
    st.subheader("Results")
    st.write(f"{report['images']} readable images · {report['wells']} wells · "
             f"{report['regions']} region annotations · {report['outside_areas']} outside reference areas")
    if report["calibration_factor"] is not None:
        st.caption(f"Fluorescence calibration: broad-region green reference "
                   f"{report['calibration_reference']:.2f} → target {report['calibration_target']:.2f}; "
                   f"shared scale factor {report['calibration_factor']:.6f}×. Raw RGB values are retained.")
    st.caption("Broad regions, brighter cores, and local peaks may overlap. Their areas are measured separately; do not add them to estimate covered area.")
    if report["skipped"]:
        st.warning("Skipped images needing review: " + ", ".join(report["skipped"]))
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.download_button("Download highlights, color keys, and CSVs", bundle,
                       "dmef-bright-regions.zip", "application/zip")
    if previews:
        chosen = st.selectbox("Inspect a well at original resolution", [name for name, _ in previews])
        layer = st.selectbox("Show region type", ["Broad", "Brighter cores", "Local peaks", "All overlays"])
        suffix = {"Broad": "broad", "Brighter cores": "cores", "Local peaks": "peaks"}.get(layer)
        selected_image = (layer_images[chosen.replace("_bright_regions.png", f"_{suffix}.png")]
                          if suffix else dict(previews)[chosen])
        left, right = st.columns(2)
        with left:
            st.image(selected_image, caption="Numbers match the region rows on the right. Use the region type selector to reduce overlap clutter.")
        with right:
            image_id, well_id = chosen.split("/", 1)
            well_id = well_id.split("_", 1)[0]
            rows = details[(details["image_id"] == image_id) & (details["well_id"] == well_id)]
            if suffix:
                rows = rows[rows["kind"] == {"broad": "broad", "cores": "bright core",
                                              "peaks": "local peak"}[suffix]]
            st.subheader("Areas and sizes")
            display_rows = rows.copy()
            display_rows["relative_error_percent"] = display_rows["relative_error_fluorescence"] * 100
            st.dataframe(display_rows[["region_id", "kind", "area_px", "mean_R_0_255",
                               "mean_G_0_255", "mean_B_0_255", "std_fluorescence_0_255",
                               "relative_error_percent", "scaled_mean_fluorescence_0_255", "ratio_R_to_G",
                               "ratio_G_to_B", "sample_hex"]].rename(columns={
                                   "region_id": "Region", "kind": "Type", "area_px": "Size (pixels)",
                                   "mean_R_0_255": "R", "mean_G_0_255": "G", "mean_B_0_255": "B",
                                   "std_fluorescence_0_255": "Fluorescence SD",
                                   "relative_error_percent": "Relative error (%)",
                                   "scaled_mean_fluorescence_0_255": "Scaled fluorescence",
                                   "ratio_R_to_G": "R/G", "ratio_G_to_B": "G/B",
                                   "sample_hex": "Sample color"}), hide_index=True, use_container_width=True)
            if not rows.empty:
                selected_id = st.selectbox("Individual region", rows["region_id"].tolist(),
                                           format_func=lambda number: f"Region {number}")
                mode = st.selectbox("RGB measurement", ["Average", "Calibrated average", "Centroid pixel", "Integrated intensity"])
                selected = rows.loc[rows["region_id"] == selected_id].iloc[0]
                prefix = {"Average": "mean", "Calibrated average": "scaled_mean", "Centroid pixel": "centroid",
                          "Integrated intensity": "integrated"}[mode]
                values = [selected[f"{prefix}_{channel}" + ("_0_255" if prefix != "integrated" else "")]
                          for channel in "RGB"]
                chart = pd.DataFrame([dict(zip("RGB", [float(value) for value in values]))],
                                     index=[mode])
                st.bar_chart(chart, color=["#d64b4b", "#4aab62", "#537ee6"])
                st.write(" · ".join(f"{channel}: {value:,.2f}" if prefix in {"mean", "scaled_mean"} else
                                    f"{channel}: {int(value):,}" for channel, value in zip("RGB", values)))
                if prefix == "centroid":
                    st.caption(f"Nearest region pixel to its geometric center: "
                               f"({int(selected['centroid_pixel_x_px'])}, {int(selected['centroid_pixel_y_px'])}).")
                elif prefix == "integrated":
                    st.caption("Sum of each source channel across the region's pixels; units are encoded RGB value × pixels.")
                elif prefix == "scaled_mean":
                    st.caption(f"Raw averages multiplied by the shared {selected['calibration_scale_factor']:.6f}× calibration factor.")
                st.subheader("Fluorescence precision")
                metric_1, metric_2, metric_3, metric_4 = st.columns(4)
                metric_1.metric("Raw average (G)", f"{selected['mean_fluorescence_0_255']:.2f}")
                metric_2.metric("Standard deviation", f"{selected['std_fluorescence_0_255']:.2f}")
                metric_3.metric("Relative error", f"{100 * selected['relative_error_fluorescence']:.2f}%")
                metric_4.metric("Scaled average", f"{selected['scaled_mean_fluorescence_0_255']:.2f}")
            key_name = chosen.replace("_bright_regions.png", "_color_key.png")
            with st.expander("Open RGB color key and distributions"):
                st.image(color_keys[key_name], caption="One swatch, mean RGB triplet, and RGB histogram for every region.")
        st.caption("Raw RGB values are the source image's encoded channels (0–255), preserving Display P3 values where present. Scaled values use a relative green-channel patch calibration; they are not absolute photon measurements.")
    if outside_overlays:
        st.subheader("Circled background RGB analysis")
        st.caption("When an uploaded image contains at least three white hand-drawn loops, the app measures the pixels inside those loops. The white strokes and detected well footprints are excluded. Images without loops use eight fixed edge reference patches.")
        outside_image = st.selectbox("Image for outside-well analysis", sorted(outside_overlays))
        shown = outside[outside["image_id"] == outside_image]
        left, right = st.columns(2)
        with left:
            st.image(outside_overlays[outside_image], caption="C labels are detected circled backgrounds; E labels are fixed edge references used only when no loops are detected.")
        with right:
            if shown.empty:
                st.info("No outside edge patch remains after excluding the detected well footprints for this image.")
                st.stop()
            display_outside = shown.copy()
            display_outside["relative_error_percent"] = display_outside["relative_error_fluorescence"] * 100
            st.dataframe(display_outside[["area_id", "selection_method", "area_px", "mean_R_0_255",
                                "mean_G_0_255", "mean_B_0_255", "std_fluorescence_0_255",
                                "relative_error_percent", "scaled_mean_fluorescence_0_255", "ratio_R_to_G",
                                "ratio_G_to_B", "sample_hex"]].rename(columns={
                                    "area_id": "Area", "selection_method": "Selection", "area_px": "Size (pixels)",
                                    "mean_R_0_255": "R", "mean_G_0_255": "G",
                                    "mean_B_0_255": "B", "std_fluorescence_0_255": "Fluorescence SD",
                                    "relative_error_percent": "Relative error (%)",
                                    "scaled_mean_fluorescence_0_255": "Scaled fluorescence", "ratio_R_to_G": "R/G",
                                    "ratio_G_to_B": "G/B", "sample_hex": "Sample color"}),
                         hide_index=True, use_container_width=True)
            selected_area = st.selectbox("Outside area", shown["area_id"].tolist())
            selected = shown.loc[shown["area_id"] == selected_area].iloc[0]
            mode = st.selectbox("Outside RGB measurement", ["Average", "Calibrated average", "Centroid pixel", "Integrated intensity"])
            prefix = {"Average": "mean", "Calibrated average": "scaled_mean", "Centroid pixel": "centroid",
                      "Integrated intensity": "integrated"}[mode]
            values = [selected[f"{prefix}_{channel}" + ("_0_255" if prefix != "integrated" else "")]
                      for channel in "RGB"]
            st.bar_chart(pd.DataFrame([dict(zip("RGB", [float(v) for v in values]))], index=[mode]),
                         color=["#d64b4b", "#4aab62", "#537ee6"])
            st.write(" · ".join(f"{channel}: {value:,.2f}" if prefix in {"mean", "scaled_mean"} else
                                f"{channel}: {int(value):,}" for channel, value in zip("RGB", values)))
            if prefix == "centroid":
                st.caption(f"Sampled pixel: ({int(selected['centroid_pixel_x_px'])}, "
                           f"{int(selected['centroid_pixel_y_px'])}).")
            elif prefix == "integrated":
                st.caption("Sum of source channel values over the selected patch; units are encoded RGB value × pixels.")
            elif prefix == "scaled_mean":
                st.caption(f"Raw averages multiplied by the shared {selected['calibration_scale_factor']:.6f}× calibration factor.")
            st.subheader("Background fluorescence precision")
            metric_1, metric_2, metric_3, metric_4 = st.columns(4)
            metric_1.metric("Raw average (G)", f"{selected['mean_fluorescence_0_255']:.2f}")
            metric_2.metric("Standard deviation", f"{selected['std_fluorescence_0_255']:.2f}")
            metric_3.metric("Relative error", f"{100 * selected['relative_error_fluorescence']:.2f}%")
            metric_4.metric("Scaled average", f"{selected['scaled_mean_fluorescence_0_255']:.2f}")
            with st.expander("Open outside-area RGB color key and distributions"):
                st.image(outside_keys[outside_image], caption="Swatch, mean RGB, and channel histograms for each patch.")
    st.caption("A region count of zero means no area met these image settings; it does not establish biological absence.")

