"""Modèle de taux : flux théoriques, calibration d'un spread et sensibilités par nœud.

Hypothèses (proxy transparent, pas une valorisation fournisseur) :
- coupons annuels versés à la date anniversaire de l'échéance, remboursement à l'échéance finale ;
- temps en ACT/365.25 depuis la date de référence ;
- taux zéro-coupon interpolés linéairement entre les nœuds 2, 5 et 10 ans, constants au-delà ;
- actualisation continue au taux de la courbe plus un spread constant ;
- le spread est ajusté pour retrouver le prix dirty publié ; ce n'est pas un OAS observé ;
- options de remboursement anticipé ignorées.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from .donnees import DATE_REFERENCE, Ligne

NOEUDS = (2.0, 5.0, 10.0)


def poids_noeuds(t: float) -> tuple[float, float, float]:
    """Poids de chaque nœud dans le taux interpolé à la maturité t (en années)."""
    if t <= 2:
        return (1.0, 0.0, 0.0)
    if t <= 5:
        return ((5 - t) / 3, (t - 2) / 3, 0.0)
    if t < 10:
        return (0.0, (10 - t) / 5, (t - 5) / 5)
    return (0.0, 0.0, 1.0)


@dataclass(frozen=True)
class Flux:
    date: date
    t: float                                  # années depuis la date de référence
    montant: float                            # en % du nominal
    poids: tuple[float, float, float]
    valeur_actuelle: float                    # en % du nominal, après calibration


@dataclass(frozen=True)
class Calibration:
    spread: float                              # spread continu ajusté au prix dirty
    flux: tuple[Flux, ...]
    sensibilites: tuple[float, float, float]   # durations par nœud (key-rate durations)

    @property
    def duration(self) -> float:
        return sum(self.sensibilites)


def _meme_jour(echeance: date, annee: int) -> date:
    try:
        return echeance.replace(year=annee)
    except ValueError:                        # 29 février d'une année non bissextile
        return echeance.replace(year=annee, day=28)


def echeancier(ligne: Ligne) -> list[tuple[date, float, float]]:
    """(date, temps, montant) des flux futurs, du plus proche au plus lointain."""
    flux, annee = [], ligne.echeance.year
    while True:
        d = _meme_jour(ligne.echeance, annee)
        if d <= DATE_REFERENCE:
            break
        montant = ligne.coupon + (100 if annee == ligne.echeance.year else 0)
        flux.append((d, (d - DATE_REFERENCE).days / 365.25, montant))
        annee -= 1
    return sorted(flux, key=lambda x: x[1])


def _taux(poids, courbe) -> float:
    return sum(w * y for w, y in zip(poids, courbe))


def calibrer(ligne: Ligne, courbe: tuple[float, float, float]) -> Calibration:
    """Ajuste le spread par dichotomie puis calcule les sensibilités par nœud."""
    bruts = [(d, t, m, poids_noeuds(t)) for d, t, m in echeancier(ligne)]
    cible = ligne.prix_dirty

    def valeur(spread: float) -> float:
        return sum(m * math.exp(-(_taux(w, courbe) + spread) * t) for _, t, m, w in bruts)

    bas, haut = -0.1, 1.0
    for _ in range(100):
        milieu = (bas + haut) / 2
        if valeur(milieu) > cible:
            bas = milieu
        else:
            haut = milieu
    spread = (bas + haut) / 2

    flux = tuple(
        Flux(d, t, m, w, m * math.exp(-(_taux(w, courbe) + spread) * t)) for d, t, m, w in bruts
    )
    if abs(sum(f.valeur_actuelle for f in flux) - cible) > 1e-8:
        raise ArithmeticError(f"Calibration non convergente pour {ligne.isin}")

    # Dérivée du prix par rapport à chaque nœud, rapportée au prix : sum(VA * t * poids) / prix.
    sensibilites = tuple(
        sum(f.valeur_actuelle * f.t * f.poids[k] for f in flux) / cible for k in range(3)
    )
    return Calibration(spread, flux, sensibilites)
