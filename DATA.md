# Data

Apart from four small tables named below, the raw data are not part of this repository. `make data` runs `src/gf/fetch.py`, which downloads them into `data/raw/` and writes `data/raw/manifest.json` with the URL, time of download, size and SHA-256 of every file. Sources change, so a later download can differ from the one behind the paper. A few inputs cannot be downloaded by script and have to be placed in `data/raw/` by hand (see below). `make results` then writes everything into `data/derived/` and runs the tests. A step whose inputs placed by hand are missing prints a note and leaves the file from the repository in `data/derived/`. The result files as used for the paper are in the repository, so they can be read and compared without running anything. Left out are the list of first names (see below) and the tables built from the cooperation study of 2016. The licence of the study is not stated and `make results` builds these tables again from the downloaded PDF.

## Sources and licences

| Source | Files in `data/raw/` | Licence |
|---|---|---|
| Statistics Austria, open data: municipal finances by sub-section 2010 to 2019, basic municipal budget data 2000 to 2019, population at 1 January, tourism, consumer price index 2015 | `gemua_at_*.csv`, `gemhh_at_*.csv`, `bevstand_*.csv`, `tour_ua_land*.csv`, `vpi15.csv` | CC BY 4.0, "Datenquelle: Statistik Austria - data.statistik.gv.at" |
| Statistics Austria, gs-open WFS: municipal boundaries and population centres, school atlas 2019/20 and 2024/25 | `boundaries_statat_*.geojson`, `schulatlas/` | CC BY 4.0, as above |
| Statistics Austria, commuter atlas, reference date 31.10.2024 | `commuters_2024_raw/` | © STATISTIK AUSTRIA, copying and passing on allowed with the source "STATISTIK AUSTRIA" and a note that the data were processed |
| State of Vorarlberg, data.vorarlberg.gv.at and VoGIS: boundaries, regional divisions, population projection, residences by type, overnight stays, childcare facilities, schools, municipal accounts (results, financing, assets, loans), population for the fiscal equalisation, building land | `boundaries_vogis.geojson`, `vbg_regional_divisions.csv`, `vbg_projection.csv`, `vbg_*.csv`, `vbg_overnight_stays.csv`, `vbg_childcare_facilities.csv`, `vbg_schools.csv`, `vogis_building_land.csv` | CC BY 4.0 |
| State of Vorarlberg, election website: municipal elections 2020 and 2025, state election 2024 | `gv_*.json`, `lt_2024.json` | no licence stated, only aggregates are used |
| State of Styria, open data: municipal council elections 2000 to 2025 | `styria_council_elections_ogd.zip` | CC BY 4.0, "Datenquelle: CC-BY-4.0: Land Steiermark - data.steiermark.gv.at" |
| Federal Ministry of Finance: fiscal equalisation per municipality (FAG § 26) 2024 and 2026, advance payments March 2026 (the advance payments read by hand, not by a script) | `bmf_fag26_*.xlsx`, `tax_share_advances_2026_03.pdf` | public documents, no licence stated |
| BEV, Austrian address register, reference date 1 April 2026 | `bev_address_register_20260401.zip` | free of charge, with the note "© Österreichisches Adressregister" |
| ÖROK, building land reserves 2025 | `oerok_building_land_2025*.zip` | CC BY 4.0 |
| Landesfeuerwehrverband Vorarlberg, annual report 2025 | `lfv_annual_report_2025.pdf` | no licence stated, only counts are used |
| OpenStreetMap, extract of Austria by Geofabrik and administrative boundaries of Vorarlberg via Overpass | `osm_austria_*.osm.pbf`, `osm/` | ODbL 1.0, © OpenStreetMap contributors |
| EU-DEM 25 m via opentopodata.org: altitude of the population centres (placed by hand, see below) | `altitude_municipalities_2020.csv` | Copernicus data, free and open use with the source named |
| Statistical office of the State of Styria: primary schools per school year, press release on the education plan 2012 (read by hand, not by a script) | `styria_statistics/*.pdf` | public documents, no licence stated |
| Bußjäger, Hornsteiner and Keuschnigg (2016), Interkommunale Zusammenarbeit in Vorarlberg, PDF on the website of the Vorarlberger Gemeindeverband | `ikz_study_2016.pdf` | no licence stated |

## Inputs placed by hand

These files are read by the scripts but cannot be fetched by a plain download. Four small tables that were typed or looked up by hand are in the repository under `data/raw/`, because they hold only facts from public documents or open data: `altitude_municipalities_2020.csv`, `grants_by_municipality_29_01_017.csv`, `hospital_contributions_2022_29_01_160.csv` and `vbg_court_districts.csv`. The others have to be fetched as described.

- `altitude_municipalities_2020.csv`: altitude of each municipality's population centre, the centres taken from the Statistics Austria WFS and their altitude looked up in EU-DEM 25 m through the opentopodata.org API.
- `offenerhaushalt/` and `offenerhaushalt_styria/`: closed accounts by budget item, 2020 to 2024, exported one file per municipality and year from offenerhaushalt.at (KDZ), on the download page of each municipality (`https://www.offenerhaushalt.at/gemeinde/NAME/downloads`): closed account, financing budget, file names kept as offered (`offenerhaushalt_CODE_YEAR_ra_fhh_gemeinde.csv` for Vorarlberg, where the municipalities publish themselves, `..._ra_fhh_statistik_at.csv` for Styria, from Statistics Austria). 88 of the 96 Vorarlberg municipalities publish there. For 65 Styrian municipalities the site refuses access. The site puts its downloads under CC BY 4.0 (KDZ, offenerhaushalt.at). The raw files are not part of this repository, the results built from them are.
- `gtfs/`: timetables in GTFS. The bus timetable of the Verkehrsverbund Vorarlberg is the sample data set of mobilitydata.gv.at (`https://mobilitydata.gv.at/daten/soll-fahrplandaten-gtfs`, state of 3 July 2026, Mobilitätsverbünde Österreich OG, licence agreement DBP v1.1, free of charge, saved as `vmobil_gtfs_20260703.zip`), the rail timetable is ÖBB GTFS 2026 from data.oebb.at (CC BY 4.0, saved as `oebb_gtfs_2026.zip`).
- `grants_by_municipality_29_01_017.csv`: grants to each municipality 2020 to 2024, typed from the answer to the state parliament question 29.01.017 (question 15, pages 17 to 19 of the PDF on suche.vorarlberg.at). The 2024 total matches the state's statement of accounts for 2024.
- `hospital_contributions_2022_29_01_160.csv`: hospital contributions 2022, extracted from the answer to the state parliament question 29.01.160 (question 18, pages 12 to 16).
- `landtag_29_01_322_childcare_2022.pdf`: answer to the state parliament question 29.01.322 with every childcare facility.
- `zag_2026.ods` and `zag_2027.ods`: the state's list of municipalities with their category under the second home levy act (ZWAbgG), for the levy years 2026 and 2027, downloaded from `https://vorarlberg.at/-/zweitwohnungen`.
- `vbg_court_districts.csv`: the 96 municipalities by court district, typed from the ordinance BGBl. Nr. 33/1971 as amended by BGBl. II Nr. 383/2016 (RIS).

`src/gf/mayors.py` also reads a list of the mayors' first names (`data/derived/first_names.csv`), from which it counts the share of women. The list holds personal data and is not published, so this one share cannot be recomputed from the repository. Without the list the script still runs and reports every candidate's sex as unclear.

## What the scripts write

Each script in `src/gf/` prints its results and writes them as text to `data/derived/`, mostly under its own name. `adjacency.py`, `commuters.py` and `coop2016.py` write only the tables listed below. These write under another name: `costs.py` to `cost_function.txt`, `grant_clawback.py` to `residual_items.txt`, `organs_styria_check.py` to `organs_styria.txt`, `pop2050.py` to `population_2050.txt`, `regions.py` to `regions_robustness.txt`, `roads.py` to `travel_time.txt` and `styria_gross_no14.py` to `styria_gross_no2014.txt`. `balance_2024.py --low` writes `balance_2024_low.txt` and `savings_2024.py` adds `savings_2024_office_top.txt`. In the outputs the state's own divisions are labelled official planning region, official region and official district, while the paper calls them planning regions, regions and districts. The Makefile runs them in an order in which every input exists. Some scripts also write tables, most of which later steps read:

| Script | Tables |
|---|---|
| `adjacency.py` | `neighbours.csv`, the pairs of municipalities that share a border |
| `costs.py` | `administration_2016_2019.csv` (core administration per municipality), `cost_curve_net.csv`, `cost_curve_gross.csv` |
| `commuters.py` | `commuters_2024.csv`, `commuters_2024_municipalities.csv` |
| `coop2016.py` | `coop2016.json`, `coop2016_members.csv`, `coop2016_corrections.csv` |
| `regions.py` | `intramax_regions.csv`, `intramax_steps.csv` |
| `pareto.py` | `pareto_partitions.csv` (the partitions used in the paper), `pareto_candidates.csv` |
| `roads.py` | `travel_time_seat.csv`, travel times by road to the seat of each unit and `pareto_candidates.csv` again with the travel times added |
| `fag.py` | `fag_units.csv`, the merged units of every partition with their population |
| `profiles.py`, `services.py` | `profiles.csv`, `services.csv` |
| `figures.py`, `maps.py`, `figure_money.py` | the data behind the figures, in `data/derived/figures/` |

`services.py` and `roads.py` keep what they extract from OpenStreetMap in `data/raw/osm/services_vbg.json` and `data/raw/osm_vbg_roads.npz`, so later runs skip that step.

`src/gf/osm_check.py` is not part of `make results`. It compares `neighbours.csv` with the OpenStreetMap boundaries and writes `osm_check.txt`.

`data/derived/commuters_2024.csv`, `commuters_2024_municipalities.csv` and the results built from them (`intramax_regions.csv`, `intramax_steps.csv`, `regions_robustness.txt`, `cross_border.txt`, `cuts_outside.txt`) rest on the commuter atlas. Quelle: STATISTIK AUSTRIA, processed (only the 96 Vorarlberg municipalities, columns renamed).

`data/derived/travel_time_seat.csv` is derived from OpenStreetMap and falls under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
