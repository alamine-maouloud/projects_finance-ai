"""Stress hypothétiques : choc parallèle de taux et choc uniforme de spreads.

Deux mesures : l'approximation linéaire par les durations, et la revalorisation
des flux du modèle, qui fait apparaître la convexité sous les grands chocs.
Aucune probabilité n'est attribuée à ces scénarios.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .portefeuille import Portefeuille

SCENARIOS_TYPES = {
    "Choc combiné": (100, 150),
    "Hausse des taux": (200, 0),
    "Élargissement du crédit": (0, 200),
    "Récession": (-100, 250),
}


@dataclass(frozen=True)
class ResultatStress:
    taux_pb: float
    spread_pb: float
    perte_lineaire: float
    perte_taux: float
    perte_credit: float
    perte_revalorisee: float
    pertes_lignes: dict      # ISIN -> perte linéaire en euros


def stresser(portefeuille: Portefeuille, taux_pb: float, spread_pb: float) -> ResultatStress:
    v = portefeuille.valeur_totale
    pertes_lignes, perte_taux, perte_credit, perte_reval = {}, 0.0, 0.0, 0.0
    for p in portefeuille.positions:
        w = portefeuille.poids(p.isin)
        taux = v * w * p.duration * taux_pb / 10_000
        credit = v * w * p.duration_spread * spread_pb / 10_000
        pertes_lignes[p.isin] = taux + credit
        perte_taux += taux
        perte_credit += credit
        choc = (taux_pb + (spread_pb if p.duration_spread else 0)) / 10_000
        avant = sum(f.valeur_actuelle for f in p.calibration.flux)
        apres = sum(f.valeur_actuelle * math.exp(-choc * f.t) for f in p.calibration.flux)
        perte_reval += v * w * (1 - apres / avant)
    return ResultatStress(taux_pb, spread_pb, perte_taux + perte_credit, perte_taux,
                          perte_credit, perte_reval, pertes_lignes)
