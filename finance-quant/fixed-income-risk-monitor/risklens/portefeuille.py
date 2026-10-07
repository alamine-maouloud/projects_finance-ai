"""Portefeuille modélisé : positions calibrées et montants détenus.

Le capital reste constant : toute vente est réinvestie en liquidités, sans frais.

Sensibilité au facteur de spread : duration de spread x bêta. Deux méthodes :
- « uniforme » : tous les spreads varient comme l'indice (bêta = 1) ;
- « dts » (Duration Times Spread) : la variation du spread d'une ligne est proportionnelle à
  son niveau, bêta = spread calibré de la ligne / spread de l'indice à la date de référence.
  Une ligne à 300 pb réagit trois fois plus qu'une ligne à 100 pb quand l'indice bouge.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .courbe import Calibration, calibrer
from .donnees import SOUVERAINS, Ligne
from .formats import eur

LIQUIDITES = "LIQUIDITES"


METHODES_SPREAD = ("dts", "uniforme")


@dataclass(frozen=True)
class Position:
    ligne: Ligne
    calibration: Calibration
    beta_spread: float = 1.0

    @property
    def isin(self) -> str:
        return self.ligne.isin

    @property
    def sensibilites(self) -> tuple[float, float, float]:
        return self.calibration.sensibilites

    @property
    def duration(self) -> float:
        return self.calibration.duration

    @property
    def duration_spread(self) -> float:
        """Sensibilité à un choc de spread ; nulle pour un souverain AAA."""
        return 0.0 if self.isin in SOUVERAINS else self.calibration.duration

    @property
    def sensibilite_spread(self) -> float:
        """Sensibilité au facteur de spread historique : duration de spread x bêta."""
        return self.duration_spread * self.beta_spread


@dataclass(frozen=True)
class Portefeuille:
    positions: tuple[Position, ...]
    montants: dict = field(default_factory=dict)   # euros par ISIN, plus LIQUIDITES

    @classmethod
    def depuis_lignes(cls, lignes: list[Ligne], courbe, spread_reference: float | None = None,
                      methode: str = "dts") -> "Portefeuille":
        if methode not in METHODES_SPREAD:
            raise ValueError(f"Méthode de spread inconnue : {methode}")
        positions = []
        for l in lignes:
            calibration = calibrer(l, courbe)
            beta = 1.0
            if methode == "dts" and spread_reference and spread_reference > 0:
                beta = max(calibration.spread, 0.0) / spread_reference
            positions.append(Position(l, calibration, beta))
        positions = tuple(positions)
        montants = {p.isin: p.ligne.valeur for p in positions}
        montants[LIQUIDITES] = 0.0
        return cls(positions, montants)

    @property
    def valeur_totale(self) -> float:
        return sum(self.montants.values())

    def poids(self, isin: str) -> float:
        return self.montants[isin] / self.valeur_totale

    def sensibilites(self) -> tuple[float, float, float]:
        """Sensibilités du portefeuille par nœud : somme des poids x sensibilités."""
        return tuple(
            sum(self.poids(p.isin) * p.sensibilites[k] for p in self.positions) for k in range(3)
        )

    def sensibilite_spread(self) -> float:
        return sum(self.poids(p.isin) * p.sensibilite_spread for p in self.positions)

    def position(self, isin: str) -> Position:
        return next(p for p in self.positions if p.isin == isin)

    def vendre(self, isin: str, montant: float) -> "Portefeuille":
        if not 0 <= montant <= self.montants[isin]:
            raise ValueError(f"Montant de vente invalide pour {isin} : {eur(montant)}")
        montants = dict(self.montants)
        montants[isin] -= montant
        montants[LIQUIDITES] += montant
        return Portefeuille(self.positions, montants)

    def vendre_prorata(self, montant: float) -> "Portefeuille":
        investi = sum(v for k, v in self.montants.items() if k != LIQUIDITES)
        if not 0 <= montant <= investi:
            raise ValueError(f"Montant de vente invalide : {eur(montant)}")
        montants = {k: (v if k == LIQUIDITES else v * (1 - montant / investi))
                    for k, v in self.montants.items()}
        montants[LIQUIDITES] += montant
        return Portefeuille(self.positions, montants)
