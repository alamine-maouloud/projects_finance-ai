"""Exécution complète : python -m risklens [--confiance 0.99] [--vente ISIN MONTANT]."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .controles import (anomalies_inventaire, concentration_lignes, dispersion_emetteurs,
                        donnees_indisponibles, rapprochements)
from .decisions import comparer_ventes, es_par_million
from .donnees import (ACTIF_NET_FONDS, DATE_REFERENCE, DOSSIER_DONNEES, charger_courbes, charger_inventaire,
                      charger_spreads, construire_scenarios, univers_modelise, verifier_empreintes)
from .excel import generer_classeur
from .tableau_de_bord import generer_tableau
from .formats import eur, nombre, pct
from .portefeuille import Portefeuille
from .risque import backtester, mesurer
from .stress import SCENARIOS_TYPES, stresser

SORTIES = Path(__file__).resolve().parent.parent / "sorties"
MONTANT_VENTE = 20_000_000


def analyser(confiance: float = 0.99, montant_vente: float = MONTANT_VENTE, methode_spread: str = "dts",
             dossier=DOSSIER_DONNEES, avec_spread: bool = True) -> dict:
    empreintes = verifier_empreintes(dossier)
    inventaire = charger_inventaire(dossier)
    courbes = charger_courbes(dossier)
    spreads = charger_spreads(dossier) if avec_spread else None
    scenarios = construire_scenarios(courbes, spreads=spreads)
    retenues, exclues = univers_modelise(inventaire)
    spread_reference = spreads[DATE_REFERENCE] if spreads else None
    portefeuille = Portefeuille.depuis_lignes(retenues, courbes[-1][1], spread_reference, methode_spread)
    mesure = mesurer(portefeuille, scenarios, confiance)
    ventes = comparer_ventes(portefeuille, scenarios, montant_vente, confiance)
    intensite = es_par_million(portefeuille, mesure)
    eligibles = [i for i in intensite if portefeuille.montants[i] >= montant_vente]
    isin_vente = max(eligibles, key=lambda i: intensite[i])
    return dict(inventaire=inventaire, courbes=courbes, scenarios=scenarios, retenues=retenues,
                empreintes=empreintes, spread_raccorde=spreads is not None, spread_reference=spread_reference,
                methode_spread=methode_spread if spreads else None,
                indisponibles=donnees_indisponibles(spreads is not None),
                exclues=exclues, portefeuille=portefeuille, mesure=mesure, ventes=ventes,
                isin_vente=isin_vente, montant_vente=montant_vente, confiance=confiance,
                backtest=backtester(portefeuille, scenarios, confiance),
                stress={nom: stresser(portefeuille, *chocs) for nom, chocs in SCENARIOS_TYPES.items()},
                alertes=anomalies_inventaire(inventaire, portefeuille) + concentration_lignes(portefeuille),
                dispersion=dispersion_emetteurs(inventaire),
                rapprochements=rapprochements(inventaire, portefeuille, mesure))


def afficher(r: dict) -> None:
    pf, m, b = r["portefeuille"], r["mesure"], r["backtest"]
    nom = {p.isin: p.ligne.libelle for p in pf.positions}
    print(f"Univers : {len(r['retenues'])} lignes modélisées sur {len(r['inventaire'])}, "
          f"{eur(pf.valeur_totale)} ({pct(pf.valeur_totale / ACTIF_NET_FONDS)} de l'actif net)")
    for l, motifs in r["exclues"]:
        print(f"  exclue : {l.libelle} ({', '.join(motifs)})")
    portee = "" if r["spread_raccorde"] else " de taux"
    print(f"\nVaR{portee} {pct(r['confiance'], 0)} à 1 jour : {eur(m.var)}   ES : {eur(m.es)}")
    print("Facteur spread : " + (f"raccordé, méthode {r['methode_spread']}, indice à "
          f"{nombre(r['spread_reference'] * 1e4)} pb" if r["spread_raccorde"] else "non raccordé (VaR de taux seule)"))
    for n, c in m.contributions_facteurs.items():
        print(f"  {n} : {eur(c)}")
    print("Premiers contributeurs :")
    for i, c in sorted(m.contributions_lignes.items(), key=lambda x: -x[1])[:5]:
        print(f"  {nom[i]} : {eur(c)} ({pct(c / m.es, 1)})")
    print(f"\nBacktest : {b.exceptions} exceptions sur {len(b.var)} (attendu {nombre(b.attendu, 1)}), "
          f"Kupiec LR {nombre(b.kupiec_lr, 2)}, p-value {nombre(b.kupiec_p, 2)}")
    print("\nStress :")
    for nom_s, s in r["stress"].items():
        print(f"  {nom_s} : linéaire {eur(s.perte_lineaire)} (taux {eur(s.perte_taux)}, crédit "
              f"{eur(s.perte_credit)}), revalorisé {eur(s.perte_revalorisee)}")
    print(f"\nVentes de {eur(r['montant_vente'])} :")
    for v in r["ventes"]:
        print(f"  {v.description} : ES {eur(v.es_apres)}, réduction {eur(v.reduction_par_million)} par M EUR vendu")
    print("\nAlertes :")
    for a in sorted(r["alertes"], key=lambda a: ["À instruire", "À examiner", "Information"].index(a.severite)):
        print(f"  [{a.severite}] {a.controle} : {a.libelle}. {a.constat}")
    print("\nRapprochements :")
    for libelle, obtenu, attendu, ok in r["rapprochements"]:
        print(f"  {'OK   ' if ok else 'ÉCART'} {libelle}")


def exporter_json(r: dict, chemin: Path) -> None:
    pf, m = r["portefeuille"], r["mesure"]
    contenu = dict(
        date_reference=str(r["courbes"][-1][0]),
        univers=dict(lignes=len(r["retenues"]), valeur=pf.valeur_totale,
                     exclues=[dict(isin=l.isin, libelle=l.libelle, motifs=mo) for l, mo in r["exclues"]]),
        spread_raccorde=r["spread_raccorde"], methode_spread=r["methode_spread"],
        confiance=r["confiance"], var=m.var, es=m.es, contributions_facteurs=m.contributions_facteurs,
        contributions_lignes=m.contributions_lignes,
        backtest=dict(exceptions=r["backtest"].exceptions, kupiec_lr=r["backtest"].kupiec_lr,
                      kupiec_p=r["backtest"].kupiec_p),
        stress={k: dict(lineaire=s.perte_lineaire, taux=s.perte_taux, credit=s.perte_credit,
                        revalorisee=s.perte_revalorisee) for k, s in r["stress"].items()},
        ventes=[dict(description=v.description, montant=v.montant, es_apres=v.es_apres,
                     reduction_par_million=v.reduction_par_million) for v in r["ventes"]],
        alertes=[a.__dict__ for a in r["alertes"]],
        donnees_indisponibles=[dict(theme=t, constat=c, suite=s) for t, c, s in r["indisponibles"]],
        empreintes=r["empreintes"],
    )
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="RiskLens : risque de taux d'une poche obligataire publiée.")
    parser.add_argument("--confiance", type=float, default=0.99, choices=[0.95, 0.99])
    parser.add_argument("--montant-vente", type=float, default=MONTANT_VENTE)
    parser.add_argument("--spread", choices=["dts", "uniforme"], default="dts",
                        help="bêta de spread par ligne : proportionnel au spread (dts) ou égal à 1 (uniforme)")
    parser.add_argument("--sans-excel", action="store_true", help="ne pas générer le classeur ni le tableau de bord")
    args = parser.parse_args()
    r = analyser(args.confiance, args.montant_vente, args.spread)
    afficher(r)
    SORTIES.mkdir(exist_ok=True)
    exporter_json(r, SORTIES / "resultats.json")
    if not args.sans_excel:
        generer_classeur(SORTIES / "RiskLens-Comite.xlsx", r)
        generer_tableau(SORTIES / "RiskLens.html", r)
        print(f"\nClasseur écrit : {SORTIES / 'RiskLens-Comite.xlsx'}")
        print(f"Tableau de bord écrit : {SORTIES / 'RiskLens.html'}")


if __name__ == "__main__":
    main()
