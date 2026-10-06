#!/usr/bin/env python3

"""
===============================================================================
NGAO / GOADI PIPELINE
===============================================================================

Run the complete local NGAO/GOADI workflow.

Default workflow
----------------

    1. Download/update Copernicus ADT data
    2. Compute NGAO and GOADI
    3. Generate figures

Optional
--------

    --qc

also compares the newly generated indices against the legacy reference
indices.

Examples
--------

Run the normal workflow:

    python -m src.goa_indices.cli

Run the workflow and legacy QC:

    python -m src.goa_indices.cli --qc

===============================================================================
"""

import argparse

from . import download
from . import indices
from . import plotting
from . import validation


def parse_arguments():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run the NGAO/GOADI climate-index workflow."
    )

    parser.add_argument(
        "--qc",
        action="store_true",
        help="Run comparison against legacy NGAO/GOADI reference indices.",
    )

    return parser.parse_args()


def main():

    args = parse_arguments()

    print("=" * 72)
    print("NGAO / GOADI COMPLETE WORKFLOW")
    print("=" * 72)

    # -------------------------------------------------------------------------
    # Step 1 — Update observational data
    # -------------------------------------------------------------------------

    print("\nSTEP 1 / 3 — DOWNLOAD DATA")
    print("-" * 72)

    download.main()

    # -------------------------------------------------------------------------
    # Step 2 — Compute indices
    # -------------------------------------------------------------------------

    print("\nSTEP 2 / 3 — COMPUTE NGAO / GOADI")
    print("-" * 72)

    indices.main()

    # -------------------------------------------------------------------------
    # Step 3 — Generate figures
    # -------------------------------------------------------------------------

    print("\nSTEP 3 / 3 — GENERATE FIGURES")
    print("-" * 72)

    plotting.main()

    # -------------------------------------------------------------------------
    # Optional legacy QC
    # -------------------------------------------------------------------------

    if args.qc:

        print("\nOPTIONAL QC — LEGACY COMPARISON")
        print("-" * 72)

        validation.main()

    print("\n" + "=" * 72)
    print("WORKFLOW COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
