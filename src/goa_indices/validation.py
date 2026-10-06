#!/usr/bin/env python3

"""
===============================================================================
NGAO / GOADI LEGACY COMPARISON AND QUALITY CONTROL
===============================================================================

Purpose
-------
Compare the new NGAO and GOADI indices produced by the modernized workflow
against the legacy/reference indices produced by the previous workflow.

The comparison is restricted to months available in BOTH datasets.

This is NOT expected to be an exact regression test because the observational
product has changed:

Legacy workflow
---------------
- primarily 0.25-degree DUACS two-satellite product
- legacy processing/regridding workflow

New workflow
------------
- 0.125-degree DUACS all-satellite product
- native 0.125-degree processing

The scientific index calculation itself remains intentionally unchanged.

Therefore this QC is intended to evaluate SCIENTIFIC CONTINUITY rather than
bit-for-bit reproducibility.

Metrics
-------
For each index:

    - number of overlapping months
    - first common month
    - last common month
    - Pearson correlation
    - RMSE
    - mean difference (new - legacy)
    - legacy mean
    - new mean
    - legacy standard deviation
    - new standard deviation
    - standard-deviation ratio

EOF sign
--------
EOF signs are mathematically arbitrary.

A correlation close to -1 may indicate that the same physical EOF mode has
been returned with the opposite sign.

This script reports such a possibility but DOES NOT automatically change the
sign of either index.

Outputs
-------
outputs/qc/

    legacy_comparison_summary.csv
    NGAO_legacy_comparison.png
    GOADI_legacy_comparison.png

===============================================================================
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# =============================================================================
# PROJECT PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]


LEGACY_DIR = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "legacy_indices"
)

NEW_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "indices"
)

QC_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "qc"
)


LEGACY_NGAO_FILE = (
    LEGACY_DIR
    / "NGAO_monthly_legacy.csv"
)

LEGACY_GOADI_FILE = (
    LEGACY_DIR
    / "GOADI_monthly_legacy.csv"
)

NEW_NGAO_FILE = (
    NEW_DIR
    / "NGAO_monthly.csv"
)

NEW_GOADI_FILE = (
    NEW_DIR
    / "GOADI_monthly.csv"
)


# =============================================================================
# FILE CHECK
# =============================================================================

def check_files():
    """
    Verify that all four files required for the QC comparison exist.
    """

    required_files = [
        LEGACY_NGAO_FILE,
        LEGACY_GOADI_FILE,
        NEW_NGAO_FILE,
        NEW_GOADI_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        message = "\nMissing required QC file(s):\n"

        for path in missing:
            message += f"\n  {path}"

        raise FileNotFoundError(message)


# =============================================================================
# LOAD LEGACY INDEX
# =============================================================================

def load_legacy_index(
    filename,
    index_name,
):
    """
    Load one legacy index CSV.

    The previous CSV format contains an unnecessary pandas index column.

    Legacy GOADI also uses the column name 'DW'.

    Both cases are normalized here without changing numerical values.
    """

    dataframe = pd.read_csv(
        filename
    )


    # -------------------------------------------------------------------------
    # Remove legacy pandas index column, usually named "Unnamed: 0".
    # -------------------------------------------------------------------------

    unnamed_columns = [
        column
        for column in dataframe.columns
        if column.startswith("Unnamed")
    ]

    if unnamed_columns:

        dataframe = dataframe.drop(
            columns=unnamed_columns
        )


    # -------------------------------------------------------------------------
    # Normalize date column name.
    # -------------------------------------------------------------------------

    if "Date" in dataframe.columns:

        dataframe = dataframe.rename(
            columns={
                "Date": "date",
            }
        )


    # -------------------------------------------------------------------------
    # Legacy GOADI is called "DW".
    # -------------------------------------------------------------------------

    if (
        index_name == "GOADI"
        and "DW" in dataframe.columns
    ):

        dataframe = dataframe.rename(
            columns={
                "DW": "GOADI",
            }
        )


    if "date" not in dataframe.columns:

        raise ValueError(
            f"No date column found in {filename}"
        )


    if index_name not in dataframe.columns:

        raise ValueError(
            f"Column '{index_name}' not found in {filename}. "
            f"Available columns: {list(dataframe.columns)}"
        )


    dataframe["date"] = pd.to_datetime(
        dataframe["date"],
        format="%Y-%m",
    )


    return dataframe[
        [
            "date",
            index_name,
        ]
    ]


# =============================================================================
# LOAD NEW INDEX
# =============================================================================

def load_new_index(
    filename,
    index_name,
):
    """
    Load one index generated by the new workflow.
    """

    dataframe = pd.read_csv(
        filename
    )


    required = {
        "date",
        index_name,
    }


    if not required.issubset(
        dataframe.columns
    ):

        raise ValueError(
            f"{filename} must contain columns: "
            f"{sorted(required)}"
        )


    dataframe["date"] = pd.to_datetime(
        dataframe["date"],
        format="%Y-%m",
    )


    return dataframe[
        [
            "date",
            index_name,
        ]
    ]


# =============================================================================
# ALIGN LEGACY AND NEW DATA
# =============================================================================

def align_indices(
    legacy,
    new,
    index_name,
):
    """
    Restrict legacy and new index series to their common monthly period.
    """

    merged = pd.merge(
        legacy,
        new,
        on="date",
        how="inner",
        suffixes=(
            "_legacy",
            "_new",
        ),
    )


    if merged.empty:

        raise ValueError(
            f"No overlapping dates found for {index_name}."
        )


    merged = merged.sort_values(
        "date"
    ).reset_index(
        drop=True
    )


    return merged


# =============================================================================
# COMPUTE QC METRICS
# =============================================================================

def calculate_metrics(
    merged,
    index_name,
):
    """
    Calculate quantitative comparison metrics.
    """

    legacy = merged[
        f"{index_name}_legacy"
    ].to_numpy()

    new = merged[
        f"{index_name}_new"
    ].to_numpy()


    # -------------------------------------------------------------------------
    # Keep only finite values in both datasets.
    # -------------------------------------------------------------------------

    valid = (
        np.isfinite(legacy)
        & np.isfinite(new)
    )


    legacy = legacy[
        valid
    ]

    new = new[
        valid
    ]


    if len(legacy) < 2:

        raise ValueError(
            f"Not enough valid overlapping values for {index_name}."
        )


    correlation = np.corrcoef(
        legacy,
        new,
    )[0, 1]


    difference = (
        new
        - legacy
    )


    rmse = np.sqrt(
        np.mean(
            difference ** 2
        )
    )


    mean_difference = np.mean(
        difference
    )


    legacy_std = np.std(
        legacy,
        ddof=1,
    )

    new_std = np.std(
        new,
        ddof=1,
    )


    if legacy_std != 0:

        std_ratio = (
            new_std
            / legacy_std
        )

    else:

        std_ratio = np.nan


    result = {
        "index": index_name,
        "common_months": len(merged),
        "valid_pairs": len(legacy),
        "first_common_month": (
            merged["date"].iloc[0].strftime(
                "%Y-%m"
            )
        ),
        "last_common_month": (
            merged["date"].iloc[-1].strftime(
                "%Y-%m"
            )
        ),
        "correlation": correlation,
        "absolute_correlation": abs(correlation),
        "rmse": rmse,
        "mean_difference_new_minus_legacy": mean_difference,
        "legacy_mean": np.mean(legacy),
        "new_mean": np.mean(new),
        "legacy_std": legacy_std,
        "new_std": new_std,
        "std_ratio_new_over_legacy": std_ratio,
    }


    return result


# =============================================================================
# PRINT QC RESULTS
# =============================================================================

def print_metrics(
    metrics,
):
    """
    Print one human-readable QC summary.
    """

    print("\n" + "=" * 72)

    print(
        f"{metrics['index']} LEGACY COMPARISON"
    )

    print("=" * 72)


    print(
        f"First common month : "
        f"{metrics['first_common_month']}"
    )

    print(
        f"Last common month  : "
        f"{metrics['last_common_month']}"
    )

    print(
        f"Common months      : "
        f"{metrics['common_months']}"
    )


    print()

    print(
        f"Correlation        : "
        f"{metrics['correlation']:.4f}"
    )

    print(
        f"RMSE               : "
        f"{metrics['rmse']:.4f}"
    )

    print(
        f"Mean difference    : "
        f"{metrics['mean_difference_new_minus_legacy']:.4f}"
    )

    print(
        f"Legacy std         : "
        f"{metrics['legacy_std']:.4f}"
    )

    print(
        f"New std            : "
        f"{metrics['new_std']:.4f}"
    )

    print(
        f"Std ratio          : "
        f"{metrics['std_ratio_new_over_legacy']:.4f}"
    )


    # -------------------------------------------------------------------------
    # EOF sign diagnostic.
    # -------------------------------------------------------------------------

    if metrics["correlation"] < -0.8:

        print(
            "\nWARNING:"
        )

        print(
            "The two index series are strongly negatively correlated."
        )

        print(
            "This may indicate an EOF sign reversal rather than "
            "a different physical mode."
        )

        print(
            "Do NOT automatically flip the sign until the spatial EOF "
            "patterns have also been inspected."
        )


# =============================================================================
# COMPARISON FIGURE
# =============================================================================

def make_comparison_figure(
    merged,
    index_name,
):
    """
    Plot legacy and new index series over their common time period.
    """

    legacy_column = (
        f"{index_name}_legacy"
    )

    new_column = (
        f"{index_name}_new"
    )


    fig, ax = plt.subplots(
        figsize=(18, 5)
    )


    ax.plot(
        merged["date"],
        merged[legacy_column],
        label="Legacy",
        linewidth=1.2,
    )


    ax.plot(
        merged["date"],
        merged[new_column],
        label="New 0.125° all-satellite",
        linewidth=1.2,
    )


    ax.axhline(
        0,
        linewidth=0.8,
        color="black",
    )


    ax.set_ylabel(
        f"{index_name} index"
    )


    ax.set_title(
        f"{index_name}: legacy vs new workflow"
    )


    ax.legend(
        frameon=False
    )


    fig.tight_layout()


    output_file = (
        QC_DIR
        / f"{index_name}_legacy_comparison.png"
    )


    fig.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight",
    )


    plt.close(
        fig
    )


    print(
        f"\nSaved comparison figure:\n"
        f"  {output_file}"
    )


# =============================================================================
# RUN QC FOR ONE INDEX
# =============================================================================

def validate_index(
    legacy_file,
    new_file,
    index_name,
):
    """
    Run the complete QC comparison for one index.
    """

    legacy = load_legacy_index(
        legacy_file,
        index_name,
    )


    new = load_new_index(
        new_file,
        index_name,
    )


    merged = align_indices(
        legacy,
        new,
        index_name,
    )


    metrics = calculate_metrics(
        merged,
        index_name,
    )


    print_metrics(
        metrics
    )


    make_comparison_figure(
        merged,
        index_name,
    )


    return metrics


# =============================================================================
# MAIN
# =============================================================================

def main():

    print("=" * 72)
    print("NGAO / GOADI QUALITY CONTROL")
    print("=" * 72)


    check_files()


    QC_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    ngao_metrics = validate_index(
        LEGACY_NGAO_FILE,
        NEW_NGAO_FILE,
        "NGAO",
    )


    goadi_metrics = validate_index(
        LEGACY_GOADI_FILE,
        NEW_GOADI_FILE,
        "GOADI",
    )


    # -------------------------------------------------------------------------
    # Save machine-readable QC summary.
    # -------------------------------------------------------------------------

    summary = pd.DataFrame(
        [
            ngao_metrics,
            goadi_metrics,
        ]
    )


    summary_file = (
        QC_DIR
        / "legacy_comparison_summary.csv"
    )


    summary.to_csv(
        summary_file,
        index=False,
    )


    print("\n" + "=" * 72)
    print("QC SUMMARY SAVED")
    print("=" * 72)

    print(
        f"\n{summary_file}"
    )


if __name__ == "__main__":
    main()
