"""
Build the fixed ROMS ocean mask on the Copernicus 0.125-degree grid.

This is a reference-data preparation step and does not need to run during
normal NGAO/GOADI updates.

Output
------
data/reference/masks/roms_ocean_mask_0125.nc

Variables
---------
roms_ocean_mask:
    1 = ROMS ocean
    0 = ROMS land or outside the ROMS domain

roms_domain_mask:
    1 = inside the ROMS grid footprint
    0 = outside the ROMS grid footprint
"""

from pathlib import Path

import numpy as np
import xarray as xr
import xesmf as xe


# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ROMS_GRID_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "roms"
    / "NWGOA_grid_3.nc"
)

# We use an actual Copernicus file to define the target grid.
# This guarantees that our mask coordinates match the downloaded ADT exactly.
COPERNICUS_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "reprocessed"
    / "adt_reprocessed.nc"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "masks"
    / "roms_ocean_mask_0125.nc"
)


# =============================================================================
# Read ROMS grid
# =============================================================================

print("Reading ROMS grid:")
print(f"  {ROMS_GRID_FILE}")

with xr.open_dataset(ROMS_GRID_FILE) as ds_roms:

    lon_roms = ds_roms["lon_rho"].load()
    lat_roms = ds_roms["lat_rho"].load()
    mask_roms = ds_roms["mask_rho"].load()


# Make absolutely sure the original mask is binary.
unique_values = np.unique(mask_roms.values)

print(f"ROMS mask values: {unique_values}")

if not np.all(np.isin(unique_values, [0, 1])):
    raise ValueError(
        "ROMS mask_rho contains values other than 0 and 1."
    )


# =============================================================================
# Build xESMF source grid
# =============================================================================

source_grid = xr.Dataset(
    coords={
        "lon": (
            ("eta_rho", "xi_rho"),
            lon_roms.values,
        ),
        "lat": (
            ("eta_rho", "xi_rho"),
            lat_roms.values,
        ),
    }
)

source_mask = xr.DataArray(
    mask_roms.values,
    dims=("eta_rho", "xi_rho"),
    name="roms_ocean_mask",
)


# =============================================================================
# Read the EXACT Copernicus target grid
# =============================================================================

print("\nReading Copernicus target grid:")
print(f"  {COPERNICUS_FILE}")

with xr.open_dataset(COPERNICUS_FILE) as ds_target:

    # Handle either Copernicus naming convention if needed.
    if "longitude" in ds_target.coords:
        lon_target = ds_target["longitude"].load()
    elif "lon" in ds_target.coords:
        lon_target = ds_target["lon"].load()
    else:
        raise KeyError(
            "Could not find longitude coordinate in Copernicus file."
        )

    if "latitude" in ds_target.coords:
        lat_target = ds_target["latitude"].load()
    elif "lat" in ds_target.coords:
        lat_target = ds_target["lat"].load()
    else:
        raise KeyError(
            "Could not find latitude coordinate in Copernicus file."
        )


print(
    f"Target grid: "
    f"{lat_target.size} latitude x "
    f"{lon_target.size} longitude"
)


# =============================================================================
# Build xESMF destination grid
# =============================================================================

target_grid = xr.Dataset(
    coords={
        "lon": ("longitude", lon_target.values),
        "lat": ("latitude", lat_target.values),
    }
)


# =============================================================================
# 1. Regrid the binary ROMS mask with nearest neighbor
# =============================================================================

print("\nRegridding ROMS land/ocean classification...")

nearest_regridder = xe.Regridder(
    source_grid,
    target_grid,
    method="nearest_s2d",
    periodic=False,
)

mask_nearest = nearest_regridder(source_mask)


# =============================================================================
# 2. Determine which target cells are genuinely inside the ROMS domain
#
# nearest_s2d can extrapolate beyond a regional source grid.
# We therefore independently calculate the ROMS grid footprint.
# =============================================================================

print("Determining ROMS domain footprint...")

source_ones = xr.DataArray(
    np.ones_like(mask_roms.values, dtype=np.float32),
    dims=("eta_rho", "xi_rho"),
)

coverage_regridder = xe.Regridder(
    source_grid,
    target_grid,
    method="bilinear",
    periodic=False,
    unmapped_to_nan=True,
)

coverage = coverage_regridder(source_ones)


# Valid bilinear mappings indicate target cells that belong to the
# ROMS grid footprint.
domain_mask = xr.where(
    np.isfinite(coverage),
    1,
    0,
).astype(np.int8)


# =============================================================================
# 3. Construct final binary ocean mask
# =============================================================================

ocean_mask = xr.where(
    (domain_mask == 1) & (mask_nearest >= 0.5),
    1,
    0,
).astype(np.int8)


# =============================================================================
# Validation
# =============================================================================

ocean_values = np.unique(ocean_mask.values)
domain_values = np.unique(domain_mask.values)

print("\nValidation")
print("----------")
print(f"Ocean mask values : {ocean_values}")
print(f"Domain mask values: {domain_values}")

if not np.all(np.isin(ocean_values, [0, 1])):
    raise ValueError("Final ocean mask is not binary.")

if not np.all(np.isin(domain_values, [0, 1])):
    raise ValueError("Final domain mask is not binary.")


n_ocean = int(ocean_mask.sum())
n_domain = int(domain_mask.sum())

print(f"ROMS-domain target cells: {n_domain}")
print(f"ROMS-ocean target cells : {n_ocean}")


# =============================================================================
# Construct output dataset
# =============================================================================

output = xr.Dataset(
    data_vars={
        "roms_ocean_mask": (
            ("latitude", "longitude"),
            ocean_mask.values,
            {
                "long_name": (
                    "ROMS ocean mask interpolated onto "
                    "Copernicus 0.125 degree grid"
                ),
                "flag_values": np.array([0, 1], dtype=np.int8),
                "flag_meanings": "land_or_outside_roms ocean",
            },
        ),
        "roms_domain_mask": (
            ("latitude", "longitude"),
            domain_mask.values,
            {
                "long_name": "ROMS model domain footprint",
                "flag_values": np.array([0, 1], dtype=np.int8),
                "flag_meanings": "outside inside",
            },
        ),
    },
    coords={
        "latitude": (
            "latitude",
            lat_target.values,
            {
                "standard_name": "latitude",
                "units": "degrees_north",
            },
        ),
        "longitude": (
            "longitude",
            lon_target.values,
            {
                "standard_name": "longitude",
                "units": "degrees_east",
            },
        ),
    },
    attrs={
        "title": "ROMS NWGOA ocean mask on Copernicus 0.125 degree grid",
        "source_grid": "NWGOA_grid_3.nc",
        "source_mask": "mask_rho",
        "mask_regridding_method": "nearest_s2d",
        "domain_detection_method": "bilinear coverage",
        "description": (
            "Fixed mask used to restrict NGAO/GOADI calculations "
            "to the ROMS NWGOA model ocean domain."
        ),
    },
)


# =============================================================================
# Save
# =============================================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True,
)

output.to_netcdf(OUTPUT_FILE)

print("\nMask written successfully:")
print(f"  {OUTPUT_FILE}")
