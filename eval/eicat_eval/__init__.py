"""Shared library for the EICAT-AI evaluation scripts in `eval/`.

The scripts next to this package are the command-line entry points; this package holds everything
more than one of them needs, so that no script imports another script.

Modules:

- `paths`       repository locations and the default inputs and outputs of every script
- `eicat`       the EICAT vocabulary: categories, severity order, mechanisms and display labels
- `gisd`        GISD gold-standard data: reading, merging per-country rows, mechanism names
- `annotators`  inter-annotator study sheets: anonymisation, exclusions, loaders, experience groups
- `agreement`   agreement statistics: pairwise Jaccard, presence matrices, Krippendorff's alpha,
                Landis & Koch bands and an exact permutation test
- `runs`        reading scored GISD evaluation runs
- `style`       OneSTOP brand styling for matplotlib figures
- `charts`      brand chart components shared between figure scripts

Scripts import it as a sibling package (`from eicat_eval import eicat`), which works because Python
puts a script's own directory on the import path; run them with `uv run --project eval eval/<script>.py`.
"""
