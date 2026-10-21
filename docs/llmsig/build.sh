#!/usr/bin/env bash
# Regenerate the slide figures (bare, no in-figure titles) and render the talk to HTML and PPTX.
# Run from anywhere: docs/llmsig/build.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

figures=docs/llmsig/figures
uv run --project eval eval/present_context.py --bare --out "$figures/context"
uv run --project eval eval/present_figures.py --bare --out "$figures/compare"
uv run --project eval eval/present_best.py --bare --out "$figures/best"
uv run --project eval eval/iaa_experience.py --bare --input eval-data/iaa/batch_a --out "$figures/iaa" \
  --metrics "$figures/iaa_metrics.json"
uv run --project eval eval/iaa_labels.py --bare --input eval-data/iaa/batch_a --out "$figures/iaa" \
  --metrics "$figures/iaa_label_metrics.json"

uv run --with python-pptx docs/llmsig/make_reference.py
quarto render docs/llmsig/eicat-ai-talk.qmd
uv run --with python-pptx docs/llmsig/finish_pptx.py
