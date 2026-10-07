"""Chargement des données publiques et définition de l'univers modélisé.

Sources (préparées par risklens.extraction) :
- inventaire publié du fonds R-co Conviction Credit Euro au 30/06/2025,
  section obligations à taux fixe en EUR (169 lignes extraites du PDF) ;
- courbes zéro-coupon AAA de la BCE à 2, 5 et 10 ans (niveaux décimaux) ;
- facultatif : spread crédit quotidien (obligations d'entreprises moins titres fédéraux, Bundesbank).

Chaque fichier dérivé est vérifié par son empreinte SHA-256, enregistrée dans donnees/manifeste.json.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DOSSIER_DONNEES = Path(__file__).resolve().parent.parent / "donnees"

DATE_REFERENCE = date(2025, 6, 30)
ACTIF_NET_FONDS = 3_926_674_151.41          # actif net publié dans l'inventaire
SOUS_TOTAL_TAUX_FIXE_EUR = 2_592_226_795.78  # sous-total publié de la section
NOMBRE_SCENARIOS = 1000
NOEUD_LONG_ANNEES = 10                       # dernier nœud de courbe disponible
HORIZON_MAX_ANNEES = 12                      # au-delà de 10 ans, taux constant égal au nœud 10 ans

# Titres traités comme souverains AAA : pas de choc de spread dans le stress crédit.
SOUVERAINS = {"DE0001102473"}


_COUPON_EN_FIN_DE_LIBELLE = re.compile(r"(\d+(?:\.\d+)?)(?: (\d+)/(\d+))? (\d{2}[-/]\d{2}(?:/\d{2})?)$")


@dataclass(frozen=True)
class Ligne:
    """Une ligne de l'inventaire publié, telle qu'extraite du PDF."""

    isin: str
    libelle: str
    echeance: date
    coupon: float
    nominal: float
    prix_clean: float
    coupon_couru: float
    valeur: float
    date_prix: date
    page: int
    # Code entre parenthèses après le libellé dans le PDF (366, EUR, UST, EXA, 999).
    # Sa signification reste à confirmer : il n'est utilisé dans aucun filtre.
    code_parenthese: str
    ecart_rapprochement: float

    @property
    def emetteur(self) -> str:
        """Libellé abrégé de l'émetteur (le PDF ne fournit pas d'identifiant émetteur)."""
        m = _COUPON_EN_FIN_DE_LIBELLE.search(self.libelle)
        return self.libelle[: m.start()].strip() if m else self.libelle

    @property
    def prix_dirty(self) -> float:
        """Prix pied de coupon inclus, en % du nominal, déduit de la valorisation publiée."""
        return self.valeur / self.nominal * 100


def empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def empreintes_attendues(dossier: Path = DOSSIER_DONNEES) -> dict:
    return charger_manifeste(dossier)["derives"]


def verifier_empreintes(dossier: Path = DOSSIER_DONNEES) -> dict:
    """Vérifie chaque fichier dérivé contre le manifeste et renvoie les empreintes."""
    attendues = empreintes_attendues(dossier)
    for nom, attendue in attendues.items():
        obtenue = empreinte(dossier / nom)
        if obtenue != attendue:
            raise ValueError(f"{nom} a changé (SHA-256 {obtenue}) : relancer l'extraction ou revoir le fichier.")
    return attendues


def charger_inventaire(dossier: Path = DOSSIER_DONNEES) -> list[Ligne]:
    lignes = []
    with (dossier / "inventory-fixed-eur.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lignes.append(Ligne(
                isin=r["id"],
                libelle=r["name"],
                echeance=date.fromisoformat(r["maturity"]),
                coupon=float(r["coupon"]),
                nominal=float(r["nominal"]),
                prix_clean=float(r["cleanPrice"]),
                coupon_couru=float(r["accruedInterest"]),
                valeur=float(r["marketValue"]),
                date_prix=date.fromisoformat(r["quoteDate"]),
                page=int(r["sourcePage"]),
                code_parenthese=r["codeParenthese"],
                ecart_rapprochement=float(r["priceReconciliation"]),
            ))
    return lignes


def charger_courbes(dossier: Path = DOSSIER_DONNEES) -> list[tuple[date, tuple[float, float, float]]]:
    """Niveaux de taux observés (2, 5 et 10 ans), triés par date."""
    courbes = []
    with (dossier / "ecb-curves.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            courbes.append((date.fromisoformat(r["date"]),
                            (float(r["rate2"]), float(r["rate5"]), float(r["rate10"]))))
    courbes.sort(key=lambda x: x[0])
    if courbes[-1][0] != DATE_REFERENCE:
        raise ValueError("La dernière courbe doit être celle de la date de référence.")
    return courbes


def charger_spreads(dossier: Path = DOSSIER_DONNEES) -> dict | None:
    """Spread crédit quotidien en décimales, ou None si la série n'a pas été extraite."""
    chemin = dossier / "spread-credit.csv"
    if not chemin.exists():
        return None
    with chemin.open(encoding="utf-8") as f:
        return {date.fromisoformat(r["date"]): float(r["spread"]) for r in csv.DictReader(f)}


@dataclass(frozen=True)
class Scenario:
    date: date
    date_precedente: date
    variations: tuple[float, float, float]  # variations observées des taux 2, 5 et 10 ans
    variation_spread: float = 0.0            # variation observée du spread crédit (0 si non raccordé)


def construire_scenarios(courbes, nombre: int = NOMBRE_SCENARIOS, spreads: dict | None = None) -> list[Scenario]:
    """Variations entre deux dates d'observation successives, sans remplissage.

    Avec un spread crédit, seules les dates communes aux deux sources sont retenues (jointure stricte).
    """
    if spreads is not None:
        courbes = [(d, t) for d, t in courbes if d in spreads]
    scenarios = [
        Scenario(d1, d0, tuple(b - a for a, b in zip(t0, t1)),
                 spreads[d1] - spreads[d0] if spreads is not None else 0.0)
        for (d0, t0), (d1, t1) in zip(courbes, courbes[1:])
    ]
    if len(scenarios) < nombre:
        raise ValueError(f"Historique insuffisant : {len(scenarios)} variations disponibles.")
    return scenarios[-nombre:]


def date_limite_modele() -> date:
    return DATE_REFERENCE.replace(year=DATE_REFERENCE.year + HORIZON_MAX_ANNEES)


def motifs_exclusion(ligne: Ligne) -> list[str]:
    """Raisons pour lesquelles une ligne ne peut pas entrer dans le modèle de taux."""
    motifs = []
    if ligne.echeance <= DATE_REFERENCE:
        motifs.append("Échéance dépassée")
    if ligne.prix_clean <= 0 or ligne.valeur <= 0:
        motifs.append("Valorisation nulle")
    if ligne.date_prix != DATE_REFERENCE:
        motifs.append(f"Prix daté du {ligne.date_prix:%d/%m/%Y}")
    if ligne.echeance > date_limite_modele():
        motifs.append(f"Maturité au-delà de {HORIZON_MAX_ANNEES} ans")
    return motifs


def univers_modelise(lignes: list[Ligne]) -> tuple[list[Ligne], list[tuple[Ligne, list[str]]]]:
    """Sépare les lignes modélisables des lignes exclues, avec leurs motifs."""
    retenues, exclues = [], []
    for ligne in lignes:
        motifs = motifs_exclusion(ligne)
        (exclues.append((ligne, motifs)) if motifs else retenues.append(ligne))
    return retenues, exclues


def charger_manifeste(dossier: Path = DOSSIER_DONNEES) -> dict:
    return json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))
