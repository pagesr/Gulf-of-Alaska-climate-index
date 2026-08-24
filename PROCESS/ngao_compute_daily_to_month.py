import numpy as np
import xarray as xr
import statsmodels.tsa.tsatools
from statsmodels.tsa.seasonal import seasonal_decompose
from eofs.standard import Eof
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# Input files
# ============================================================================
# First part of the DAILY ADT time series
adt_file_1 = (
    'c3s_obs-sl_glo_phy-ssh_my_twosat-l4-duacs-0.25deg_P1D_adt_'
    '177.88W-126.12W_40.12N-62.88N_1993-01-01-2025-05-01.nc'
)

# Second part of the DAILY ADT time series
adt_file_2 = 'adt_from_0125_on_025.nc'

# Grid/mask used in the original script
grid_path = 'mask_roms_on_025.nc'


# ============================================================================
# Load grid and mask -- SAME AS ORIGINAL SCRIPT
# ============================================================================
with xr.open_dataset(grid_path) as grid:
    mask_fill = grid['mask_rho'][:].values
    mask_fill[mask_fill[:] == 0] = np.nan


# ============================================================================
# Load and concatenate the two DAILY ADT files
# ============================================================================
print('\nLoading daily ADT files...')
print(f'  Part 1: {adt_file_1}')
print(f'  Part 2: {adt_file_2}')

# Keep the files in the requested chronological order.  We deliberately do
# NOT sort the time axis here, because sorting could hide an overlap or an
# ordering problem at the boundary between the two files.
ds1 = xr.open_dataset(adt_file_1)
ds2 = xr.open_dataset(adt_file_2)

try:
    if 'adt' not in ds1:
        raise KeyError(f"Variable 'adt' not found in {adt_file_1}")
    if 'adt' not in ds2:
        raise KeyError(f"Variable 'adt' not found in {adt_file_2}")
    if 'time' not in ds1.coords:
        raise KeyError(f"Coordinate 'time' not found in {adt_file_1}")
    if 'time' not in ds2.coords:
        raise KeyError(f"Coordinate 'time' not found in {adt_file_2}")

    adt_daily = xr.concat([ds1['adt'], ds2['adt']], dim='time')

    # ========================================================================
    # Check the DAILY time axis
    # ========================================================================
    time_index = pd.DatetimeIndex(adt_daily['time'].values)

    if len(time_index) < 2:
        raise ValueError('The concatenated time series contains fewer than 2 time records.')

    print('\nDaily time-series information')
    print('-----------------------------')
    print(f'Number of daily records : {len(time_index)}')
    print(f'First day/time          : {time_index[0]}')
    print(f'Last day/time           : {time_index[-1]}')

    # Difference between consecutive records.  For a normal daily series every
    # difference must be exactly one day.  This catches duplicates, overlaps,
    # reversed records, and missing days.
    time_diff = np.diff(time_index.values)
    expected_step = np.timedelta64(1, 'D')

    strictly_increasing = np.all(time_diff > np.timedelta64(0, 'ns'))
    regular_daily = np.all(time_diff == expected_step)

    print(f'Time strictly increasing: {strictly_increasing}')
    print(f'Exactly 1 day between all consecutive records: {regular_daily}')

    if not strictly_increasing or not regular_daily:
        bad = np.where(time_diff != expected_step)[0]

        print('\nERROR: irregularities found in the daily time axis.')
        print(f'Number of irregular time steps: {len(bad)}')
        print('First irregular steps:')
        for k in bad[:20]:
            print(
                f'  index {k} -> {k + 1}: '
                f'{time_index[k]}  ->  {time_index[k + 1]}  '
                f'(delta = {time_index[k + 1] - time_index[k]})'
            )

        raise ValueError(
            'Daily time axis is not continuous with exactly one-day increments. '
            'Monthly averaging has been stopped so that a gap/overlap is not hidden.'
        )

    print('Daily time axis check: OK')

    # ========================================================================
    # Compute MONTHLY MEAN from the daily ADT data in Python
    # ========================================================================
    # MS = month-start bins.  Each output value is the arithmetic mean of all
    # daily ADT records belonging to that calendar month.
    print('\nComputing monthly means from daily ADT with xarray...')
    adt_monthly = adt_daily.resample(time='MS').mean(dim='time', skipna=True)

    # Load the monthly result while the source NetCDF files are still open.
    adt_monthly = adt_monthly.load()

finally:
    ds1.close()
    ds2.close()


# ============================================================================
# From here onward, use the SAME processing method as the original script
# ============================================================================
nctime = adt_monthly['time'][:]
zos = adt_monthly.values * mask_fill[:]
zos[zos[:] < -100] = np.nan

print('\nMonthly time-series information')
print('-------------------------------')
print(f'Number of monthly records: {len(nctime)}')
print(f'First monthly record     : {pd.Timestamp(nctime.values[0])}')
print(f'Last monthly record      : {pd.Timestamp(nctime.values[-1])}')

# Convert time to date format
# SAME AS ORIGINAL SCRIPT
date = []
t = 0
for i in range(len(nctime)):
    date.append(str(np.array(nctime[i].dt.date))[0:7])
    t = t + 1

nbday = len(date)

# Detrend data
# SAME AS ORIGINAL SCRIPT
zos_dtrend_quad = np.zeros([nbday, 92, 208])
for j in range(92):
    for i in range(208):
        if mask_fill[j, i] == 1:
            zos_dtrend_quad[:, j, i] = statsmodels.tsa.tsatools.detrend(zos[:, j, i], order=2)
zos_dtrend_quad[zos_dtrend_quad > 1e6] = 0

# Decompose to get seasonal component
# SAME AS ORIGINAL SCRIPT
zos_dtrend_quad_seasonal = np.zeros([nbday, 92, 208])
for j in range(92):
    for i in range(208):
        if mask_fill[j, i] == 1:
            tmp = seasonal_decompose(
                np.nan_to_num(zos_dtrend_quad[:, j, i]),
                model='additive',
                period=12
            )
            zos_dtrend_quad_seasonal[:, j, i] = tmp.seasonal

zos_dtrend_quad_seasonal[zos_dtrend_quad_seasonal < -1e6] = np.nan
zos_dtrend_quad_deseasonal = zos_dtrend_quad - zos_dtrend_quad_seasonal
zos_dtrend_quad_deseasonal[zos_dtrend_quad_deseasonal == 0] = np.nan

# EOF analysis
# SAME AS ORIGINAL SCRIPT
solver = Eof(zos_dtrend_quad_deseasonal)
pcs_zeta = solver.pcs(npcs=5, pcscaling=1)
variance_fractions = solver.varianceFraction(neigs=5)
print('\nEOF variance fractions:')
print(variance_fractions)
np.save('ngao_mon.npy', pcs_zeta[:, 0])
np.save('goadi_mon.npy', pcs_zeta[:, 1])

# Save to CSV
# SAME AS ORIGINAL SCRIPT
def save_to_csv(data, label, filename):
    df = pd.DataFrame({'Date': date, label: data})
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath)


np.save('date_mon.npy', date)
save_to_csv(pcs_zeta[:, 0], 'NGAO', '../INDEX/NGAO_monthly.csv')
save_to_csv(pcs_zeta[:, 1], 'DW', '../INDEX/GOADI_monthly.csv')
