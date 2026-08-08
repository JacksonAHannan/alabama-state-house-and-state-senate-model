Alabama House of Representatives district boundaries from 10/05/12 to 05/19/17 (shapefile)

##Redistricting Data Hub (RDH) Retrieval Date
01/20/21

##Sources
Special thanks to Professor Justin Levitt, founder of All About Redistricting (https://redistricting.lls.edu/) who compiled current and previous legislative boundaries, currently hosted on the AAR website, and shared his sources with the RDH to support our data collection efforts.
Alabama House of Representative district boundaries for 10/05/12 to 05/19/17 were retrieved from https://www2.census.gov/geo/tiger/TIGER2014/SLDL/tl_2014_01_sldl.zip

##Processing
The Alabama House of Representatives district boundaries were retrieved with a python script. 
The shapefiles were unzipped and uploaded to python and renamed with RDH conventions and zipped into a folder with supporting geospatial files and this README. 
Processing was primarily completed using the pandas and geopandas libraries.

##Additional Notes
For more information on the data see the AAR page at: https://redistricting.lls.edu/state/alabama
Please direct questions related to processing this dataset to info@redistrictingdatahub.org