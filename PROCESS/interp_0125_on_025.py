"""
interp_0125_on_025.py

Created On: May 2025
Author: Remi Pages

Description:
 Interp 0,125 on 0.25 grid

Requirements:
- xesmf libraries (e.g., in a conda environment named 'pyroms')
- The grid file is also required.
"""

import numpy as np
#import pyroms
import netCDF4 as netCDF
#import pyroms_toolbox
from regrid_xesmf_adt import regrid_GLBy_JRA

class nctime(object):
    pass  # Empty class, consider removing if not used elsewhere

# Load the destination grid
#dst_grd = pyroms.grid.get_ROMS_grid('NWGOA3')

# Open the forcing dataset
cdf = netCDF.Dataset('cmems_obs-sl_glo_phy-ssh_nrt_allsat-l4-duacs-0.125deg_P1D_adt_177.94W-126.06W_40.06N-62.94N_2024-11-21-2025-05-14.nc')

# Extract the 'adt' variable and its attributes
src_var = np.array(cdf.variables['adt'][:])
src_var[src_var[:]<-10]=np.nan
time = cdf.variables['time'][:]
spval = -2147483647  # Consider using cdf.variables['adt']._FillValue if it's more appropriate

print(f"Time values: {time}")

# Assuming you have a function called regrid_GLBy_JRA to regrid your data
dst_varz = regrid_GLBy_JRA(src_var, method='nearest_s2d')
# Replace NaNs in dst_varz with fill value
dst_varz_clean = np.where(np.isnan(dst_varz), spval, dst_varz)
# Create a new NetCDF file to save the interpolated data
with netCDF.Dataset('adt_from_0125_on_025.nc', 'w', format='NETCDF4') as save:
    save.createDimension('latitude', 92)
    save.createDimension('longitude', 208)
    save.createDimension('time', None)
    
    var = save.createVariable('adt', 'f4', ('time', 'latitude', 'longitude'), fill_value=spval)
    var[:] = dst_varz_clean[:]  # Uncomment when regrid_GLBy_JRA function is available
    
    octime = save.createVariable('time', 'f4', 'time')
    octime[:] = time[:]
    octime.units = 'days since 1950-01-01 00:00:00'

