# DMEF bright region analysis

Differential Macroscopic DNA/RNA Epi-Fluorescence image analysis for Aarav Shandilya.

## Bright, uniform regions inside wells

The upload interface analyzes original-resolution image pixels inside each well.
It highlights connected groups of pixels that are among the brightest in that
well and have similar local color and brightness. The tuned detector also
finds brighter cores and small local peaks, which may overlap broader areas.
Each numbered region has a
separate color key with an average RGB swatch, red/green/blue values on the
source image's 0–255 encoded RGB scale, and per-channel intensity distributions. The exported
`regions.csv` records the exact averages with two decimal places. The included
JPEGs use Display P3 profiles; measurements preserve their decoded RGB channel
values. The swatches are approximate when viewed on an sRGB display. These
values are neither linear light measurements nor calibrated fluorescence.

These regions describe **image appearance**, not verified bacterial colonies.
The ten supplied photographs have no individually annotated colony locations,
so a supervised colony detector has not been trained. These are likely repeated
views of the same four physical wells and cannot be treated as 40 independent
training samples. Do not interpret the raw candidate counts as colony forming
units or as a dilution series without a confirmed plate map and calibration.

### Run in VS Code on Windows (PowerShell)

Open the extracted `dmef-analysis` folder in VS Code, then use its terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The terminal prints a local address (usually `http://localhost:8501`). Open
it in your browser. Upload original photos or a ZIP of photos, choose settings,
click **Analyze wells**, select a well and region type, inspect its overlay
beside the table of region sizes and RGB values, and download the results ZIP.
Different outline colors and numbers distinguish regions. The swatches represent their original mean RGB values, while the
outline colors are visual markers. Nothing is resized for detection or
measurement; the displayed browser preview may be scaled to fit the page.
A zero count does not establish that a well has no colonies.

For the included photos, you can also run the command-line version:

```powershell
.\.venv\Scripts\python.exe bright_regions.py --input data/raw --output bright-results
```

The supplied `bright-results` directory contains the rebuilt analysis for the
included photographs. `regions.csv` records the region type, area, center, average
RGB, brightness, and swatch. `well_summary.csv` records thresholds and counts;
`rois.json` contains detected well geometry; `run.json` records settings and
images requiring review. Each `W##_bright_regions.png` is a full-resolution
well crop with all numbered outlines. `W##_broad.png`, `W##_cores.png`, and
`W##_peaks.png` show the types separately to reduce visual crowding.
Each `W##_color_key.png` has a swatch, pixel area, average RGB, and channel
distribution for every numbered region. Overlapping areas must not be summed
to estimate unique covered pixels. A completed plate map
CSV may attach confirmed sample and dilution labels to the output. The app
lets you tune brightness cutoff, uniformity, and edge exclusion. These choices
change the detected regions and should be checked against manually marked
examples to assess accuracy.

For one region, the app offers **Average**, **Centroid pixel**, and
**Integrated intensity** RGB views. The area table also includes R/G and B/G
ratios. See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for formulas, units, and
every CSV field. `sample_plate_map.csv` contains demonstration labels for one
image; `sample_regions.csv` contains example output. For GitHub and public
Streamlit hosting steps, see [DEPLOY.md](DEPLOY.md).

### How the bright region analysis works

1. Decode the complete original image and locate the four colored wells.
2. Exclude the reflective outer edge of each well.
3. Smooth pixel values locally at the original resolution. Find broad areas
   above the chosen brightness percentile and below the local color variation
   cutoff. Find brighter cores and small peaks brighter than their neighbors
   in separate passes.
4. Group touching pixels in each pass, discard tiny groups and near duplicate
   masks, and calculate mean RGB from **unsmoothed original pixels** in each
   group. Nested regions remain separate annotations.
5. Export numbered overlays, separate type views, RGB keys, and area tables.
   This is heuristic segmentation, not a trained colony detector. A higher
   annotation count does not establish better detection accuracy.

## Earlier exploratory candidate analysis

The previous `colony_candidates.py` workflow looked for small bright/dark
spots and broad dark patches. It remains in this project as exploratory work;
the current upload interface runs `bright_regions.py`. Run the earlier version
with `python colony_candidates.py --input data/raw --output colony-results`.
The supplied `colony-results` directory contains its earlier pilot output.
`candidates.csv` lists pixel positions, contrast, and well quadrants;
`well_summary.csv` and `region_summary.csv` show counts of *candidates*.
The earlier workflow also produced a chart beside each well. Its three bars show the median
red, green, and blue values of all pixels inside the green ellipse on a fixed
0–255 scale. `well_summary.csv` contains those medians and the channel IQRs;
each `W##_rgb_scale.png` is downloadable with the results. These are stored
camera RGB values, not a wavelength spectrum or calibrated fluorescence.
The `type` column separates `bright`, `dark`, and `dark_patch`. A dark patch
can be a colony-containing region, a shadow, a stain, or uneven illumination;
its area is not a count of individual colonies.
`candidate_review_template.csv` has blank columns for a human reviewer to mark
which proposed spots are actual colonies. Reviewers must also add missed
colonies manually; candidate labels alone cannot measure detection recall.
Use `rois.json` to review or override well geometry. A `plate_map_template.csv`
shows how to identify confirmed samples and dilutions; upload your completed
map in the current interface to attach those labels to the bright-region output. Values from
handwriting on the photos have not been inferred.

For actual model training, obtain marked colony locations, independently
confirmed sample and dilution identities, controls, and separate experiments.
The existing `dmef.py train` command trains only a class predictor from reviewed
well-level RGB measurements when adequate labels exist; it does not detect
individual colonies.

### How the candidate analysis works

1. Read the original full-resolution photo and find the four colored wells.
2. Draw an inner ellipse inside each well to avoid the reflective rim.
3. Compare each pixel with nearby pixels. Mark small bright and dark spots,
   then look separately for larger dark patches.
4. Measure the median red, green, and blue values within the entire inner
   ellipse. Display each value on a 0–255 chart.
5. Export the marked images and tables for human review. The markings are
   visual candidates, not verified colonies or a trained classifier.

## Current status
Ten original JPEG photographs are included. They appear to show repeated captures of the same four-well arrangement. Their independence, sample labels, units, controls, exposure settings, and acquisition conditions are not confirmed. Handwriting is not treated as ground truth. All rows remain unreviewed and all captures use a single `pilot_unconfirmed` group.

The image-analysis pipeline runs now. **No pathogen classifier has been fitted to this pilot, and no biological accuracy is claimed.** A runnable logistic-regression training/prediction pipeline is included but requires reviewed labels, multiple classes, and independent experiments. It intentionally refuses this unlabelled pilot.

## Run (Python 3.12)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python dmef.py analyze
python correct.py
python -m unittest discover -s tests
```
Review `results/<image>/review.png` and RGB plots. Original JPEGs are byte-preserved in `data/raw`. PNG analysis copies are decoded working images; conversion does not recover JPEG losses. EXIF orientation and embedded ICC profiles are handled. Untagged images are flagged. No resizing is used for measurements; detection uses a smaller image and maps coordinates back.

## Implementation
1. Threshold orange/yellow interiors and fit ellipses to accommodate camera angle. This is a pilot heuristic, not a learned biological model; different dyes/colors require revised detection or manual ROIs.
2. Assign four wells in row order (top-left, top-right, bottom-left, bottom-right). These are positional IDs, not confirmed physical sample identities.
3. Compare a circumscribing square, full ellipse, inner ellipse, and candidate-excluded inner ellipse. A square inscribed within the well is a different comparison; square measurement is not inherently invalid.
4. Measure per-channel medians and IQR. Compare 0%, 5%, 10%, and 15% radius reductions. Default 10% is provisional and may omit genuine edge signal. Select a fixed margin against manually reviewed data, not by maximizing intensity.
5. Flag small local intensity changes and near-saturated pixels as candidate artifacts. This does not identify dust vs biology. Preserve both inclusive and candidate-excluded measurements; training defaults to inclusive inner measurements. Mask values: 0 outside, 1 edge band, 2 inner sample, 3 candidate artifact. Review overlays: green boundary, blue edge band, magenta candidates.
6. Store RGB intensity profiles, not wavelength-resolved spectra. Stored channel units are not physical fluorescence units. Camera processing/exposure still affect comparisons.
7. `correct.py` optionally subtracts manually assigned matched-blank medians. Do not use the dark ring as a blank. Only assign controls captured under matching conditions. Signed values are retained. RF/B is left missing unless a positive, independently documented excitation B measurement is provided; sample blue is not silently substituted. These are empirical stored-RGB corrections, not calibrated photon intensities.
8. Review ROI and target labels; assign experiment groups that keep repeated captures and related physical samples together. At least three independent experiments per class is a software minimum, not a sample-size justification.
9. Train a standardized logistic classifier using inner RGB medians and IQR. Three-fold experiment-grouped predictions estimate development performance. Fit preprocessing inside each fold. Reserve additional independent experiments for final external validation. No random well/image split, fabricated labels, or augmentation as independent evidence.

## Manual review and more data
Edit `results/rois.json`: cx/cy are pixel centers after EXIF orientation; rx/ry are ellipse radii; angle is degrees. Rerun using:
```bash
python dmef.py analyze --rois results/rois.json
```
Use a new output directory when adding images so a pre-existing labels file is not overwritten. Correct ROIs before editing labels. Unexpected well counts need manual review. Never assume a detected circle is approved.

Fill `results/labels.csv`: confirmed target class, experiment_id, reviewed=True, roi_reviewed=True. Optional blank_image_id / blank_well_id reference another measured blank; excitation_B must have the same documented measurement convention. Do not infer that handwriting `1.0` means a concentration without units. A plate map, known controls, biological outcomes and acquisition records are needed from Adith.

```bash
python dmef.py train
python dmef.py predict --measurements new-results/measurements.csv --output predictions.csv
```
This baseline predicts classes, not concentration. Only load trusted `.joblib` files. Model files are generated locally. Review prediction inputs using the same imaging/ROI protocol. More data alone does not establish accuracy; class balance, independent experiments and controls matter.

## GitHub repository and public testing app
The project is committed locally but a GitHub repository has not yet been
created. See [DEPLOY.md](DEPLOY.md) for the Windows Git push and Streamlit
Community Cloud publishing workflow. The repository may stay private while
the hosted app is public. Review research photos before deciding whether to
publish repository contents. If GitHub CLI is available, the optional private
repository helper is:
```bash
bash publish-private.sh
```
The script uses your GitHub CLI login, creates `dmef-analysis` as private,
verifies privacy before pushing, and uploads code and included data. It stops
on an existing origin or name collision. No credentials are in this project.

## Earlier pilot results
The earlier pipeline reported four inner wells in every image: 40 measurements across 10 captures. That report predates the current strict image decoding. This is a detection count, not 40 independent biological samples or evidence of detection accuracy on unseen data. All labels remain unconfirmed. The baseline geometry, signed correction, refusal-to-train, and grouped-training smoke tests passed (4 tests). Synthetic smoke-test performance is not reported as research performance.

The download omits large regenerated `analysis.png` copies; rerunning analysis recreates them from included originals. Review images, masks, graphs, and CSV results are included.
