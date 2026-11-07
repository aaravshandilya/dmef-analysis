# Region measurements and sample files

The detector segments bright image areas inside each well at the original pixel
resolution. A row of `regions.csv` describes **one numbered image region**.
Broad areas, bright cores, and local peaks may overlap. None of these rows is
automatically a verified colony.

## Four RGB views

| View in the app | Calculation for each R, G, B channel | Units | How to read it |
| --- | --- | --- | --- |
| Average | Sum of channel values in the region / `area_px` | encoded image value, 0–255 | Typical color of the whole region. |
| Calibrated average | Raw average × one shared calibration factor | relative scaled image value | Preserves differences between areas while matching the selected patch target. |
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

## Fluorescence precision and patch scaling

The app treats the green channel as the fluorescence measurement. For every
well region and outside reference area it reports:

- `mean_fluorescence_0_255`: mean green-channel value.
- `std_fluorescence_0_255`: population standard deviation of green values,
  calculated as `sqrt(sum((G - mean_G)^2) / area_px)`.
- `relative_error_fluorescence`: `std_fluorescence_0_255 /
  mean_fluorescence_0_255`. The website multiplies this decimal by 100 for its
  percent display.

The default target patch intensity is 147. The reference is the pixel-weighted
green average across all broad regions in the run. The shared calibration factor
is `target / reference`; every RGB mean and standard deviation, including the
outside references, is multiplied by that same factor. Raw columns are never
overwritten. This is a relative image calibration, not an absolute photon count,
and it does not apply a distance or inverse-square correction.

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
| `std_R_0_255`, `std_G_0_255`, `std_B_0_255` | Population standard deviation of source pixel values in each channel. |
| `relative_error_R`, `relative_error_G`, `relative_error_B` | Per-channel standard deviation / mean; dimensionless decimals. |
| `mean_fluorescence_0_255`, `std_fluorescence_0_255`, `relative_error_fluorescence` | Green-channel fluorescence average, standard deviation, and SD / average. |
| `centroid_R_0_255`, `centroid_G_0_255`, `centroid_B_0_255` | Source RGB at the sampled centroid pixel. |
| `integrated_R`, `integrated_G`, `integrated_B` | Sum of all pixel values in each channel. |
| `integrated_RGB_total` | Sum of the three integrated channel values. |
| `ratio_R_to_G`, `ratio_G_to_B` | Integrated R / integrated G and integrated G / integrated B. Equal to ratios of the unrounded channel means. A ratio is blank when its denominator is zero. |
| `mean_brightness_0_255` | Mean of the smoothed weighted RGB brightness used for selection. |
| `mean_local_color_std` | Mean local RGB variation score used in selection; smaller is more uniform. |
| `sample_hex` | Approximate swatch from rounded mean RGB values. |
| `calibration_target_0_255` | Requested patch target, 147 by default. |
| `calibration_reference_G_0_255`, `calibration_scale_factor` | Pixel-weighted broad-region green reference and target / reference factor. |
| `scaled_mean_R_0_255`, `scaled_mean_G_0_255`, `scaled_mean_B_0_255` | Raw channel averages multiplied by the shared factor. |
| `scaled_std_R_0_255`, `scaled_std_G_0_255`, `scaled_std_B_0_255` | Raw channel standard deviations multiplied by the shared factor. |
| `scaled_mean_fluorescence_0_255`, `scaled_std_fluorescence_0_255` | Calibrated green average and standard deviation. |
| `sample_id`, `dilution` | Optional user-provided labels from a plate map; blank unless supplied. |

For a test upload, select the included `data/raw/01-IMG_0989.jpeg` and upload
`sample_plate_map.csv` in the optional plate-map control. Its sample and dilution
labels are **demonstration placeholders** and must not be used as biological
facts. `sample_regions.csv` shows example output rows from that image. The
completed full analysis is in `bright-results/regions.csv`.
`sample_outside_areas.csv` contains the nine detected white-loop background
measurements from the annotated development example.

