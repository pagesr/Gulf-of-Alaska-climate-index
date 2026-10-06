"""
Download the ADT data required to compute the NGAO and GOADI indices.

The workflow combines:

1. Copernicus Marine reprocessed 0.125° ADT
2. Copernicus Marine near-real-time (NRT) 0.125° ADT

The end date of the reprocessed product is discovered automatically.
The NRT period starts one day after that date.

Authentication
--------------
Run once before using this script:

    copernicusmarine login

Credentials are then managed by the Copernicus Marine Toolbox and are
not stored in this repository.
"""

from datetime import timedelta
from pathlib import Path
import json

import copernicusmarine
import pandas as pd


# =============================================================================
# Configuration
#
# These values will later move to config/default.toml.
# =============================================================================

PAST_DATASET_ID = (
    "cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D"
)

NRT_DATASET_ID = (
    "cmems_obs-sl_glo_phy-ssh_nrt_allsat-l4-duacs-0.125deg_P1D"
)

VARIABLES = ["adt"]

START_DATETIME_PAST = "1993-01-01T00:00:00"

MIN_LONGITUDE = -175
MAX_LONGITUDE = -120
MIN_LATITUDE = 40
MAX_LATITUDE = 62


# =============================================================================
# Project paths
# =============================================================================

# download.py is:
#
# repo/src/goa_indices/download.py
#
# parents[2] therefore corresponds to the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

PAST_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "reprocessed"
NRT_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "nrt"

PAST_FILE = PAST_DIRECTORY / "adt_reprocessed.nc"
NRT_FILE = NRT_DIRECTORY / "adt_nrt.nc"

PAST_MANIFEST = PAST_DIRECTORY / "manifest.json"


# =============================================================================
# Utilities
# =============================================================================

def get_remote_time_range(dataset_id):
    """
    Return the first and last timestamps currently available in a
    Copernicus Marine dataset.

    open_dataset() uses remote lazy access, so this does not download
    the full dataset.
    """

    print(f"\nChecking remote coverage for:\n  {dataset_id}")

    ds = copernicusmarine.open_dataset(
        dataset_id=dataset_id,
        variables=VARIABLES,
    )

    try:
        start = pd.Timestamp(ds.time.min().values)
        end = pd.Timestamp(ds.time.max().values)
    finally:
        ds.close()

    print(f"  First available date: {start}")
    print(f"  Last available date : {end}")

    return start, end


def get_remote_version(dataset_id):
    """
    Return the currently selected/default Copernicus dataset version.
    """

    catalogue = copernicusmarine.describe(
        dataset_id=dataset_id,
        disable_progress_bar=True,
    )

    dataset = catalogue.products[0].datasets[0]

    # Copernicus returns the default/current version first.
    version = dataset.versions[0].label

    return version


def load_manifest(path):
    """
    Read a download manifest if one exists.
    """

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(path, dataset_id, version, start_date, end_date):
    """
    Save information describing the downloaded dataset.
    """

    manifest = {
        "dataset_id": dataset_id,
        "dataset_version": version,
        "start_datetime": str(start_date),
        "end_datetime": str(end_date),
        "variable": VARIABLES,
        "longitude": [MIN_LONGITUDE, MAX_LONGITUDE],
        "latitude": [MIN_LATITUDE, MAX_LATITUDE],
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


# =============================================================================
# Reprocessed / historical data
# =============================================================================

def download_reprocessed():
    """
    Download the reprocessed ADT record if necessary.

    The file is downloaded again when:

    - it does not exist;
    - no manifest exists;
    - Copernicus has released a new dataset version; or
    - the reprocessed record has been extended.
    """

    PAST_DIRECTORY.mkdir(parents=True, exist_ok=True)

    _, remote_end = get_remote_time_range(PAST_DATASET_ID)

    remote_version = get_remote_version(PAST_DATASET_ID)

    print(f"  Dataset version      : {remote_version}")

    manifest = load_manifest(PAST_MANIFEST)

    needs_download = True

    if PAST_FILE.exists() and manifest is not None:

        local_version = manifest.get("dataset_version")
        local_end = pd.Timestamp(manifest.get("end_datetime"))

        if (
            local_version == remote_version
            and local_end == remote_end
        ):
            needs_download = False

    if not needs_download:
        print("\nReprocessed data are already current.")
        print(f"  {PAST_FILE}")

        return remote_end

    print("\nDownloading reprocessed data...")

    temp_file = PAST_DIRECTORY / "adt_reprocessed_tmp.nc"

    # Remove an incomplete temporary file from a previous failed run.
    if temp_file.exists():
        temp_file.unlink()

    copernicusmarine.subset(
        dataset_id=PAST_DATASET_ID,
        variables=VARIABLES,
        minimum_longitude=MIN_LONGITUDE,
        maximum_longitude=MAX_LONGITUDE,
        minimum_latitude=MIN_LATITUDE,
        maximum_latitude=MAX_LATITUDE,
        start_datetime=START_DATETIME_PAST,
        end_datetime=remote_end.isoformat(),
        output_directory=str(PAST_DIRECTORY),
        output_filename=temp_file.name,
        overwrite=True,
    )

    # Replace the old file only after the new download completed.
    temp_file.replace(PAST_FILE)

    save_manifest(
        PAST_MANIFEST,
        dataset_id=PAST_DATASET_ID,
        version=remote_version,
        start_date=START_DATETIME_PAST,
        end_date=remote_end,
    )

    print("\nReprocessed download complete:")
    print(f"  {PAST_FILE}")

    return remote_end


# =============================================================================
# Near-real-time data
# =============================================================================

def download_nrt(past_end):
    """
    Download the NRT segment.

    NRT starts one day after the final day in the reprocessed dataset.

    The local NRT file is replaced on every run so that it always
    represents the latest available operational data.
    """

    NRT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    remote_nrt_start, remote_nrt_end = get_remote_time_range(
        NRT_DATASET_ID
    )

    requested_start = past_end + timedelta(days=1)

    # Ensure that we never request a date before the NRT dataset exists.
    start_nrt = max(requested_start, remote_nrt_start)

    end_nrt = remote_nrt_end

    print("\nNRT period required:")
    print(f"  Start: {start_nrt}")
    print(f"  End  : {end_nrt}")

    if start_nrt > end_nrt:
        print(
            "\nNo NRT data are required: the reprocessed dataset "
            "already reaches the latest NRT date."
        )

        if NRT_FILE.exists():
            NRT_FILE.unlink()

        return

    temp_file = NRT_DIRECTORY / "adt_nrt_tmp.nc"

    if temp_file.exists():
        temp_file.unlink()

    print("\nDownloading NRT data...")

    copernicusmarine.subset(
        dataset_id=NRT_DATASET_ID,
        variables=VARIABLES,
        minimum_longitude=MIN_LONGITUDE,
        maximum_longitude=MAX_LONGITUDE,
        minimum_latitude=MIN_LATITUDE,
        maximum_latitude=MAX_LATITUDE,
        start_datetime=start_nrt.isoformat(),
        end_datetime=end_nrt.isoformat(),
        output_directory=str(NRT_DIRECTORY),
        output_filename=temp_file.name,
        overwrite=True,
    )

    # Atomic-ish replacement: keep the previous valid NRT file until the
    # new download has successfully completed.
    temp_file.replace(NRT_FILE)

    print("\nNRT download complete:")
    print(f"  {NRT_FILE}")


# =============================================================================
# Main workflow
# =============================================================================

def main():

    print("=" * 70)
    print("NGAO / GOADI Copernicus data download")
    print("=" * 70)

    past_end = download_reprocessed()

    download_nrt(past_end)

    print("\nDownload stage complete.")


if __name__ == "__main__":
    main()
