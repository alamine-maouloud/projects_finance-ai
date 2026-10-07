"""Mesures de risque historiques : VaR, Expected Shortfall, contributions et backtest.

Conventions : les pertes sont positives ; horizon d'un jour ; positions constantes.
Perte du jour t = valeur x [somme_k (sensibilité au nœud k x variation du taux k)
                           + sensibilité spread x variation du spread crédit].
Sans série de spread, la variation de spread vaut zéro : seule la composante taux est mesurée.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .portefeuille import Portefeuille

NOMS_NOEUDS = ("Taux 2 ans", "Taux 5 ans", "Taux 10 ans")
NOM_SPREAD = "Spread crédit"
NOMS_FACTEURS = NOMS_NOEUDS + (NOM_SPREAD,)


@dataclass(frozen=True)
class QueueDeDistribution:
    var: float
    es: float
    poids: tuple[float, ...]   # poids de chaque scénario dans l'ES (somme = 1)


def rang_var(confiance: float, n: int) -> int:
    """Rang croissant de la VaR : arrondi supérieur de confiance x n (arrondi à 1e-9 près)."""
    return math.ceil(round(confiance * n, 9))


def queue(pertes: list[float], confiance: float) -> QueueDeDistribution:
    """VaR empirique et ES pondéré (la dernière observation de la queue peut compter en partie)."""
    if not pertes or not 0 < confiance < 1 or not all(math.isfinite(x) for x in pertes):
        raise ValueError("Échantillon de pertes ou niveau de confiance invalide")
    n = len(pertes)
    ordre = sorted(range(n), key=lambda i: -pertes[i])       # pires pertes d'abord, tri stable
    masse = n * (1 - confiance)                              # nombre de journées dans la queue
    poids, reste = [0.0] * n, masse
    for i in ordre:
        pris = min(1.0, max(0.0, reste))
        poids[i] = pris / masse
        reste -= pris
    var = pertes[ordre[n - rang_var(confiance, n)]]
    es = sum(p * w for p, w in zip(pertes, poids))
    return QueueDeDistribution(var, es, tuple(poids))


def pertes_historiques(portefeuille: Portefeuille, scenarios) -> list[float]:
    s = portefeuille.sensibilites()
    s_spread = portefeuille.sensibilite_spread()
    v = portefeuille.valeur_totale
    return [v * (sum(sk * dk for sk, dk in zip(s, sc.variations)) + s_spread * sc.variation_spread)
            for sc in scenarios]


@dataclass(frozen=True)
class MesureDeRisque:
    var: float
    es: float
    pertes: tuple[float, ...]
    poids_queue: tuple[float, ...]
    contributions_lignes: dict          # ISIN -> contribution à l'ES en euros
    contributions_facteurs: dict        # nom du facteur -> contribution à l'ES en euros


def mesurer(portefeuille: Portefeuille, scenarios, confiance: float = 0.99) -> MesureDeRisque:
    pertes = pertes_historiques(portefeuille, scenarios)
    q = queue(pertes, confiance)
    # Variation moyenne de chaque facteur sur les journées de la queue (pondérées comme l'ES).
    choc_queue = [sum(w * sc.variations[k] for w, sc in zip(q.poids, scenarios)) for k in range(3)]
    choc_spread = sum(w * sc.variation_spread for w, sc in zip(q.poids, scenarios))
    v = portefeuille.valeur_totale
    par_ligne = {
        p.isin: v * portefeuille.poids(p.isin) * (sum(s * c for s, c in zip(p.sensibilites, choc_queue))
                                                   + p.sensibilite_spread * choc_spread)
        for p in portefeuille.positions
    }
    par_facteur = {nom: v * portefeuille.sensibilites()[k] * choc_queue[k] for k, nom in enumerate(NOMS_NOEUDS)}
    par_facteur[NOM_SPREAD] = v * portefeuille.sensibilite_spread() * choc_spread
    return MesureDeRisque(q.var, q.es, tuple(pertes), q.poids, par_ligne, par_facteur)


@dataclass(frozen=True)
class Backtest:
    dates: tuple
    pertes: tuple[float, ...]
    var: tuple[float, ...]
    exceptions: int
    attendu: float
    kupiec_lr: float
    kupiec_p: float


def kupiec(exceptions: int, n: int, confiance: float) -> tuple[float, float]:
    """Test de couverture inconditionnelle : statistique LR et p-value (khi-deux à 1 degré)."""
    p = 1 - confiance
    observe = exceptions / n
    def logv(prob):
        a = (n - exceptions) * math.log(1 - prob) if exceptions < n else 0.0
        b = exceptions * math.log(prob) if exceptions > 0 else 0.0
        return a + b
    lr = -2 * (logv(p) - logv(observe)) if 0 < observe < 1 else -2 * logv(p)
    return lr, math.erfc(math.sqrt(lr / 2))


def backtester(portefeuille: Portefeuille, scenarios, confiance: float = 0.99,
               fenetre: int = 250, nombre: int = 250) -> Backtest:
    """Chaque VaR n'utilise que les `fenetre` pertes strictement antérieures."""
    pertes = pertes_historiques(portefeuille, scenarios)
    debut = max(fenetre, len(pertes) - nombre)
    var = [queue(pertes[t - fenetre:t], confiance).var for t in range(debut, len(pertes))]
    realisees = pertes[debut:]
    exceptions = sum(1 for l, v in zip(realisees, var) if l > v)
    lr, pval = kupiec(exceptions, len(var), confiance)
    return Backtest(tuple(sc.date for sc in scenarios[debut:]), tuple(realisees), tuple(var),
                    exceptions, len(var) * (1 - confiance), lr, pval)
