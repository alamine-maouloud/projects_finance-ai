import numpy as np
import pandas as pd
import pytest

from immorisk import data
from immorisk.config import RAW


def dvf_rows(rows):
    base = {c: None for c in data.DVF_COLUMNS}
    base.update({"nature_mutation": "Vente", "code_departement": "69", "code_commune": "69383",
                 "date_mutation": "2025-03-01", "longitude": 4.85, "latitude": 45.76})
    return pd.DataFrame([{**base, **r} for r in rows])


def test_clean_keeps_single_flats_and_drops_bundles():
    raw = dvf_rows([
        # a flat with its cellar: kept, the cellar dropped
        {"id_mutation": "1", "valeur_fonciere": 200_000, "id_parcelle": "p1", "lot1_numero": "10",
         "type_local": "Appartement", "surface_reelle_bati": 40, "nombre_pieces_principales": 2},
        {"id_mutation": "1", "valeur_fonciere": 200_000, "id_parcelle": "p1", "lot1_numero": "11",
         "type_local": "Dépendance", "surface_reelle_bati": None, "nombre_pieces_principales": 0},
        # the same flat repeated on a second row (one row per land use): counted once
        {"id_mutation": "1", "valeur_fonciere": 200_000, "id_parcelle": "p1", "lot1_numero": "10",
         "type_local": "Appartement", "surface_reelle_bati": 40, "nombre_pieces_principales": 2},
        # two flats sold together: price cannot be split, dropped
        {"id_mutation": "2", "valeur_fonciere": 300_000, "id_parcelle": "p2", "lot1_numero": "1",
         "type_local": "Appartement", "surface_reelle_bati": 30, "nombre_pieces_principales": 1},
        {"id_mutation": "2", "valeur_fonciere": 300_000, "id_parcelle": "p2", "lot1_numero": "2",
         "type_local": "Appartement", "surface_reelle_bati": 35, "nombre_pieces_principales": 2},
        # a flat with a shop: dropped
        {"id_mutation": "3", "valeur_fonciere": 250_000, "id_parcelle": "p3", "lot1_numero": "1",
         "type_local": "Appartement", "surface_reelle_bati": 50, "nombre_pieces_principales": 2},
        {"id_mutation": "3", "valeur_fonciere": 250_000, "id_parcelle": "p3", "lot1_numero": "2",
         "type_local": "Local industriel. commercial ou assimilé", "surface_reelle_bati": 60, "nombre_pieces_principales": 0},
        # an off-plan sale: dropped
        {"id_mutation": "4", "nature_mutation": "Vente en l'état futur d'achèvement", "valeur_fonciere": 250_000,
         "id_parcelle": "p4", "lot1_numero": "1", "type_local": "Appartement", "surface_reelle_bati": 50, "nombre_pieces_principales": 2},
        # a 5 m2 "flat": dropped
        {"id_mutation": "5", "valeur_fonciere": 20_000, "id_parcelle": "p5", "lot1_numero": "1",
         "type_local": "Appartement", "surface_reelle_bati": 5, "nombre_pieces_principales": 1},
    ] + [
        # enough ordinary sales for the department quantile trim to be meaningful
        {"id_mutation": f"x{i}", "valeur_fonciere": 150_001 + 500 * i, "id_parcelle": f"q{i}", "lot1_numero": "1",
         "type_local": "Appartement", "surface_reelle_bati": 40, "nombre_pieces_principales": 2}
        for i in range(200)
    ])
    out = data.clean_flat_sales(raw)
    kept = set(zip(out["price"], out["surface"]))
    assert (200_000, 40) in kept
    assert not any(p in (300_000, 250_000, 20_000) for p, _ in kept)
    assert (out["price"] == 200_000).sum() == 1
    assert out["price_m2"].between(300, 30_000).all()


def test_zones():
    assert data.zone_of("75") == "paris"
    assert data.zone_of("93") == "petite_couronne"
    assert data.zone_of("91") == "grande_couronne"
    assert data.zone_of("69") == "province"


@pytest.mark.skipif(not (RAW / "qpv_2024.geojson").exists(), reason="QPV perimeters not downloaded")
def test_priority_area_flags_points_inside_perimeters():
    import json

    import shapely

    features = [f for f in json.loads((RAW / "qpv_2024.geojson").read_text())["features"] if f.get("geometry")]
    inside = [shapely.geometry.shape(f["geometry"]).representative_point() for f in features[:50]]
    lon = np.array([p.x for p in inside] + [2.3376])  # the last point: the Louvre, not a priority area
    lat = np.array([p.y for p in inside] + [48.8606])
    flags = data.in_priority_area(lon, lat)
    assert flags[:-1].all()
    assert not flags[-1]
