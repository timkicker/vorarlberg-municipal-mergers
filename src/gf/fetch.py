"""Download raw sources into data/raw and record them in data/raw/manifest.json.

Every file gets url, retrieval time, size and sha256, so a later run can tell
whether a source changed. Files already present with the recorded checksum are
skipped, `--force` downloads everything again.
"""

import datetime
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

RAW = pathlib.Path(__file__).resolve().parents[2] / "data" / "raw"
UA = "municipal-mergers-research/0.1"

SOURCES = {
    "boundaries_statat_2026.geojson": (
        "https://www.statistik.at/gs-open/GEODATA/ows?service=WFS&version=1.0.0"
        "&request=GetFeature&typeName=GEODATA:STATISTIK_AUSTRIA_GEM_20260101"
        "&outputFormat=application/json&CQL_FILTER=g_id%20LIKE%20%278%25%27"
    ),
    "boundaries_vogis.geojson": (
        "https://vogis.cnv.at/geoserver/ows?service=WFS&version=1.1.0&request=GetFeature"
        "&srsName=EPSG:31254&typeName=vogis:gemeinden&outputFormat=application/json"
        "&maxFeatures=1000000"
    ),
    "vbg_regional_divisions.csv": (
        "https://data.vorarlberg.gv.at/katalog/regionen/"
        "regsta_vbg_gemeinden_regionale_gliederung.csv"
    ),
    "osm/vbg_admin8.json": (
        "https://overpass-api.de/api/interpreter?data="
        "%5Bout%3Ajson%5D%5Btimeout%3A180%5D%3Barea%5B%22ISO3166-2%22%3D%22AT-8%22%5D"
        "%5Badmin_level%3D4%5D-%3E.v%3Brel%28area.v%29%5B%22boundary%22%3D%22administrative%22%5D"
        "%5B%22admin_level%22%3D%228%22%5D%3Bout%20geom%3B"
    ),
    "gemhh_at_2000_2019.csv": "https://data.statistik.gv.at/data/OGD_gem_basis_quer1_GemHH_BQ_1.csv",
    "gemhh_at_header.csv": "https://data.statistik.gv.at/data/OGD_gem_basis_quer1_GemHH_BQ_1_HEADER.csv",
    # Statistics Austria, overnight stays by accommodation type and state since 1973, CC BY 4.0
    "tour_ua_land.csv": "https://data.statistik.gv.at/data/OGD_touextsai_Tour_UA_1.csv",
    "tour_ua_land_header.csv": "https://data.statistik.gv.at/data/OGD_touextsai_Tour_UA_1_HEADER.csv",
    "tour_ua_land_bl.csv": "https://data.statistik.gv.at/data/OGD_touextsai_Tour_UA_1_C-BBTR-0.csv",
    "tour_ua_land_month.csv": "https://data.statistik.gv.at/data/OGD_touextsai_Tour_UA_1_C-SDB_TIT-0.csv",
    "tour_ua_land_w96.csv": "https://data.statistik.gv.at/data/OGD_touextsai_Tour_UA_1_C-W96-0.csv",
    "gemua_at_2016.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_7.csv",
    "gemua_at_2017.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_8.csv",
    "gemua_at_2018.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_9.csv",
    "gemua_at_2019.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_10.csv",
    "gemua_at_header.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_10_HEADER.csv",
    "gemua_at_ua.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_10_C-VAUAB-0.csv",
    "boundaries_statat_at_2018.geojson": (
        "https://www.statistik.at/gs-open/GEODATA/ows?service=WFS&version=1.0.0"
        "&request=GetFeature&typeName=GEODATA:STATISTIK_AUSTRIA_GEM_20180101"
        "&outputFormat=application/json"
    ),
    "gemua_at_2010.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_6.csv",
    "gemua_at_2011.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_5.csv",
    "gemua_at_2012.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_4.csv",
    "gemua_at_2013.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_3.csv",
    "gemua_at_2014.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_2.csv",
    "gemua_at_2015.csv": "https://data.statistik.gv.at/data/OGD_gem_unterabschn_GHD_UA_1.csv",
    "boundaries_statat_at_2014.geojson": (
        "https://www.statistik.at/gs-open/GEODATA/ows?service=WFS&version=1.0.0"
        "&request=GetFeature&typeName=GEODATA:STATISTIK_AUSTRIA_GEM_20140101"
        "&outputFormat=application/json"
    ),
    "boundaries_statat_at_2015.geojson": (
        "https://www.statistik.at/gs-open/GEODATA/ows?service=WFS&version=1.0.0"
        "&request=GetFeature&typeName=GEODATA:STATISTIK_AUSTRIA_GEM_20150101"
        "&outputFormat=application/json"
    ),
    # Austrian address register (BEV), data as of the reference date 01.04.2026, STRASSE.csv and ADRESSE.csv
    "bev_address_register_20260401.zip": "https://data.bev.gv.at/download/Adressregister/Archiv_Adressregister/Adresse_Relationale_Tabellen_Stichtagsdaten_20260401.zip",
    "gv_2025.json": "https://apps.vorarlberg.at/wahlen/data/GV/GV_2025-03-16.json",
    "gv_2020.json": "https://apps.vorarlberg.at/wahlen/data/GV/GV_2020-09-13.json",
    # the state of Vorarlberg, state election 2024 per municipality, same lists everywhere
    "lt_2024.json": "https://apps.vorarlberg.at/wahlen/data/LT/LT_2024-10-13.json",
    "vbg_childcare_facilities.csv": "https://data.vorarlberg.gv.at/katalog/bildung/bilkul_vbg_kth_einrichtungen_adressen.csv",
    # the state of Vorarlberg, schools with school code and GKZ, same catalogue
    "vbg_schools.csv": "https://data.vorarlberg.gv.at/katalog/bildung/bilkul_vbg_schulen_adressen.csv",
    # the state of Vorarlberg, population by type of residence, yearly average, same catalogue
    "vbg_residence_type.csv": "https://data.vorarlberg.gv.at/katalog/bevoelkerung/bevges_vbg_bevoelk_ab_1995_geschlecht_wohnsitzqualitaet_jahresdurchschnitt.csv",
    # Statistics Austria, consumer price index 2015, CC BY 4.0
    "vpi15.csv": "https://data.statistik.gv.at/data/OGD_vpi15_VPI_2015_1.csv",
    # Statistics Austria school atlas, CC BY 4.0, every school as a point (EPSG:3857)
    "schulatlas/s_2019_20.json": ("https://www.statistik.at/gs-open/ATLAS_SCHULE_OPEN/ows?service=WFS&version=2.0.0&request=GetFeature" "&typeNames=ATLAS_SCHULE_OPEN:SCHULEN_2019_20&outputFormat=application/json"),
    "schulatlas/s_2024_25.json": ("https://www.statistik.at/gs-open/ATLAS_SCHULE_OPEN/ows?service=WFS&version=2.0.0&request=GetFeature" "&typeNames=ATLAS_SCHULE_OPEN:SCHULEN_2024_25&outputFormat=application/json"),
    # statistics office of the state of Styria, primary schools per school year since 1923/24 (only read by hand)
    "styria_statistics/ZR1-Volksschulen-25.pdf": "https://www.landesentwicklung.steiermark.at/cms/dokumente/12651299_141979459/c191e977/ZR1-Volksschulen-25.pdf",
    "styria_statistics/Presseinfo_Bildungsplan_2012.pdf": "https://kommunikation.steiermark.at/cms/dokumente/11697670_29767960/1ee5274d/12_Presseinfo_Bildungsplan_10_01_12.pdf",
    # the state of Styria, OGD "municipal council election results Styria", CC BY 4.0
    "styria_council_elections_ogd.zip": "https://service.stmk.gv.at/ogd/OGD_Data_ABT07/wahlen/GRW_2000-2025_endergebnisse.zip",
    "boundaries_statat_at_2025.geojson": (
        "https://www.statistik.at/gs-open/GEODATA/ows?service=WFS&version=1.0.0"
        "&request=GetFeature&typeName=GEODATA:STATISTIK_AUSTRIA_GEM_20250101"
        "&outputFormat=application/json"
    ),
    "boundaries_statat_at_2011.geojson": (
        "https://www.statistik.at/gs-open/GEODATA/ows?service=WFS&version=1.0.0"
        "&request=GetFeature&typeName=GEODATA:STATISTIK_AUSTRIA_GEM_20110101"
        "&outputFormat=application/json"
    ),
    "vbg_projection.csv": "https://data.vorarlberg.gv.at/katalog/bevoelkerung/bevges_vbg_bevoelkerungsprognose.csv",
    "osm_austria_261119.osm.pbf": "https://download.geofabrik.de/europe/austria/austria-261119.osm.pbf",
    "ikz_study_2016.pdf": (
        "https://www.gemeindeverband.at/system/web/getDocument.ashx?cts=1740867694&fileid=1171998&ncd=1"
    ),
    # Statistics Austria, population by municipality on 1 January 2024, CC BY 4.0
    "bevstand_2024.csv": "https://data.statistik.gv.at/data/OGD_bevstandjbab2002_BevStand_2024.csv",
    # the state of Vorarlberg, overnight stays by municipality and month
    "vbg_overnight_stays.csv": (
        "https://data.vorarlberg.gv.at/katalog/wirtschaft/"
        "wirfin_vbg_tour_ankuenfte_naechtigungen_hauptgliederung_monatlich.csv"
    ),
    # the state of Vorarlberg, municipal finance statistics from 2020 (VRV 2015), via data.gv.at dataset 21dcc58e
    "vbg_result_accounts.csv": (
        "https://data.vorarlberg.gv.at/katalog/wirtschaft/wirfin_vbg_ghd_ergebnishaushalt_vrv2015_ab_2020.csv"
    ),
    "vbg_financing_accounts.csv": (
        "https://data.vorarlberg.gv.at/katalog/wirtschaft/wirfin_vbg_ghd_finanzierungshaushalt_vrv2015_ab_2020.csv"
    ),
    "vbg_asset_accounts.csv": (
        "https://data.vorarlberg.gv.at/katalog/wirtschaft/wirfin_vbg_ghd_vermoegenshaushalt_vrv2015_ab_2020.csv"
    ),
    "vbg_loans.csv": (
        "https://data.vorarlberg.gv.at/katalog/wirtschaft/wirfin_vbg_darlehensendstand_gig_leasing_haftungsendstand.csv"
    ),
    "vbg_population_fag.csv": "https://data.vorarlberg.gv.at/katalog/wirtschaft/wirfin_vbg_ghd_bevoelkerung_fag.csv",
    # BMF, federal grant under §§ 25 and 26 FAG 2024 per municipality (structural fund), as of 13.5.2024
    "bmf_fag26_2024.xlsx": (
        "https://www.bmf.gv.at/dam/jcr:c25ff99a-18fb-4072-83a8-fd103b570c4f/"
        "%C2%A7%C2%A7%2025+26%20FAG%202024%20%C3%9Cberweisung%202024.xlsx"
    ),
    # BMF, same sheet for the transfer of 2026, municipal accounts 2024, as of 10.6.2026
    "bmf_fag26_2026.xlsx": (
        "https://www.bmf.gv.at/dam/jcr:fdf2d6f3-8b99-4ad1-a1f9-94a2f2b759d5/"
        "%C2%A7%C2%A7+25+26+FAG+2024+%C3%9Cberweisung+2026.xlsx"
    ),
    # Statistics Austria, population by municipality and age on 1 January 2020, CC BY 4.0
    "bevstand_2020.csv": "https://data.statistik.gv.at/data/OGD_bevstandjbab2002_BevStand_2020.csv",
    "bevstand_2021.csv": "https://data.statistik.gv.at/data/OGD_bevstandjbab2002_BevStand_2021.csv",
    "bevstand_2022.csv": "https://data.statistik.gv.at/data/OGD_bevstandjbab2002_BevStand_2022.csv",
    "bevstand_2023.csv": "https://data.statistik.gv.at/data/OGD_bevstandjbab2002_BevStand_2023.csv",
    # Austrian Association of Municipalities after BMF, advances on municipal tax shares, table of March 2026
    "tax_share_advances_2026_03.pdf": (
        "https://gemeindebund.at/website2024/wp-content/uploads/2026/03/ertragsanteilvorschusse-marz-2026.pdf"
    ),
    # the state of Vorarlberg (VoGIS), building land by zoning plan, updated daily, CC BY 4.0, EPSG 31254
    "vogis_building_land.csv": "https://vogis.cnv.at/geoserver/ows?service=WFS&version=1.1.0&request=GetFeature&srsName=EPSG:31254&typeName=vogis:siedlung_widmung&outputFormat=csv",
    # Vorarlberg fire brigade association (LFV), annual report 2025, key figures per district
    "lfv_annual_report_2025.pdf": "https://www.lfv-vorarlberg.at/images/stories/Aktuelles/2026/Jahresbericht_2025_klein.pdf",
}

COMMUTER_LIST = (
    "https://www.statistik.at/gs-atlas/ATLAS_PENDLER/ows?service=WFS&version=1.0.0"
    "&request=GetFeature&typeName=ATLAS_PENDLER:ATLAS_PENDLER_AUSP_LIST_GEM"
    "&outputFormat=application%2Fjson&viewparams=GKZ:{gkz};DATE:2024-10-31;THRESH_ABS:0"
)

# out-commuters, in-commuters and employed people who work in their own municipality
COMMUTER_INFO = (
    "https://www.statistik.at/gs-atlas/ATLAS_PENDLER/ows?service=WFS&version=1.0.0"
    "&request=GetFeature&typeName=ATLAS_PENDLER:ATLAS_PENDLER_INFO_GEM"
    "&outputFormat=application%2Fjson&viewparams=GKZ:{gkz};DATE:2024-10-31"
)


def get(url: str, tries: int = 5) -> bytes:
    """Download with retries and exponential backoff (Overpass and the WFS answer 502 at times)."""
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            if k == tries - 1:
                raise
            wait = 10 * 2**k
            print(f"  {e}, retry in {wait} s")
            time.sleep(wait)
    raise RuntimeError("unreachable")


# Nextcloud public shares (Environment Agency Austria): the file needs the session cookie and request token of the share page
SHARES = {
    # ÖROK monitoring, building land reserves 2025, CC BY 4.0, GeoPackage in a zip
    "oerok_building_land_2025.zip": ("https://docs.umweltbundesamt.at/s/LiAec6tJ72fjmgA", "Baulandreserven_OGD_2025_v25.zip"),
    "oerok_building_land_2025_info.zip": ("https://docs.umweltbundesamt.at/s/LiAec6tJ72fjmgA", "1_Zusatzinfos.zip"),
}


def get_share(share: str, file: str) -> bytes:
    import http.cookiejar
    import re

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    page = opener.open(urllib.request.Request(share, headers={"User-Agent": UA}), timeout=60).read().decode("utf-8", "replace")
    token = re.search(r'data-requesttoken="([^"]+)"', page).group(1)
    host, key = share.split("/s/")
    req = urllib.request.Request(f"{host}/public.php/dav/files/{key}/{file}",
                                 headers={"User-Agent": UA, "requesttoken": token, "X-Requested-With": "XMLHttpRequest"})
    return opener.open(req, timeout=600).read()


def store(manifest: dict, name: str, url: str, force: bool = False) -> None:
    path = RAW / name
    old = manifest.get(name)
    if not force and old and old.get("url") == url and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == old["sha256"]:
        print(name, "present, skipped")
        return
    body = get_share(*SHARES[name]) if name in SHARES else get(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    manifest[name] = {
        "url": url,
        "retrieved": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    print(name, len(body))


def main(which: list[str]) -> None:
    force = "--force" in which
    which = [w for w in which if w != "--force"]
    mpath = RAW / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    names = which or list(SOURCES) + list(SHARES) + ["commuters", "commuter_info"]
    for name in names:
        if name == "commuters":
            import csv

            rows = csv.DictReader((RAW / "vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";")
            for row in rows:
                store(manifest, f"commuters_2024_raw/ausp_{row['gkz']}.json", COMMUTER_LIST.format(gkz=row["gkz"]), force)
                time.sleep(1)
        elif name == "commuter_info":
            import csv

            rows = csv.DictReader((RAW / "vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";")
            for row in rows:
                store(manifest, f"commuters_2024_raw/info_{row['gkz']}.json", COMMUTER_INFO.format(gkz=row["gkz"]), force)
                time.sleep(1)
        elif name in SHARES:
            store(manifest, name, " ".join(SHARES[name]), force)
        else:
            store(manifest, name, SOURCES[name], force)
        mpath.write_text(json.dumps(manifest, indent=1, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
