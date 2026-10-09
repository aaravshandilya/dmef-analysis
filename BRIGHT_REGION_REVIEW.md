# Bright region review

The rebuilt interface finds bright, locally uniform, connected pixel groups
inside detected wells. Its colored outlines and numbers identify regions; the
matching color key shows each region's mean source RGB and per-channel spread.

The source JPEGs are Display P3. An earlier version converted them to sRGB
before calculating means, which clipped blue to zero in some saturated yellow
regions. This version measures decoded source RGB channels without that gamut
conversion. The color swatches are visual approximations on sRGB screens; the
CSV triplets are the source-channel values.

The tuned run used the original image pixels, a 75th percentile broad-area
brightness setting, an 80th percentile local uniformity setting, and a 12%
excluded rim. Separate passes find brighter cores and local peaks. On the ten
included JPEGs it produced 40 wells and 1,475 annotations: 450 broad areas,
390 bright cores, and 635 local peaks. Each well has 21–48 annotations. All
1,475 regions have nonzero mean blue values (minimum 1.31 on the source 0–255
scale). All ten complete JPEGs
decoded and all 40 well positions were found. An incomplete working copy of
`04-IMG_0986.jpeg` was replaced with the complete, tracked original before
this run.

These are image segments, not colony labels. Some genuine colonies may be dark,
and some highlighted bright regions may be reflections or background changes.
Regions in different passes may overlap. Their counts and areas must not be
summed to estimate distinct biological objects or unique coverage.
To measure accuracy, mark representative true regions and false highlights on
independent photos, then compare the numbered outlines to those annotations.
Tune settings against a review set and evaluate on separate images. Repeated
captures of one well should stay in the same split.

Run `python bright_regions.py --input data/raw --output bright-results` to
recreate the files. In the upload app, open a well overlay beside its color key
and download its CSVs and images for closer inspection.
