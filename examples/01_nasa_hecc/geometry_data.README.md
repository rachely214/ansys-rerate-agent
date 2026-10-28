# Getting the NASA HECC geometry data (downloaded, not committed)

The example reads NASA's published impeller coordinates (NASA/CR-2014-218114/REV1 supplement, Appendix E.4
"Hot Coordinates", tables C_1 to C_24). NTRS lists the supplement with distribution PUBLIC. The files are
downloaded from NASA at setup time and never committed (see `docs/RELEASE_CHECKLIST.md`).

Automatic (recommended):

```powershell
.\setup.ps1 -FetchExampleData          # or, later:
.\.venv\Scripts\python.exe scripts\setup\fetch_example_data.py --example 01_nasa_hecc
```

This downloads the supplement archive (about 4.9 GB, resumable if interrupted) into `work/downloads/` and extracts
only `AppendixE.4_HotCoordinates/` (32 small files) to `examples/01_nasa_hecc/geometry_data/`. Source URL, size and
the expected files are in `data_source.yaml`. If you already have the archive:
`fetch_example_data.py --example 01_nasa_hecc --zip <path to the .zip>`.

Manual: open https://ntrs.nasa.gov/citations/20180001472, download the supplement zip, and copy
`AppendixE.4_HotCoordinates` into `examples/01_nasa_hecc/geometry_data/`.

The folder contains `README_ExportControlClassification.txt`; read it before redistributing anything.
`scripts/setup/doctor.py --case examples/01_nasa_hecc/case.yaml` checks that the files are found.
