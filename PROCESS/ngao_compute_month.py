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

# Load grid and mask
grid_path = 'mask_roms_on_025.nc'
with xr.open_dataset(grid_path) as grid:
    mask_fill = grid['mask_rho'][:].values
    mask_fill[mask_fill[:]==0]=np.nan

# Load data
with xr.open_dataset('adt_full_on_025_monthly.nc') as ds:
    nctime = ds['time'][:]
    zos = ds['adt'].values*mask_fill[:]
    zos[zos[:]<-100]=np.nan

# Convert time to date format
date=[]
t=0
for i in range (len(nctime)):
    date.append(str(np.array(nctime[i].dt.date))[0:7])
    t=t+1
    
nbday=len(date)

# Detrend data
zos_dtrend_quad = np.zeros([nbday, 92, 208])
for j in range(92):
    for i in range(208):
        if mask_fill[j, i] == 1:
            zos_dtrend_quad[:, j, i] = statsmodels.tsa.tsatools.detrend(zos[:, j, i], order=2)
zos_dtrend_quad[zos_dtrend_quad > 1e6] = 0

# Decompose to get seasonal component
zos_dtrend_quad_seasonal = np.zeros([nbday, 92, 208])
for j in range(92):
    for i in range(208):
        if mask_fill[j, i] == 1:
            tmp = seasonal_decompose(np.nan_to_num(zos_dtrend_quad[:, j, i]), model='additive', period=12)
            zos_dtrend_quad_seasonal[:, j, i] = tmp.seasonal

zos_dtrend_quad_seasonal[zos_dtrend_quad_seasonal < -1e6] = np.nan
zos_dtrend_quad_deseasonal = zos_dtrend_quad - zos_dtrend_quad_seasonal
zos_dtrend_quad_deseasonal[zos_dtrend_quad_deseasonal == 0] = np.nan

# EOF analysis
solver = Eof(zos_dtrend_quad_deseasonal)
pcs_zeta = solver.pcs(npcs=5, pcscaling=1)
variance_fractions = solver.varianceFraction(neigs=5)
print(variance_fractions)
np.save('ngao_mon.npy',pcs_zeta[:,0])
np.save('goadi_mon.npy',pcs_zeta[:,1])

# Save to CSV
def save_to_csv(data, label, filename):
    df = pd.DataFrame({'Date': date, label: data})
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath)
np.save('date_mon.npy',date)
save_to_csv(pcs_zeta[:, 0], 'NGAO','NGAO_monthly.csv')
save_to_csv(pcs_zeta[:, 1], 'DW','GOADI_monthly.csv')
