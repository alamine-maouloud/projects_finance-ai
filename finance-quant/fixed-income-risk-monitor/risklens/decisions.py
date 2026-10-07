"""Aide à la décision : quelle vente réduit le plus l'ES par euro vendu ?

La contribution d'une ligne à l'ES, divisée par le montant détenu, mesure l'ES
marginal par euro investi (allocation d'Euler). Elle indique où une petite vente
réduit le plus le risque ; une vente importante doit être recalculée en entier,
ce que fait `comparer_ventes`.
"""
from __future__ import annotations

from dataclasses import dataclass

from .portefeuille import Portefeuille
from .risque import mesurer


def es_par_million(portefeuille: Portefeuille, mesure) -> dict:
    """Contribution à l'ES pour un million d'euros détenu, par ligne."""
    return {
        isin: c / portefeuille.montants[isin] * 1e6
        for isin, c in mesure.contributions_lignes.items()
        if portefeuille.montants[isin] > 0
    }


@dataclass(frozen=True)
class ComparaisonVente:
    description: str
    montant: float
    es_avant: float
    es_apres: float

    @property
    def reduction(self) -> float:
        return self.es_avant - self.es_apres

    @property
    def reduction_par_million(self) -> float:
        return self.reduction / self.montant * 1e6


def comparer_ventes(portefeuille: Portefeuille, scenarios, montant: float,
                    confiance: float = 0.99) -> list[ComparaisonVente]:
    """Compare, à montant égal : vente au prorata, vente du premier contributeur,
    et vente de la ligne la plus risquée par euro parmi celles qui peuvent absorber le montant."""
    base = mesurer(portefeuille, scenarios, confiance)
    nom = {p.isin: p.ligne.libelle for p in portefeuille.positions}
    eligibles = [i for i in nom if portefeuille.montants[i] >= montant]
    premier = max(eligibles, key=lambda i: base.contributions_lignes[i])
    intensite = es_par_million(portefeuille, base)
    plus_risquee = max(eligibles, key=lambda i: intensite[i])

    candidats = [("Vente au prorata de toutes les lignes", portefeuille.vendre_prorata(montant)),
                 (f"Vente de {nom[premier]} (premier contributeur à l'ES)",
                  portefeuille.vendre(premier, montant))]
    if plus_risquee != premier:
        candidats.append((f"Vente de {nom[plus_risquee]} (ES par euro le plus élevé)",
                          portefeuille.vendre(plus_risquee, montant)))
    return [ComparaisonVente(d, montant, base.es, mesurer(pf, scenarios, confiance).es)
            for d, pf in candidats]
