# Region measurements and sample files

The detector segments bright image areas inside each well at the original pixel
resolution. A row of `regions.csv` describes **one numbered image region**.
Broad areas, bright cores, and local peaks may overlap. None of these rows is
automatically a verified colony.

## Three RGB views

| View in the app | Calculation for each R, G, B channel | Units | How to read it |
| --- | --- | --- | --- |
| Average | Sum of channel values in the region / `area_px` | encoded image value, 0–255 | Typical color of the whole region. |
| Centroid pixel | Channel value at the region pixel nearest its geometric center | encoded image value, 0–255 | A representative single-pixel reading; can differ from the average. |
| Integrated intensity | Sum of channel values over all pixels in the region | encoded image value × pixels | Combined signal over the whole area; grows with region size. |

The geometric centroid (`center_x_px`, `center_y_px`) can fall outside a curved
or hollow mask. The actual sampled location is
(`centroid_pixel_x_px`, `centroid_pixel_y_px`) in full-image coordinates.
`integrated_RGB_total` adds the three channel sums; it is **not** a calibrated
physical light measurement or the integral of a wavelength spectrum.

The included JPEGs use Display P3. The numbers preserve decoded source JPEG
channels without converting the gamut to sRGB. RGB histograms in each well's
`W##_color_key.png` show the pixel-value distributions, not a spectrometer
measurement. Do not compare these values across different cameras or exposure
settings without calibration.

## Circled background and outside-well areas

`outside_areas.csv` gives the same average, centroid-pixel, integrated RGB,
pixel size, R/G and G/B measurements for each detected white hand-drawn loop.
Loop interiors are labeled C01, C02, and so on. The white stroke and detected
well ellipses with an enlarged rim guard are excluded. If fewer than three
loops can be detected, the analyzer falls back to eight fixed patches: four
image corners (E01, E03, E06, E08) and four edge centers (E02, E04, E05, E07).
The full-image `outside_areas.png` locates the selected pixels;
`outside_color_key.png` shows their RGB swatches and channel distributions.
The `selection_method` field records `white loop` or `fixed edge patch`.
These are image-background references, not biologically validated blanks or
measurements of a wavelength spectrum.

## CSV fields

| Field | Meaning |
| --- | --- |
| `image_id`, `well_id`, `region_id` | Source filename stem, positional well (W01–W04), and overlay number within that well. |
| `kind` | `broad`, `bright core`, or `local peak`; annotations of different kinds can overlap. |
| `area_px` | Number of pixels in the region mask, not a physical area or colony count. |
| `center_x_px`, `center_y_px` | Geometric center of the region in source-image pixel coordinates. |
| `centroid_pixel_x_px`, `centroid_pixel_y_px` | Nearest pixel inside the region to that center. |
| `mean_R_0_255`, `mean_G_0_255`, `mean_B_0_255` | Average source RGB values over the region. |
| `centroid_R_0_255`, `centroid_G_0_255`, `centroid_B_0_255` | Source RGB at the sampled centroid pixel. |
| `integrated_R`, `integrated_G`, `integrated_B` | Sum of all pixel values in each channel. |
| `integrated_RGB_total` | Sum of the three integrated channel values. |
| `ratio_R_to_G`, `ratio_G_to_B` | Integrated R / integrated G and integrated G / integrated B. Equal to ratios of the unrounded channel means. A ratio is blank when its denominator is zero. |
| `mean_brightness_0_255` | Mean of the smoothed weighted RGB brightness used for selection. |
| `mean_local_color_std` | Mean local RGB variation score used in selection; smaller is more uniform. |
| `sample_hex` | Approximate swatch from rounded mean RGB values. |
| `sample_id`, `dilution` | Optional user-provided labels from a plate map; blank unless supplied. |

For a test upload, select the included `data/raw/01-IMG_0989.jpeg` and upload
`sample_plate_map.csv` in the optional plate-map control. Its sample and dilution
labels are **demonstration placeholders** and must not be used as biological
facts. `sample_regions.csv` shows example output rows from that image. The
completed full analysis is in `bright-results/regions.csv`.
`sample_outside_areas.csv` contains the nine detected white-loop background
measurements from the annotated development example.
