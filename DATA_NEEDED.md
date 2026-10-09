# Information needed to train a biological model

For each physical well: sample ID, organism identity (confirmed), concentration and units if relevant, blank/negative/positive-control status, dye and preparation, independent experiment ID, and reference assay outcome.

For each photograph: which physical wells appear, whether it repeats an earlier capture, excitation and filter settings, exposure/ISO/white balance, device, and acquisition time. Do not treat ten photographs of four wells as forty independent samples.

Confirm what the model should predict: organism class, positive/negative result, or a numerical load. This version implements class prediction; numerical-load regression is not fitted.

Handwritten labels appear to include E. coli and 1.0, but labels and units are intentionally not inferred for training. All supplied rows need confirmation.

The earlier RF/B convention must be documented with the actual excitation-reference region or reference measurement. The current frames do not establish a valid blue reference or blank. Until supplied, those values remain absent rather than fabricated.
