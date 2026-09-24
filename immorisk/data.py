"""Download and load the open data sources.

Sources (all open data, downloaded once into data/raw):

* DVF, every property sale recorded by the tax administration, geolocated
  version published by Etalab (files.data.gouv.fr/geo-dvf), 2021 to 2025.
* Carte des loyers, advertised rents per commune for a reference flat,
  "Estimations ANIL, a partir des donnees du Groupe SeLoger et de leboncoin",
  2022 and 2025 editions.
* LOVAC, vacant private dwellings per commune by length of vacancy (Cerema, DGALN).
* INSEE notaires price indices for existing flats and the rent reference index
  (IRL), quarterly, through the INSEE BDM SDMX service.
* Priority neighbourhoods (QPV 2024 perimeters, ANCT) and ADEME energy
  performance diagnoses (DPE) of flats.
"""

from __future__ import annotations

import json
import shutil
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DVF_YEARS, PROCESSED, RAW

DVF_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/full.csv.gz"

RENT_URLS = {
    (2025, "app12"): "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-144934/pred-app12-mef-dhup.csv",
    (2025, "app3"): "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-144951/pred-app3-mef-dhup.csv",
    (2022, "app12"): "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2022/20221216-154001/pred-app12-mef-dhup.csv",
    (2022, "app3"): "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2022/20221216-154012/pred-app3-mef-dhup.csv",
}

LOVAC_URL = "https://static.data.gouv.fr/resources/logements-vacants-du-parc-prive-par-commune-departement-region-france/20260625-163627/lovac-opendata-communes26.csv"

BDM_URL = "https://api.insee.fr/series/BDM/V1/data/SERIES_BDM/{ids}"

# INSEE notaires indices of existing flats (seasonally adjusted) and the IRL.
INSEE_SERIES = {
    "paris": "010567013",
    "petite_couronne": "010567093",
    "grande_couronne": "010567081",
    "province": "010567063",
    "irl": "001515333",
}

ZONES = ("paris", "petite_couronne", "grande_couronne", "province")

# DVF does not cover Alsace-Moselle (land register) nor Mayotte; the INSEE
# indices cover mainland France only, so overseas departments are left out.
EXCLUDED_DEPARTMENTS = {"57", "67", "68", "971", "972", "973", "974", "976"}


def zone_of(dep: str) -> str:
    if dep == "75":
        return "paris"
    if dep in {"92", "93", "94"}:
        return "petite_couronne"
    if dep in {"77", "78", "91", "95"}:
        return "grande_couronne"
    return "province"


def download(url: str, path: Path, retries: int = 3) -> Path:
    """Download url to path unless it is already there (atomic write)."""
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "immorisk/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, length=1 << 20)
            tmp.replace(path)
            return path
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return path


# ---------------------------------------------------------------- DVF sales

DVF_COLUMNS = [
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere",
    "code_commune", "code_departement", "id_parcelle", "lot1_numero",
    "type_local", "surface_reelle_bati", "nombre_pieces_principales",
    "longitude", "latitude",
]


def clean_flat_sales(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per sale of a single flat, with a usable price per m2.

    DVF has one row per (sale, parcel, premises), the sale price is repeated on
    every row and a flat often comes with a cellar or a parking space. We keep
    plain sales ("Vente") whose premises are exactly one flat plus optional
    outbuildings ("Dependance"): sales of several flats, of a flat with a shop
    or a house, off-plan sales and auctions have prices that cannot be split.
    """
    d = raw[raw["nature_mutation"] == "Vente"]
    d = d[d["type_local"].notna()]
    # the same premises can be repeated (one row per land use); drop repeats
    d = d.drop_duplicates(["id_mutation", "id_parcelle", "lot1_numero", "type_local", "surface_reelle_bati"])
    kinds = pd.DataFrame({
        "id_mutation": d["id_mutation"],
        "n_flat": (d["type_local"] == "Appartement").astype(int),
        "n_other": (~d["type_local"].isin(["Appartement", "Dépendance"])).astype(int),
    }).groupby("id_mutation").sum()
    keep = kinds.index[(kinds["n_flat"] == 1) & (kinds["n_other"] == 0)]
    flats = d[d["id_mutation"].isin(keep) & (d["type_local"] == "Appartement")].copy()

    flats["price"] = pd.to_numeric(flats["valeur_fonciere"], errors="coerce")
    flats["surface"] = pd.to_numeric(flats["surface_reelle_bati"], errors="coerce")
    flats["rooms"] = pd.to_numeric(flats["nombre_pieces_principales"], errors="coerce")
    flats = flats[(flats["surface"] >= 9) & (flats["surface"] <= 250) & (flats["rooms"].between(1, 8))]
    flats = flats[flats["price"] > 0]
    flats["price_m2"] = flats["price"] / flats["surface"]
    # absolute sanity bounds, then trim the tails within each department
    flats = flats[flats["price_m2"].between(300, 30_000)]
    lp = np.log(flats["price_m2"])
    by_dep = lp.groupby(flats["code_departement"])
    flats = flats[(lp >= by_dep.transform("quantile", 0.01)) & (lp <= by_dep.transform("quantile", 0.99))]

    date = pd.to_datetime(flats["date_mutation"])
    out = pd.DataFrame({
        "commune": flats["code_commune"].astype(str).str.zfill(5),
        "dep": flats["code_departement"].astype(str),
        "date": date,
        "quarter": date.dt.year * 10 + date.dt.quarter,
        "price": flats["price"],
        "surface": flats["surface"],
        "rooms": flats["rooms"].astype(int),
        "price_m2": flats["price_m2"],
        "lon": flats["longitude"],
        "lat": flats["latitude"],
    })
    return out[~out["dep"].isin(EXCLUDED_DEPARTMENTS)].reset_index(drop=True)


def load_sales(years=DVF_YEARS, refresh: bool = False) -> pd.DataFrame:
    """Cleaned sales of single flats for the given years (cached as parquet)."""
    frames = []
    for year in years:
        cache = PROCESSED / f"flat_sales_{year}.parquet"
        if cache.exists() and not refresh:
            frames.append(pd.read_parquet(cache))
            continue
        path = download(DVF_URL.format(year=year), RAW / "dvf" / f"dvf_{year}.csv.gz")
        raw = pd.read_csv(
            path, usecols=DVF_COLUMNS, low_memory=False,
            dtype={"code_commune": str, "code_departement": str, "id_mutation": str,
                   "id_parcelle": str, "lot1_numero": str},
        )
        clean = clean_flat_sales(raw)
        cache.parent.mkdir(parents=True, exist_ok=True)
        clean.to_parquet(cache, index=False)
        frames.append(clean)
    sales = pd.concat(frames, ignore_index=True)
    sales["qpv"] = in_priority_area(sales["lon"].to_numpy(), sales["lat"].to_numpy())
    return sales


# -------------------------------------------------------------- rent map

def load_rents(edition: int = 2025, typology: str = "app12") -> pd.DataFrame:
    """Advertised rent per m2 (charges included) with its 95% prediction interval."""
    path = download(RENT_URLS[(edition, typology)], RAW / f"loyers_{edition}_{typology}.csv")
    d = pd.read_csv(path, sep=";", encoding="latin-1", decimal=",", dtype={"INSEE_C": str, "DEP": str})
    d = d.rename(columns={
        "INSEE_C": "commune", "LIBGEO": "name", "DEP": "dep", "loypredm2": "rent_m2",
        "lwr.IPm2": "rent_lo", "upr.IPm2": "rent_hi", "TYPPRED": "rent_level",
        "nbobs_com": "rent_obs", "nbobs_mail": "rent_obs_zone", "R2_adj": "rent_r2",
    })
    d["commune"] = d["commune"].str.zfill(5)
    cols = ["commune", "name", "dep", "rent_m2", "rent_lo", "rent_hi", "rent_level", "rent_obs", "rent_obs_zone", "rent_r2"]
    return d[cols].drop_duplicates("commune").reset_index(drop=True)


# -------------------------------------------------------------- vacancy

def load_vacancy() -> pd.DataFrame:
    """Short-term (frictional) vacancy rate of private housing per commune.

    LOVAC counts private dwellings vacant on 1 January and those vacant for more
    than two years. The difference, over the private stock, is the frictional
    vacancy rate: flats between two tenants or two owners. Small counts are
    masked ("s") for secrecy and come back as missing.
    """
    path = download(LOVAC_URL, RAW / "lovac_communes.csv")
    d = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
    num = lambda c: pd.to_numeric(d[c], errors="coerce")
    out = pd.DataFrame({
        "commune": d["CODGEO_26"].str.zfill(5),
        "vacant": num("pp_vacant_26"),
        "vacant_long": num("pp_vacant_plus_2ans_26"),
        "stock": num("ff_pp_total_25"),
    })
    out["vacancy_short"] = (out["vacant"] - out["vacant_long"]) / out["stock"]
    out["vacancy_total"] = out["vacant"] / out["stock"]
    return out


# -------------------------------------------------------------- priority neighbourhoods

QPV_URL = ("https://opendata.caissedesdepots.fr/api/explore/v2.1/catalog/datasets/"
           "quartiers-prioritaires-de-la-politique-de-la-ville-au-1er-janvier-2024/exports/geojson")


def in_priority_area(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """True for points inside a 2024 priority neighbourhood (quartier prioritaire, QPV).

    QPVs are the areas of concentrated low income targeted by urban policy
    (1,580 perimeters, ANCT, via Caisse des Depots open data).
    """
    import shapely

    path = download(QPV_URL, RAW / "qpv_2024.geojson")
    features = json.loads(path.read_text())["features"]
    polys = [shapely.geometry.shape(f["geometry"]) for f in features if f.get("geometry")]
    tree = shapely.STRtree(polys)
    lon = np.asarray(lon, float)
    lat = np.asarray(lat, float)
    ok = np.isfinite(lon) & np.isfinite(lat)
    points = shapely.points(lon[ok], lat[ok])
    hit = np.zeros(len(points), bool)
    idx_point, _ = tree.query(points, predicate="within")
    hit[idx_point] = True
    out = np.zeros(len(lon), bool)
    out[ok] = hit
    return out


# -------------------------------------------------------------- energy ratings

DPE_URL = ("https://data.ademe.fr/data-fair/api/v1/datasets/meg-83tjwtg8dyz4vv7h1dqe/values_agg"
           "?field=code_insee_ban&agg_size=1000&size=0&qs={qs}")
DPE_GROUPS = {"all": "", "E": " AND etiquette_dpe:E", "F": " AND etiquette_dpe:F", "G": " AND etiquette_dpe:G"}


def _dpe_counts(dep: str) -> list[tuple]:
    rows = []
    for group, extra in DPE_GROUPS.items():
        qs = urllib.request.quote(f"type_batiment:appartement AND code_departement_ban:{dep}{extra}")
        req = urllib.request.Request(DPE_URL.format(qs=qs), headers={"User-Agent": "immorisk/1.0"})
        for attempt in range(4):
            try:
                payload = json.loads(urllib.request.urlopen(req, timeout=120).read())
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
        rows += [(a["value"], group, a["total"]) for a in payload["aggs"]]
    return rows


def load_dpe(departments, refresh: bool = False) -> pd.DataFrame:
    """Energy ratings of flats per commune: counts of all, E, F and G diagnostics.

    ADEME publishes every energy performance diagnosis (DPE) since July 2021;
    the API aggregates them per commune, one query per department and rating.
    F and G rated flats can no longer be let from 2028 and 2025 respectively,
    E rated ones from 2034 (loi Climat et resilience).
    """
    cache = RAW / "dpe_flats_by_commune.csv"
    if refresh or not cache.exists():
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as pool:
            parts = list(pool.map(_dpe_counts, sorted(set(departments))))
        long = pd.DataFrame([r for part in parts for r in part], columns=["commune", "group", "count"])
        wide = long.pivot_table(index="commune", columns="group", values="count", aggfunc="sum", fill_value=0)
        wide = wide.reindex(columns=list(DPE_GROUPS), fill_value=0).reset_index()
        cache.parent.mkdir(parents=True, exist_ok=True)
        wide.to_csv(cache, index=False)
    d = pd.read_csv(cache, dtype={"commune": str})
    d["commune"] = d["commune"].str.zfill(5)
    total = d["all"].replace(0, np.nan)
    return pd.DataFrame({
        "commune": d["commune"], "dpe_count": d["all"],
        "share_E": d["E"] / total, "share_F": d["F"] / total, "share_G": d["G"] / total,
    })


# -------------------------------------------------------------- INSEE series

def _parse_bdm(xml_bytes: bytes) -> pd.DataFrame:
    root = ET.fromstring(xml_bytes)
    rows = []
    for s in root.iter():
        if not s.tag.endswith("Series"):
            continue
        idbank = s.attrib.get("IDBANK")
        for o in s:
            if o.tag.endswith("Obs") and o.attrib.get("OBS_VALUE") not in (None, "", "NaN"):
                rows.append((idbank, o.attrib["TIME_PERIOD"], float(o.attrib["OBS_VALUE"])))
    return pd.DataFrame(rows, columns=["idbank", "period", "value"])


def load_insee(refresh: bool = False) -> pd.DataFrame:
    """Quarterly index levels, one column per series in INSEE_SERIES."""
    cache = RAW / "insee_series.csv"
    if refresh or not cache.exists():
        ids = "+".join(INSEE_SERIES.values())
        req = urllib.request.Request(BDM_URL.format(ids=ids), headers={"User-Agent": "immorisk/1.0"})
        long = _parse_bdm(urllib.request.urlopen(req, timeout=120).read())
        cache.parent.mkdir(parents=True, exist_ok=True)
        long.to_csv(cache, index=False)
    long = pd.read_csv(cache, dtype={"idbank": str})
    names = {v: k for k, v in INSEE_SERIES.items()}
    long["series"] = long["idbank"].map(names)
    wide = long.pivot(index="period", columns="series", values="value").sort_index()
    wide.index = pd.PeriodIndex(wide.index.str.replace("-Q", "Q"), freq="Q")
    return wide[list(INSEE_SERIES)]
