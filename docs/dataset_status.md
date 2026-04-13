# Dataset Status (Local + Git)

This file documents the data sources requested and where they are stored in this repository.

## Canonical local dataset folder

Use this as the single source of truth:

- `data/global_risk/`

Duplicate archive copies under `SAVED DATA/` are intentionally not tracked.

## Source coverage

- Alliances (ATOP): DONE (`data/global_risk/ATOP 5.1 (.csv)/*.csv`)
- Political regime (V-Dem): DONE (`data/global_risk/V-Dem-CY-FullOthers-v15_csv/V-Dem-CY-Full+Others-v15.csv`)
- Leaders (Archigos): DONE (`data/global_risk/Archigos_Leaders.csv`)
- Sanctions (OFAC + GSDB): DONE (`data/global_risk/OFAC_Sanctions.csv`, `data/global_risk/global Sanction db_v4/GSDB_V4.csv`)
- Chokepoints (World Port Index): DONE (`data/global_risk/UpdatedPub150.csv`)
- Diplomatic relations: DONE (covered by ATOP + Lowy index inputs)
- Legality (treaties): DONE (legal memory corpus + registry in code)
- Real war patterns (UCDP GED): DONE (`data/global_risk/ged251-csv/GEDEvent_v25_1.csv`)
- Economic pressure (World Bank): DONE (`data/global_risk/WorldBank_Economy_Data.csv`)
- Military capability (SIPRI): DONE (`data/global_risk/SIPRI/*.csv`)
- Territorial disputes (EEZ): DONE (`data/global_risk/World_EEZ_v12_20231025_LR/*`)

## Notes on real-time feeds

- Real-time tensions (GDELT): live feed via provider/sensor code, not a static bundled CSV.
- Supply chain leverage (Comtrade): provided by provider integration; raw bulk CSV is not currently bundled in this repo snapshot.

## Git tracking policy

- Canonical files in `data/global_risk` are tracked as the single source bundle.
- Very large files are tracked with Git LFS (`Archigos`, `V-Dem`, `UCDP GED`).
