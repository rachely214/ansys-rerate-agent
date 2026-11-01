# The NASA geometry data (downloaded, not committed)

The example impeller is NASA's High Efficiency Centrifugal Compressor. Its published coordinates (NASA/CR-2014-
218114/REV1 supplement, Appendix E.4 "Hot Coordinates", tables C_1 to C_24) are public on NASA's Technical Reports
Server, but they are not stored in this repository.

The setup assistant gets them for you (`scripts/setup/install_runtime.py example-data`). It downloads NASA's supplement
archive (about 4.9 GB, resumes if interrupted) and keeps only the 32 small table files, in
`%LOCALAPPDATA%\ansys-rerate-agent\example-data\01_nasa_hecc\geometry_data\`. The run finds them there
automatically. Source URL, size and the expected files are listed in `data_source.yaml`.

Already have the archive? `python scripts/setup/install_runtime.py example-data --zip <path to the .zip>`.

Manual: open https://ntrs.nasa.gov/citations/20180001472, download the supplement zip, and copy the folder
`AppendixE.4_HotCoordinates` into the folder named above.

The NASA folder contains `README_ExportControlClassification.txt`. Read it before sharing the data with anyone.
