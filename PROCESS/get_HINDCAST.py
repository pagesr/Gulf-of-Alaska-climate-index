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
  dataset_id="c3s_obs-sl_glo_phy-ssh_my_twosat-l4-duacs-0.25deg_P1D",
  dataset_version="202411",
  variables=["adt"],
  minimum_longitude=-178,
  maximum_longitude=-126,
  minimum_latitude=40,
  maximum_latitude=63,
  start_datetime="1993-01-01T00:00:00",
  end_datetime="2024-06-14T00:00:00",
)
