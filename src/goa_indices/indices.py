#!/usr/bin/env python3

"""
===============================================================================
NGAO / GOADI INDEX CALCULATION
===============================================================================

Purpose
-------
Compute the Northern Gulf of Alaska Oscillation (NGAO) and Gulf of Alaska
Downwelling Index (GOADI) from Copernicus Marine absolute dynamic topography
(ADT).

Input data
----------
The calculation uses two Copernicus Marine 0.125-degree ADT datasets:

    1. Reprocessed historical ADT
       data/raw/reprocessed/adt_reprocessed.nc

    2. Near-real-time ADT
       data/raw/nrt/adt_nrt.nc

The two datasets must:

    - contain the variable "adt";
    - use the same latitude/longitude grid;
    - form one continuous daily time series with no gaps or overlaps.

Spatial mask
------------
The calculation is restricted to the NWGOA ROMS model domain using:

    data/reference/masks/roms_ocean_mask_0125.nc

with:

    roms_ocean_mask = 1 : ocean inside ROMS domain
    roms_ocean_mask = 0 : land or outside ROMS domain

Scientific method
-----------------
IMPORTANT:

The scientific processing below deliberately follows the original NGAO/GOADI
implementation.

The order of operations is:

    daily ADT
        |
        v
    concatenate reprocessed + NRT
        |
        v
    verify continuous daily time axis
        |
        v
    monthly arithmetic mean
        |
        v
    apply ROMS ocean mask
        |
        v
    quadratic detrending at each ocean grid cell
        statsmodels.tsa.tsatools.detrend(order=2)
        |
        v
    estimate seasonal cycle at each grid cell
        statsmodels seasonal_decompose(
            model="additive",
            period=12
        )
        |
        v
    subtract seasonal component
        |
        v
    EOF analysis using eofs.standard.Eof
        |
        +---- PC1 -> NGAO
        |
        +---- PC2 -> GOADI

No latitude weighting, alternative detrending, fixed EOF basis, or other
scientific modification is introduced here.

Outputs
-------
outputs/indices/

    NGAO_monthly.csv
    GOADI_monthly.csv

    NGAO_monthly.npy
    GOADI_monthly.npy
    dates_monthly.npy

    EOF_variance_fractions.csv

Notes
-----
Figures are intentionally NOT produced here.

Plotting belongs in:

    src/goa_indices/plotting.py

This keeps index calculation and visualization as separate steps.

===============================================================================
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.tsa.tsatools
import xarray as xr

from eofs.standard import Eof
from statsmodels.tsa.seasonal import seasonal_decompose


# =============================================================================
# PROJECT PATHS
# =============================================================================

# This file is expected to be:
#
#     repository_root/src/goa_indices/indices.py
#
# Therefore parents[2] is the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# -----------------------------------------------------------------------------
# Input files
# -----------------------------------------------------------------------------

REPROCESSED_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "reprocessed"
    / "adt_reprocessed.nc"
)

NRT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "nrt"
    / "adt_nrt.nc"
)

MASK_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "masks"
    / "roms_ocean_mask_0125.nc"
)


# -----------------------------------------------------------------------------
# Output directory
# -----------------------------------------------------------------------------

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "indices"
)


# =============================================================================
# BASIC FILE VALIDATION
# =============================================================================

def check_required_files():
    """
    Verify that all input files required for the calculation exist.

    This check happens before opening NetCDF files so that missing inputs
    produce a clear error message.
    """

    required_files = [
        REPROCESSED_FILE,
        NRT_FILE,
        MASK_FILE,
    ]

    missing_files = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing_files:

        message = "\nMissing required input file(s):\n"

        for path in missing_files:
            message += f"\n  {path}"

        raise FileNotFoundError(message)


# =============================================================================
# COORDINATE UTILITIES
# =============================================================================

def get_latitude_name(obj):
    """
    Return the latitude coordinate name.

    Copernicus files normally use 'latitude', but supporting 'lat' makes the
    code slightly more robust without altering the scientific calculation.
    """

    if "latitude" in obj.coords:
        return "latitude"

    if "lat" in obj.coords:
        return "lat"

    raise KeyError(
        "Could not find a latitude coordinate "
        "('latitude' or 'lat')."
    )


def get_longitude_name(obj):
    """
    Return the longitude coordinate name.
    """

    if "longitude" in obj.coords:
        return "longitude"

    if "lon" in obj.coords:
        return "lon"

    raise KeyError(
        "Could not find a longitude coordinate "
        "('longitude' or 'lon')."
    )


# =============================================================================
# LOAD ROMS MASK
# =============================================================================

def load_roms_mask():
    """
    Load the ROMS ocean mask on the Copernicus 0.125-degree grid.

    Returns
    -------
    mask_da : xarray.DataArray
        Binary mask with:

            1 = ocean inside ROMS domain
            0 = land or outside ROMS domain
    """

    print("\nLoading ROMS ocean mask:")
    print(f"  {MASK_FILE}")

    with xr.open_dataset(MASK_FILE) as ds_mask:

        if "roms_ocean_mask" not in ds_mask:

            raise KeyError(
                "Variable 'roms_ocean_mask' was not found in "
                f"{MASK_FILE}"
            )

        mask_da = ds_mask["roms_ocean_mask"].load()


    # -------------------------------------------------------------------------
    # Validate that the mask really is binary.
    # -------------------------------------------------------------------------

    unique_values = np.unique(mask_da.values)

    print(f"  Mask values: {unique_values}")

    if not np.all(np.isin(unique_values, [0, 1])):

        raise ValueError(
            "roms_ocean_mask must contain only 0 and 1."
        )


    print(
        "  Mask shape : "
        f"{mask_da.shape}"
    )

    print(
        "  Ocean cells: "
        f"{int(mask_da.sum().values)}"
    )

    return mask_da


# =============================================================================
# VALIDATE THAT GRIDS MATCH
# =============================================================================

def validate_spatial_grid(adt_reprocessed, adt_nrt, mask):
    """
    Verify that the two ADT datasets and ROMS mask use exactly the same
    latitude/longitude grid.

    We deliberately do NOT interpolate anything here.

    The new pipeline uses the same Copernicus 0.125-degree grid throughout.
    A grid mismatch should therefore be treated as an error.
    """

    lat_reprocessed = get_latitude_name(adt_reprocessed)
    lon_reprocessed = get_longitude_name(adt_reprocessed)

    lat_nrt = get_latitude_name(adt_nrt)
    lon_nrt = get_longitude_name(adt_nrt)

    lat_mask = get_latitude_name(mask)
    lon_mask = get_longitude_name(mask)


    # -------------------------------------------------------------------------
    # Compare historical and NRT grids.
    # -------------------------------------------------------------------------

    if not np.array_equal(
        adt_reprocessed[lat_reprocessed].values,
        adt_nrt[lat_nrt].values,
    ):

        raise ValueError(
            "Latitude coordinates differ between "
            "reprocessed and NRT ADT."
        )


    if not np.array_equal(
        adt_reprocessed[lon_reprocessed].values,
        adt_nrt[lon_nrt].values,
    ):

        raise ValueError(
            "Longitude coordinates differ between "
            "reprocessed and NRT ADT."
        )


    # -------------------------------------------------------------------------
    # Compare satellite grid and mask grid.
    # -------------------------------------------------------------------------

    if not np.array_equal(
        adt_reprocessed[lat_reprocessed].values,
        mask[lat_mask].values,
    ):

        raise ValueError(
            "Latitude coordinates differ between "
            "ADT and ROMS mask."
        )


    if not np.array_equal(
        adt_reprocessed[lon_reprocessed].values,
        mask[lon_mask].values,
    ):

        raise ValueError(
            "Longitude coordinates differ between "
            "ADT and ROMS mask."
        )


    print("\nSpatial grid check: OK")

    print(
        "  Grid size: "
        f"{adt_reprocessed[lat_reprocessed].size} latitude x "
        f"{adt_reprocessed[lon_reprocessed].size} longitude"
    )


# =============================================================================
# LOAD AND CONCATENATE DAILY ADT
# =============================================================================

def load_daily_adt(mask):
    """
    Load and concatenate the historical/reprocessed and NRT ADT records.

    The order is deliberately:

        reprocessed
        then
        NRT

    The time coordinate is NOT automatically sorted.

    This is intentional. Sorting could hide a bad handoff between the two
    products, such as an overlapping day or reversed records.
    """

    print("\nLoading daily ADT datasets...")

    print("\nReprocessed:")
    print(f"  {REPROCESSED_FILE}")

    print("\nNRT:")
    print(f"  {NRT_FILE}")


    ds_reprocessed = xr.open_dataset(REPROCESSED_FILE)
    ds_nrt = xr.open_dataset(NRT_FILE)


    try:

        # ---------------------------------------------------------------------
        # Required variable / coordinate checks
        # ---------------------------------------------------------------------

        for path, dataset in [
            (REPROCESSED_FILE, ds_reprocessed),
            (NRT_FILE, ds_nrt),
        ]:

            if "adt" not in dataset:

                raise KeyError(
                    f"Variable 'adt' not found in {path}"
                )

            if "time" not in dataset.coords:

                raise KeyError(
                    f"Coordinate 'time' not found in {path}"
                )


        adt_reprocessed = ds_reprocessed["adt"]
        adt_nrt = ds_nrt["adt"]


        # ---------------------------------------------------------------------
        # Both satellite products and the mask must use the same grid.
        # ---------------------------------------------------------------------

        validate_spatial_grid(
            adt_reprocessed,
            adt_nrt,
            mask,
        )


        # ---------------------------------------------------------------------
        # Concatenate.
        #
        # join='exact' prevents xarray from silently constructing a union of
        # spatial coordinates if something unexpected changes upstream.
        # ---------------------------------------------------------------------

        adt_daily = xr.concat(
            [
                adt_reprocessed,
                adt_nrt,
            ],
            dim="time",
            join="exact",
        )


        # =====================================================================
        # CHECK DAILY TIME AXIS
        # =====================================================================

        time_index = pd.DatetimeIndex(
            adt_daily["time"].values
        )


        if len(time_index) < 2:

            raise ValueError(
                "The concatenated time series contains "
                "fewer than two daily records."
            )


        print("\nDaily time-series information")
        print("----------------------------------------")

        print(
            f"Number of daily records : "
            f"{len(time_index)}"
        )

        print(
            f"First day/time          : "
            f"{time_index[0]}"
        )

        print(
            f"Last day/time           : "
            f"{time_index[-1]}"
        )


        # ---------------------------------------------------------------------
        # Exactly preserve the strict daily continuity check from the previous
        # implementation.
        # ---------------------------------------------------------------------

        time_diff = np.diff(
            time_index.values
        )

        expected_step = np.timedelta64(
            1,
            "D",
        )


        strictly_increasing = np.all(
            time_diff > np.timedelta64(0, "ns")
        )

        regular_daily = np.all(
            time_diff == expected_step
        )


        print(
            f"Time strictly increasing       : "
            f"{strictly_increasing}"
        )

        print(
            f"Exactly one day between records: "
            f"{regular_daily}"
        )


        if (
            not strictly_increasing
            or not regular_daily
        ):

            bad = np.where(
                time_diff != expected_step
            )[0]


            print(
                "\nERROR: irregularities found "
                "in daily time axis."
            )

            print(
                f"Number of irregular steps: "
                f"{len(bad)}"
            )


            for k in bad[:20]:

                print(
                    f"  index {k} -> {k + 1}: "
                    f"{time_index[k]} -> "
                    f"{time_index[k + 1]} "
                    f"(delta = "
                    f"{time_index[k + 1] - time_index[k]})"
                )


            raise ValueError(
                "Daily time axis is not continuous with "
                "exactly one-day increments. Monthly "
                "averaging has been stopped so that a "
                "gap or overlap is not hidden."
            )


        print("\nDaily time axis check: OK")


        # =====================================================================
        # MONTHLY MEAN
        #
        # SAME SCIENTIFIC OPERATION AS CURRENT SCRIPT
        # =====================================================================

        print(
            "\nComputing monthly means "
            "from daily ADT..."
        )


        # MS = month-start bins.
        #
        # Each value is the arithmetic mean of the daily ADT values belonging
        # to that calendar month.
        adt_monthly = adt_daily.resample(
            time="MS"
        ).mean(
            dim="time",
            skipna=True,
        )


        # Load before the two original NetCDF files are closed.
        adt_monthly = adt_monthly.load()


    finally:

        ds_reprocessed.close()
        ds_nrt.close()


    return adt_monthly


# =============================================================================
# SCIENTIFIC NGAO / GOADI CALCULATION
# =============================================================================

def compute_indices(adt_monthly, mask):
    """
    Perform the NGAO / GOADI scientific calculation.

    IMPORTANT
    ---------
    This section intentionally preserves the processing order and algorithms
    used by the original implementation.
    """

    # =========================================================================
    # APPLY ROMS MASK
    #
    # SAME APPROACH AS ORIGINAL IMPLEMENTATION
    # =========================================================================

    print("\nApplying ROMS ocean mask...")


    mask_fill = mask.values.astype(float)


    # Original implementation converts land = 0 to NaN and then multiplies
    # ADT by the mask.
    mask_fill[
        mask_fill == 0
    ] = np.nan


    nctime = adt_monthly["time"][:]


    zos = (
        adt_monthly.values
        * mask_fill
    )


    # Preserve the original defensive missing-value treatment.
    zos[
        zos < -100
    ] = np.nan


    print("\nMonthly time-series information")
    print("----------------------------------------")

    print(
        f"Number of monthly records: "
        f"{len(nctime)}"
    )

    print(
        f"First monthly record     : "
        f"{pd.Timestamp(nctime.values[0])}"
    )

    print(
        f"Last monthly record      : "
        f"{pd.Timestamp(nctime.values[-1])}"
    )


    # =========================================================================
    # CONVERT TIME TO YYYY-MM
    #
    # SAME LOGIC AS ORIGINAL IMPLEMENTATION
    # =========================================================================

    date = []


    for i in range(
        len(nctime)
    ):

        date.append(
            str(
                np.array(
                    nctime[i].dt.date
                )
            )[0:7]
        )


    nbmonth = len(date)


    # Grid dimensions are now derived from the new 0.125-degree mask rather
    # than hard-coded as the old 92 x 208 0.25-degree grid.
    ny, nx = mask_fill.shape


    print(
        f"\nProcessing grid size: "
        f"{ny} x {nx}"
    )


    # =========================================================================
    # STEP 1 — QUADRATIC DETRENDING
    #
    # SCIENCE PRESERVED:
    #
    #     statsmodels.tsa.tsatools.detrend(
    #         series,
    #         order=2
    #     )
    #
    # =========================================================================

    print(
        "\nRemoving quadratic trend "
        "at each ocean grid cell..."
    )


    zos_dtrend_quad = np.zeros(
        [
            nbmonth,
            ny,
            nx,
        ]
    )


    for j in range(
        ny
    ):

        for i in range(
            nx
        ):

            if (
                mask_fill[j, i]
                == 1
            ):

                zos_dtrend_quad[
                    :,
                    j,
                    i,
                ] = (
                    statsmodels.tsa.tsatools.detrend(
                        zos[
                            :,
                            j,
                            i,
                        ],
                        order=2,
                    )
                )


    # Preserve original treatment.
    zos_dtrend_quad[
        zos_dtrend_quad > 1e6
    ] = 0


    # =========================================================================
    # STEP 2 — REMOVE SEASONAL COMPONENT
    #
    # SCIENCE PRESERVED:
    #
    #     seasonal_decompose(
    #         np.nan_to_num(...),
    #         model="additive",
    #         period=12
    #     )
    #
    # =========================================================================

    print(
        "\nRemoving seasonal cycle "
        "at each ocean grid cell..."
    )


    zos_dtrend_quad_seasonal = np.zeros(
        [
            nbmonth,
            ny,
            nx,
        ]
    )


    for j in range(
        ny
    ):

        for i in range(
            nx
        ):

            if (
                mask_fill[j, i]
                == 1
            ):

                tmp = seasonal_decompose(
                    np.nan_to_num(
                        zos_dtrend_quad[
                            :,
                            j,
                            i,
                        ]
                    ),
                    model="additive",
                    period=12,
                )


                zos_dtrend_quad_seasonal[
                    :,
                    j,
                    i,
                ] = tmp.seasonal


    # Preserve original treatment.
    zos_dtrend_quad_seasonal[
        zos_dtrend_quad_seasonal < -1e6
    ] = np.nan


    # Subtract seasonal component.
    zos_dtrend_quad_deseasonal = (
        zos_dtrend_quad
        - zos_dtrend_quad_seasonal
    )


    # Preserve original treatment:
    # zeros are interpreted as masked/non-ocean points.
    zos_dtrend_quad_deseasonal[
        zos_dtrend_quad_deseasonal == 0
    ] = np.nan


    # =========================================================================
    # STEP 3 — EOF ANALYSIS
    #
    # SCIENCE PRESERVED:
    #
    #     solver = Eof(...)
    #     pcs(npcs=5, pcscaling=1)
    #
    #     PC1 = NGAO
    #     PC2 = GOADI
    #
    # =========================================================================

    print(
        "\nComputing EOF decomposition..."
    )


    solver = Eof(
        zos_dtrend_quad_deseasonal
    )


    pcs_zeta = solver.pcs(
        npcs=5,
        pcscaling=1,
    )


    variance_fractions = (
        solver.varianceFraction(
            neigs=5
        )
    )


    print("\nEOF variance fractions")
    print("----------------------------------------")

    for mode, fraction in enumerate(
        variance_fractions,
        start=1,
    ):

        print(
            f"EOF {mode}: "
            f"{fraction:.6f} "
            f"({fraction * 100:.2f} %)"
        )


    ngao = pcs_zeta[
        :,
        0,
    ]

    goadi = pcs_zeta[
        :,
        1,
    ]


    return (
        date,
        ngao,
        goadi,
        variance_fractions,
    )


# =============================================================================
# SAVE OUTPUTS
# =============================================================================

def save_outputs(
    date,
    ngao,
    goadi,
    variance_fractions,
):
    """
    Save NGAO, GOADI, dates, and EOF diagnostics in outputs/indices/.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    # =========================================================================
    # CSV PRODUCTS
    # =========================================================================

    ngao_csv = (
        OUTPUT_DIR
        / "NGAO_monthly.csv"
    )


    goadi_csv = (
        OUTPUT_DIR
        / "GOADI_monthly.csv"
    )


    pd.DataFrame(
        {
            "date": date,
            "NGAO": ngao,
        }
    ).to_csv(
        ngao_csv,
        index=False,
    )


    pd.DataFrame(
        {
            "date": date,
            "GOADI": goadi,
        }
    ).to_csv(
        goadi_csv,
        index=False,
    )


    # =========================================================================
    # NUMPY PRODUCTS
    #
    # Retained because the legacy plotting workflow used NumPy arrays.
    # =========================================================================

    np.save(
        OUTPUT_DIR
        / "NGAO_monthly.npy",
        ngao,
    )


    np.save(
        OUTPUT_DIR
        / "GOADI_monthly.npy",
        goadi,
    )


    np.save(
        OUTPUT_DIR
        / "dates_monthly.npy",
        np.asarray(date),
    )


    # =========================================================================
    # EOF DIAGNOSTIC
    # =========================================================================

    pd.DataFrame(
        {
            "EOF_mode": np.arange(
                1,
                len(variance_fractions) + 1,
            ),
            "variance_fraction": variance_fractions,
            "variance_percent": (
                variance_fractions
                * 100
            ),
        }
    ).to_csv(
        OUTPUT_DIR
        / "EOF_variance_fractions.csv",
        index=False,
    )


    print("\nOutputs written to:")
    print(f"  {OUTPUT_DIR}")

    print("\nIndex products:")
    print(
        f"  {ngao_csv.name}"
    )
    print(
        f"  {goadi_csv.name}"
    )


# =============================================================================
# MAIN WORKFLOW
# =============================================================================

def main():
    """
    Run the complete local NGAO / GOADI index calculation.
    """

    print("=" * 72)
    print(
        "NGAO / GOADI INDEX CALCULATION"
    )
    print("=" * 72)


    # -------------------------------------------------------------------------
    # 1. Check input files
    # -------------------------------------------------------------------------

    check_required_files()


    # -------------------------------------------------------------------------
    # 2. Load fixed ROMS mask
    # -------------------------------------------------------------------------

    mask = load_roms_mask()


    # -------------------------------------------------------------------------
    # 3. Load, validate, concatenate, and monthly-average daily ADT
    # -------------------------------------------------------------------------

    adt_monthly = load_daily_adt(
        mask
    )


    # -------------------------------------------------------------------------
    # 4. Perform the original scientific calculation
    # -------------------------------------------------------------------------

    (
        date,
        ngao,
        goadi,
        variance_fractions,
    ) = compute_indices(
        adt_monthly,
        mask,
    )


    # -------------------------------------------------------------------------
    # 5. Save output products
    # -------------------------------------------------------------------------

    save_outputs(
        date,
        ngao,
        goadi,
        variance_fractions,
    )


    print("\n" + "=" * 72)
    print(
        "NGAO / GOADI calculation complete."
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
