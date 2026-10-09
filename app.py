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
                                        plate_map_path=map_path)
            except (ValueError, OSError) as error:
                st.error(f"Analysis could not finish: {error}")
                st.stop()
            summary = pd.read_csv(output / "well_summary.csv")
            details = pd.read_csv(output / "regions.csv")
            previews = [(p.relative_to(output).as_posix(), p.read_bytes())
                        for p in sorted(output.glob("*/*_bright_regions.png"))]
            layer_images = {p.relative_to(output).as_posix(): p.read_bytes()
                            for suffix in ("broad", "cores", "peaks")
                            for p in sorted(output.glob(f"*/*_{suffix}.png"))}
            color_keys = {p.relative_to(output).as_posix(): p.read_bytes()
                          for p in sorted(output.glob("*/*_color_key.png"))}
            buffer = BytesIO()
            with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
                for path in sorted(output.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(output))
            st.session_state["analysis"] = (report, summary, details, previews, layer_images,
                                            color_keys, buffer.getvalue())

if "analysis" in st.session_state:
    report, summary, details, previews, layer_images, color_keys, bundle = st.session_state["analysis"]
    st.subheader("Results")
    st.write(f"{report['images']} readable images · {report['wells']} wells · "
             f"{report['regions']} region annotations")
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
            st.dataframe(rows[["region_id", "kind", "area_px", "mean_R_0_255",
                               "mean_G_0_255", "mean_B_0_255", "ratio_R_to_G",
                               "ratio_B_to_G", "sample_hex"]].rename(columns={
                                   "region_id": "Region", "kind": "Type", "area_px": "Size (pixels)",
                                   "mean_R_0_255": "R", "mean_G_0_255": "G", "mean_B_0_255": "B",
                                   "ratio_R_to_G": "R/G", "ratio_B_to_G": "B/G",
                                   "sample_hex": "Sample color"}), hide_index=True, use_container_width=True)
            if not rows.empty:
                selected_id = st.selectbox("Individual region", rows["region_id"].tolist(),
                                           format_func=lambda number: f"Region {number}")
                mode = st.selectbox("RGB measurement", ["Average", "Centroid pixel", "Integrated intensity"])
                selected = rows.loc[rows["region_id"] == selected_id].iloc[0]
                prefix = {"Average": "mean", "Centroid pixel": "centroid",
                          "Integrated intensity": "integrated"}[mode]
                values = [selected[f"{prefix}_{channel}" + ("_0_255" if prefix != "integrated" else "")]
                          for channel in "RGB"]
                chart = pd.DataFrame([dict(zip("RGB", [float(value) for value in values]))],
                                     index=[mode])
                st.bar_chart(chart, color=["#d64b4b", "#4aab62", "#537ee6"])
                st.write(" · ".join(f"{channel}: {value:,.2f}" if prefix == "mean" else
                                    f"{channel}: {int(value):,}" for channel, value in zip("RGB", values)))
                if prefix == "centroid":
                    st.caption(f"Nearest region pixel to its geometric center: "
                               f"({int(selected['centroid_pixel_x_px'])}, {int(selected['centroid_pixel_y_px'])}).")
                elif prefix == "integrated":
                    st.caption("Sum of each source channel across the region's pixels; units are encoded RGB value × pixels.")
            key_name = chosen.replace("_bright_regions.png", "_color_key.png")
            with st.expander("Open RGB color key and distributions"):
                st.image(color_keys[key_name], caption="One swatch, mean RGB triplet, and RGB histogram for every region.")
        st.caption("RGB values are the source image's encoded channels (0–255), preserving its Display P3 values where present; swatches are approximate on sRGB screens. These are not calibrated fluorescence.")
    st.caption("A region count of zero means no area met these image settings; it does not establish biological absence.")
