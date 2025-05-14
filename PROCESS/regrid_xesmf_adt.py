import xarray as xr
import xesmf

def regrid_GLBy_JRA(fld, method='nearest_s2d'):
    coords = xr.open_dataset('cmems_obs-sl_glo_phy-ssh_nrt_allsat-l4-duacs-0.25deg_P1D_adt_177.88W-126.12W_40.12N-62.88N_2024-06-15-2024-11-20.nc')
#    coords = coords.rename({'lon_rho': 'lon', 'lat_rho': 'lat'})

    gsource = xr.open_dataset('cmems_obs-sl_glo_phy-ssh_nrt_allsat-l4-duacs-0.125deg_P1D_adt_177.94W-126.06W_40.06N-62.94N_2024-11-21-2025-05-14.nc')

    regrid = xesmf.Regridder(
        gsource,
        coords,
        method=method,
        periodic=False,
        filename='regrid_adt.nc',
        reuse_weights=False
    )
    tdest = regrid(fld)
    return tdest
