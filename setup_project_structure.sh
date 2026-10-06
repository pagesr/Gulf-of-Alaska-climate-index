#!/usr/bin/env bash

set -euo pipefail

echo "Creating NGAO/GOADI project structure..."

# -----------------------------------------------------------------------------
# Source package
# -----------------------------------------------------------------------------

mkdir -p src/goa_indices

touch src/goa_indices/__init__.py
touch src/goa_indices/download.py
touch src/goa_indices/preprocess.py
touch src/goa_indices/indices.py
touch src/goa_indices/plotting.py
touch src/goa_indices/validation.py
touch src/goa_indices/cli.py


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

mkdir -p config

touch config/default.toml


# -----------------------------------------------------------------------------
# Data directories
# -----------------------------------------------------------------------------

mkdir -p data/raw/reprocessed
mkdir -p data/raw/nrt
mkdir -p data/interim
mkdir -p data/processed
mkdir -p data/reference


# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

mkdir -p outputs/indices
mkdir -p outputs/figures


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

mkdir -p tests

touch tests/__init__.py
touch tests/test_download.py
touch tests/test_preprocess.py
touch tests/test_indices.py
touch tests/test_reference_results.py


# -----------------------------------------------------------------------------
# Documentation
# -----------------------------------------------------------------------------

mkdir -p docs

touch docs/methodology.md
touch docs/data_sources.md
touch docs/reproducibility.md
touch docs/architecture.md
touch docs/costs.md


# -----------------------------------------------------------------------------
# Miscellaneous scripts
# -----------------------------------------------------------------------------

mkdir -p scripts


# -----------------------------------------------------------------------------
# GitHub Actions directory
# We create the directory now but will NOT add workflows yet.
# -----------------------------------------------------------------------------

mkdir -p .github/workflows


# -----------------------------------------------------------------------------
# Keep empty generated-data/output directories visible in Git
# -----------------------------------------------------------------------------

touch data/raw/.gitkeep
touch data/interim/.gitkeep
touch data/processed/.gitkeep
touch outputs/indices/.gitkeep
touch outputs/figures/.gitkeep


# -----------------------------------------------------------------------------
# Files we will configure later
# -----------------------------------------------------------------------------

touch pyproject.toml


# -----------------------------------------------------------------------------
# Show resulting structure
# -----------------------------------------------------------------------------

echo
echo "Project structure created."
echo

if command -v tree >/dev/null 2>&1; then
    tree -a -L 4
else
    find . \
        -not -path "./.git/*" \
        -maxdepth 4 \
        | sort
fi
