"""
interp_0125_on_025.py

Created On: May 2025
Author: Remi Pages

Description:
 Interp 0,125 on 0.25 grid

Requirements:
-xesmf libraries (e.g., in a conda environment named 'pyroms')
- The grid file is also required.
"""

import numpy as np
#import pyroms
import netCDF4 as netCDF
#import pyroms_toolbox
from regrid_xesmf import regrid_GLBy_JRA

class nctime(object):
    pass  # Empty class, consider removing if not used elsewhere

# Load the destination grid
#dst_grd = pyroms.grid.get_ROMS_grid('NWGOA3')

# Open the forcing dataset
cdf = netCDF.Dataset('NWGOA_grid_3.nc')


# Extract the 'adt' variable and its attributes
src_var = np.array(cdf.variables['mask_rho'][:])


# Assuming you have a function called regrid_GLBy_JRA to regrid your data
dst_varz = regrid_GLBy_JRA(src_var, method='bilinear')
# Replace NaNs in dst_varz with fill value
# Create a new NetCDF file to save the interpolated data
with netCDF.Dataset('mask_roms_on_025.nc', 'w', format='NETCDF4') as save:
    save.createDimension('latitude', 92)
    save.createDimension('longitude', 208)
    
    var = save.createVariable('mask_rho', 'f4', ('latitude', 'longitude'))
    var[:] = dst_varz[:]  # Uncomment when regrid_GLBy_JRA function is available
    

