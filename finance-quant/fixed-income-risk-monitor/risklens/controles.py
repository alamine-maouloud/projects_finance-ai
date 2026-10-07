"""Contrôles sur l'inventaire publié complet et sur le portefeuille modélisé.

Les seuils sont des seuils de revue, paramétrables. Ils ne constituent pas les limites
contractuelles ou réglementaires du fonds, qui exigent le prospectus et le portefeuille complet.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .donnees import (ACTIF_NET_FONDS, DATE_REFERENCE, NOEUD_LONG_ANNEES, SOUS_TOTAL_TAUX_FIXE_EUR,
                      SOUVERAINS, Ligne)
from .formats import eur, nombre, pct
from .portefeuille import Portefeuille

SEUILS = {
    "spread_revue_pb": 600,        # spread calibré au-delà duquel la ligne passe en suivi crédit
    "age_prix_jours": 5,           # ancienneté maximale d'un prix à la date de référence
    "ligne_max": 0.10,             # poids maximal d'une ligne dans le portefeuille modélisé
    "emetteur_max": 0.10,          # règle de dispersion de type 5/10/40, en % de l'actif net
    "emetteur_seuil": 0.05,
    "emetteurs_cumul_max": 0.40,
    "ecart_rapprochement": 0.02,   # écart toléré entre valeur publiée et nominal x prix + couru
}

SPREAD_NON_RACCORDE = ("Spreads historiques", "Série de spread non extraite : la VaR ne couvre que le risque de taux.",
                       "Lancer python -m risklens.extraction pour télécharger les séries de la Bundesbank")
SPREAD_PROXY = ("Spread crédit approché", "Le facteur de spread est un indice d'obligations d'entreprises allemandes "
                "(Bundesbank) : il ne reflète ni la composition ni la notation exacte du fonds.",
                "Remplacer par un indice crédit euro sous licence si l'équipe en dispose")

DONNEES_INDISPONIBLES = [
    ("Dérivés et couvertures", "Les instruments à terme du fonds ne sont pas intégrés ; une couverture de duration réduirait le risque de taux.",
     "Extraire la section des instruments financiers à terme de l'inventaire"),
    ("Notations", "Aucune notation ni historique de migration dans les sources publiques importées.",
     "Raccorder un référentiel de notations pour suivre les passages en haut rendement"),
    ("Données ESG", "Aucune donnée ESG émetteur importée ; l'absence de donnée n'est pas une mauvaise note.",
     "Raccorder une source ESG documentée"),
    ("Autres sections du fonds", "Taux variable, autres devises et liquidités du fonds hors périmètre.",
     "Étendre l'extraction à l'inventaire complet"),
]


def donnees_indisponibles(spread_raccorde: bool) -> list[tuple[str, str, str]]:
    return [SPREAD_PROXY if spread_raccorde else SPREAD_NON_RACCORDE] + DONNEES_INDISPONIBLES


@dataclass(frozen=True)
class Alerte:
    severite: str      # « À instruire », « À examiner » ou « Information »
    controle: str
    isin: str
    libelle: str
    constat: str
    suite: str


def anomalies_inventaire(lignes: list[Ligne], portefeuille: Portefeuille | None = None,
                         seuils: dict = SEUILS) -> list[Alerte]:
    alertes = []
    spreads = {p.isin: p.calibration.spread for p in portefeuille.positions} if portefeuille else {}
    for l in lignes:
        def ajouter(severite, controle, constat, suite):
            alertes.append(Alerte(severite, controle, l.isin, l.libelle, constat, suite))

        if abs(l.ecart_rapprochement) > seuils["ecart_rapprochement"]:
            ajouter("À instruire", "Rapprochement de valorisation",
                    f"Écart de {nombre(l.ecart_rapprochement, 2)} EUR avec nominal x prix + couru",
                    "Rapprocher avec le valorisateur avant tout calcul")
        if l.echeance <= DATE_REFERENCE:
            ajouter("À instruire", "Titre échu toujours en inventaire",
                    f"Échéance au {l.echeance:%d/%m/%Y}, valorisé {eur(l.valeur)}",
                    "Confirmer le statut du titre (remboursement, défaut, restructuration) et la valeur de recouvrement")
        if l.prix_clean <= 0 or l.valeur <= 0:
            ajouter("À instruire", "Valorisation nulle",
                    f"Prix {nombre(l.prix_clean, 2)}, valeur {eur(l.valeur)} pour un nominal de {eur(l.nominal)}",
                    "Documenter la méthode de valorisation retenue et la source du prix")
        age = (DATE_REFERENCE - l.date_prix).days
        if age > seuils["age_prix_jours"]:
            ajouter("À instruire", "Prix ancien",
                    f"Dernier prix daté du {l.date_prix:%d/%m/%Y} ({age} jours)",
                    "Obtenir un prix récent ou justifier l'absence de cotation")
        if l.isin in spreads and spreads[l.isin] * 1e4 > seuils["spread_revue_pb"]:
            ajouter("À examiner", "Spread élevé",
                    f"Spread calibré de {nombre(spreads[l.isin] * 1e4)} pb (prix {nombre(l.prix_clean, 2)})",
                    "Suivi crédit : analyse de l'émetteur et des contraintes du mandat")
        t = (l.echeance - DATE_REFERENCE).days / 365.25
        if l.isin in spreads and t > NOEUD_LONG_ANNEES:
            ajouter("Information", "Extrapolation de courbe",
                    f"Maturité de {nombre(t, 2)} ans, au-delà du nœud 10 ans",
                    "Taux supposé constant au-delà de 10 ans ; ajouter un nœud long si le poids augmente")
    return alertes


def concentration_lignes(portefeuille: Portefeuille, seuils: dict = SEUILS) -> list[Alerte]:
    return [
        Alerte("À examiner", "Concentration de ligne", p.isin, p.ligne.libelle,
               f"{pct(portefeuille.poids(p.isin))} du portefeuille modélisé",
               "Seuil de revue interne au prototype, pas une limite du fonds")
        for p in portefeuille.positions if portefeuille.poids(p.isin) > seuils["ligne_max"]
    ]


@dataclass(frozen=True)
class Dispersion:
    poids_emetteurs: dict          # émetteur -> poids dans l'actif net du fonds
    plus_de_5: dict                # émetteurs au-dessus du seuil de 5 %
    cumul_plus_de_5: float
    depassements_10: dict


def dispersion_emetteurs(lignes: list[Ligne], seuils: dict = SEUILS) -> Dispersion:
    """Règle de dispersion de type 5/10/40, calculée en % de l'actif net publié.

    Seule la section taux fixe EUR est connue : les ratios obtenus sont des minimums.
    Les émetteurs sont regroupés par libellé abrégé, faute d'identifiant émetteur.
    """
    poids = defaultdict(float)
    for l in lignes:
        poids[l.emetteur] += l.valeur / ACTIF_NET_FONDS
    souverains = {l.emetteur for l in lignes if l.isin in SOUVERAINS}
    non_souverains = {e: w for e, w in poids.items() if e not in souverains}
    plus_de_5 = {e: w for e, w in non_souverains.items() if w > seuils["emetteur_seuil"]}
    return Dispersion(dict(poids), plus_de_5, sum(plus_de_5.values()),
                      {e: w for e, w in non_souverains.items() if w > seuils["emetteur_max"]})


def rapprochements(lignes: list[Ligne], portefeuille: Portefeuille, mesure) -> list[tuple[str, float, float, bool]]:
    """(contrôle, valeur obtenue, valeur attendue, conforme)."""
    total = sum(l.valeur for l in lignes)
    somme_poids = sum(portefeuille.poids(i) for i in portefeuille.montants)
    contributions = sum(mesure.contributions_lignes.values())
    noeuds = sum(mesure.contributions_facteurs.values())
    return [
        ("Total de l'inventaire = sous-total publié (EUR)", total, SOUS_TOTAL_TAUX_FIXE_EUR,
         abs(total - SOUS_TOTAL_TAUX_FIXE_EUR) < 0.02),
        ("Somme des poids du portefeuille modélisé", somme_poids, 1.0, abs(somme_poids - 1) < 1e-9),
        ("Somme des contributions par ligne = ES (EUR)", contributions, mesure.es, abs(contributions - mesure.es) < 0.01),
        ("Somme des contributions par facteur = ES (EUR)", noeuds, mesure.es, abs(noeuds - mesure.es) < 0.01),
        ("Somme des poids de queue", sum(mesure.poids_queue), 1.0, abs(sum(mesure.poids_queue) - 1) < 1e-9),
    ]
