import xarray as xr
import xesmf

def regrid_GLBy_JRA(fld, method='nearest_s2d'):
    gsource = xr.open_dataset('/Volumes/homes/HauriLab/ROMS_NGOA/NWGOA_grid_3.nc')
    gsource = gsource.rename({'lon_rho': 'lon', 'lat_rho': 'lat'})
    coords = xr.open_dataset('cmems_obs-sl_glo_phy-ssh_nrt_allsat-l4-duacs-0.25deg_P1D_adt_177.88W-126.12W_40.12N-62.88N_2024-06-15-2024-11-20.nc')

    regrid = xesmf.Regridder(
        gsource,
        coords,
        method=method,
        periodic=False,
        filename='regrid_t.nc',
        reuse_weights=False
    )
    tdest = regrid(fld)
    return tdest
