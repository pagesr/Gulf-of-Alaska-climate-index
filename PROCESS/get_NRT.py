
################################################################
# Script Name: CMEMS Data Fetcher NGAO Data Processing
# Created On: 12-07-23
# Author: Remi Pages
# Description: This script fetches sea level data from the CMEMS service for the current date.
################################################################

import copernicusmarine as cm
from copernicusmarine import login

login(username='your_username', password='your_password')


cm.subset(
  dataset_id="cmems_obs-sl_glo_phy-ssh_nrt_allsat-l4-duacs-0.25deg_P1D",
  dataset_version="202311",
  force_download= True,
  variables=["adt"],
  minimum_longitude=-178,
  maximum_longitude=-126,
  minimum_latitude=40,
  maximum_latitude=63,
  start_datetime="2024-06-15T00:00:00",
  end_datetime="2024-11-20T00:00:00",
)

