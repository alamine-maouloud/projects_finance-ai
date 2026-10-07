"""Extraction et préparation des données sources.

python -m risklens.extraction               utilise les fichiers bruts déjà présents, télécharge les manquants
python -m risklens.extraction --telecharger retélécharge toutes les sources

Étapes :
1. inventaire PDF du fonds : vérification de l'empreinte, lecture de la section taux fixe EUR,
   rapprochement de chaque ligne et du sous-total publié ;
2. courbes AAA de la BCE (2, 5 et 10 ans) : jointure stricte par date, observations validées seulement ;
3. spread crédit : rendement moyen des obligations d'entreprises allemandes (Nicht-MFIs) moins
   rendement moyen des titres fédéraux cotés, séries quotidiennes de la Bundesbank ;
4. manifeste : adresses, empreintes des fichiers bruts et dérivés, contrôles.

Les fichiers bruts vont dans donnees/brut, les fichiers dérivés dans donnees.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent.parent / "donnees"
BRUT = DOSSIER / "brut"
DATE_REFERENCE = date(2025, 6, 30)
DEBUT_HISTORIQUE = date(2021, 6, 30)
SOUS_TOTAL_TAUX_FIXE_EUR = 2_592_226_795.78

BCE = "https://data-api.ecb.europa.eu/service/data/YC/"
BBK = "https://api.statistiken.bundesbank.de/rest/data/BBSIS/"
SOURCES = {
    "inventaire_pdf": dict(
        fichier="inventaire.pdf",
        url="https://docs.am.eu.rothschildandco.com/RASA_88e4b412-e3e1-e411-80c8-005056924e5f_FR_EN.pdf",
        sha256="9863e148ff46fb90108eb0dc91b20e115c727489119e8c69410915f157817641",
        description="R-co Conviction Credit Euro, inventaire au 30/06/2025"),
    "bce_5y": dict(
        fichier="ecb-5y.csv",
        url=BCE + "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y?startPeriod=2021-06-30&endPeriod=2025-06-30&format=csvdata",
        description="BCE, courbe AAA, taux zéro-coupon 5 ans"),
    "bce_2y_10y": dict(
        fichier="ecb-2y-10y.csv",
        url=BCE + "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y+SR_10Y?startPeriod=2021-06-30&endPeriod=2025-06-30&format=csvdata",
        description="BCE, courbe AAA, taux zéro-coupon 2 et 10 ans"),
    "bbk_entreprises": dict(
        fichier="bbk-entreprises.csv",
        url=BBK + "D.I.UMR.RD.EUR.X2000.B.A.A.R.A.A._Z._Z.A?format=csv&lang=de",
        description="Bundesbank, rendement moyen des obligations d'entreprises (Nicht-MFIs), quotidien"),
    "bbk_bund": dict(
        fichier="bbk-bund.csv",
        url=BBK + "D.I.UMR.RD.EUR.S1311.B.A604.A.R.A.A._Z._Z.A?format=csv&lang=de",
        description="Bundesbank, rendement moyen des titres fédéraux cotés, quotidien"),
}

COLONNES_INVENTAIRE = ["id", "name", "maturity", "coupon", "nominal", "cleanPrice", "accruedInterest",
                       "marketValue", "quoteDate", "sourcePage", "codeParenthese", "priceReconciliation"]


def sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def telecharger(cle: str, forcer: bool = False) -> Path | None:
    """Télécharge une source dans donnees/brut si absente (ou si forcer). Renvoie None en cas d'échec."""
    source = SOURCES[cle]
    cible = BRUT / source["fichier"]
    if cible.exists() and not forcer:
        return cible
    BRUT.mkdir(parents=True, exist_ok=True)
    try:
        requete = urllib.request.Request(source["url"], headers={"User-Agent": "RiskLens/1.0"})
        with urllib.request.urlopen(requete, timeout=180) as reponse:
            contenu = reponse.read()
    except OSError as erreur:
        print(f"Téléchargement impossible pour {cle} : {erreur}")
        return None
    temporaire = cible.with_suffix(cible.suffix + ".part")
    temporaire.write_bytes(contenu)
    temporaire.replace(cible)
    return cible


# ---------------------------------------------------------------- inventaire PDF

_LIGNE = re.compile(
    r"^([A-Z]{2}[A-Z0-9]{10}) (.*?) \(([^)]+)\) (\d{6}) ([\d,.]+) M EUR ([\d,.]+) % (\d{2}/\d{2}/\d{2}) "
    r"([\d,.]+) ([A-Z0-9]) ([\d,.-]+) ([\d,.-]+) ([\d,.-]+) ([\d,.-]+) ([\d,.-]+)$")
_COUPON = re.compile(r"(\d+(?:\.\d+)?)(?: (\d+)/(\d+))? (\d{2}[-/]\d{2}(?:/\d{2})?)$")
DEBUT_SECTION = "Fixed-rate bonds traded on a regulated or similar market"
FIN_SECTION = "SUBTOTAL Asset Currency : EUR EURO"


def _nombre(texte: str) -> float:
    return float(texte.replace(",", ""))


def lire_ligne_inventaire(texte: str, page: int) -> dict:
    """Transforme une ligne de texte du PDF en enregistrement ; lève ValueError si le format diffère."""
    m = _LIGNE.match(texte)
    if not m:
        raise ValueError(f"Ligne non reconnue, page {page} : {texte}")
    isin, nom, code, echeance, nominal, _cout, date_prix, prix, _qualite, _livre, valeur, couru, _pv, _part = m.groups()
    c = _COUPON.search(nom)
    coupon = None if not c else float(c[1]) + (float(c[2]) / float(c[3]) if c[2] else 0)
    rec = dict(id=isin, name=nom, maturity=datetime.strptime(echeance, "%d%m%y").date().isoformat(),
               coupon=coupon, nominal=_nombre(nominal), cleanPrice=_nombre(prix),
               accruedInterest=_nombre(couru), marketValue=_nombre(valeur),
               quoteDate=datetime.strptime(date_prix, "%d/%m/%y").date().isoformat(),
               sourcePage=page, codeParenthese=code)
    rec["priceReconciliation"] = rec["marketValue"] - rec["nominal"] * rec["cleanPrice"] / 100 - rec["accruedInterest"]
    if abs(rec["priceReconciliation"]) >= 0.02:
        raise ValueError(f"{isin} : valeur publiée non rapprochée ({rec['priceReconciliation']:.2f})")
    return rec


def lire_section_taux_fixe(pages: list[str]) -> list[dict]:
    """Lit la section obligations à taux fixe en EUR à partir du texte de chaque page."""
    enregistrements, active, echecs = [], False, []
    for numero, texte in enumerate(pages, 1):
        for ligne in (texte or "").splitlines():
            if ligne == DEBUT_SECTION and not enregistrements:
                active = True
            if active and ligne == FIN_SECTION:
                active = False
            if not active or not re.match(r"^[A-Z]{2}[A-Z0-9]{10} ", ligne):
                continue
            try:
                enregistrements.append(lire_ligne_inventaire(ligne, numero))
            except ValueError as erreur:
                echecs.append(str(erreur))
    if echecs:
        raise ValueError("Lignes non lues :\n" + "\n".join(echecs))
    total = sum(r["marketValue"] for r in enregistrements)
    if abs(total - SOUS_TOTAL_TAUX_FIXE_EUR) >= 0.02:
        raise ValueError(f"Total extrait {total:.2f} différent du sous-total publié {SOUS_TOTAL_TAUX_FIXE_EUR:.2f}")
    return enregistrements


def extraire_inventaire(pdf: Path) -> list[dict]:
    attendue = SOURCES["inventaire_pdf"]["sha256"]
    if sha256(pdf) != attendue:
        raise ValueError("Le PDF de l'inventaire a changé : revue manuelle requise avant toute extraction.")
    import pdfplumber
    with pdfplumber.open(pdf) as document:
        pages = [page.extract_text() or "" for page in document.pages]
    return lire_section_taux_fixe(pages)


# ---------------------------------------------------------------- courbes BCE

def lire_courbes_bce(fichiers: list[Path]) -> list[tuple[str, float, float, float]]:
    """Niveaux 2, 5 et 10 ans en décimales, dates communes aux trois séries, observations validées."""
    niveaux: dict[str, dict[str, float]] = {}
    for f in fichiers:
        with f.open(encoding="utf-8") as flux:
            for r in csv.DictReader(flux):
                if r["OBS_VALUE"] and r["OBS_STATUS"] == "A" and r["TIME_PERIOD"] <= DATE_REFERENCE.isoformat():
                    niveaux.setdefault(r["TIME_PERIOD"], {})[r["DATA_TYPE_FM"]] = float(r["OBS_VALUE"]) / 100
    cles = ("SR_2Y", "SR_5Y", "SR_10Y")
    dates = sorted(d for d, v in niveaux.items() if all(k in v for k in cles))
    if not dates or dates[-1] != DATE_REFERENCE.isoformat():
        raise ValueError("La courbe de la date de référence est absente.")
    return [(d, *(niveaux[d][k] for k in cles)) for d in dates]


# ---------------------------------------------------------------- Bundesbank

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def lire_serie_bundesbank(chemin: Path) -> dict[str, float]:
    """Lit une série quotidienne de la Bundesbank (CSV, séparateur ; ou ,, décimale , ou .).

    Les lignes d'en-tête et les valeurs manquantes (« . » ou vide) sont ignorées.
    Renvoie {date ISO : valeur en % par an}.
    """
    texte = chemin.read_text(encoding="utf-8-sig", errors="replace")
    lignes = [l for l in texte.splitlines() if l.strip()]
    serie: dict[str, float] = {}
    entete = lignes[0] if lignes else ""
    if "TIME_PERIOD" in entete and "OBS_VALUE" in entete:
        separateur = ";" if entete.count(";") > entete.count(",") else ","
        for r in csv.DictReader(lignes, delimiter=separateur):
            valeur = (r.get("OBS_VALUE") or "").strip().replace(",", ".")
            if _DATE.match(r.get("TIME_PERIOD", "")) and valeur not in ("", "."):
                serie[r["TIME_PERIOD"]] = float(valeur)
        return serie
    for ligne in lignes:
        separateur = ";" if ";" in ligne else ","
        champs = [c.strip().strip('"') for c in ligne.split(separateur)]
        if len(champs) < 2 or not _DATE.match(champs[0]):
            continue
        valeur = champs[1].replace(",", ".")
        if valeur in ("", "."):
            continue
        serie[champs[0]] = float(valeur)
    return serie


def construire_spread(entreprises: dict[str, float], bund: dict[str, float],
                      dates_courbes: set[str]) -> list[tuple[str, float, float, float]]:
    """(date, rendement entreprises, rendement Bund, spread) en décimales, dates communes avec les courbes."""
    dates = sorted(d for d in entreprises.keys() & bund.keys() & dates_courbes
                   if DEBUT_HISTORIQUE.isoformat() <= d <= DATE_REFERENCE.isoformat())
    lignes = [(d, entreprises[d] / 100, bund[d] / 100, (entreprises[d] - bund[d]) / 100) for d in dates]
    for d, e, b, s in lignes:
        if not (-0.02 < e < 0.20 and -0.02 < b < 0.15 and -0.01 < s < 0.10):
            raise ValueError(f"Valeur hors plage plausible le {d} : entreprises {e:.4%}, Bund {b:.4%}")
    if not lignes or lignes[-1][0] != DATE_REFERENCE.isoformat():
        raise ValueError("Le spread de la date de référence est absent.")
    return lignes


# ---------------------------------------------------------------- écriture et manifeste

def ecrire_csv(chemin: Path, colonnes: list[str], lignes) -> str:
    with chemin.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(colonnes)
        w.writerows(lignes)
    return sha256(chemin)


def ecrire_manifeste(derives: dict, controles: dict) -> None:
    sources = {}
    for cle, s in SOURCES.items():
        fichier = BRUT / s["fichier"]
        sources[cle] = dict(url=s["url"], description=s["description"], fichier=f"brut/{s['fichier']}",
                            present=fichier.exists(), sha256=sha256(fichier) if fichier.exists() else s.get("sha256"))
    manifeste = dict(date_reference=DATE_REFERENCE.isoformat(),
                     genere_le=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     sources=sources, derives=derives, controles=controles)
    (DOSSIER / "manifeste.json").write_text(json.dumps(manifeste, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prépare les données de RiskLens.")
    parser.add_argument("--telecharger", action="store_true", help="retélécharger toutes les sources")
    args = parser.parse_args()
    derives, controles = {}, {}

    pdf = telecharger("inventaire_pdf", args.telecharger)
    if pdf:
        inventaire = extraire_inventaire(pdf)
        derives["inventory-fixed-eur.csv"] = ecrire_csv(
            DOSSIER / "inventory-fixed-eur.csv", COLONNES_INVENTAIRE,
            ([r[c] for c in COLONNES_INVENTAIRE] for r in inventaire))
        controles["lignes_inventaire"] = len(inventaire)
        print(f"Inventaire : {len(inventaire)} lignes, total rapproché du sous-total publié.")
    elif (DOSSIER / "inventory-fixed-eur.csv").exists():
        derives["inventory-fixed-eur.csv"] = sha256(DOSSIER / "inventory-fixed-eur.csv")
        print("Inventaire : PDF indisponible, extraction existante conservée.")

    fichiers_bce = [telecharger("bce_5y", args.telecharger), telecharger("bce_2y_10y", args.telecharger)]
    if not all(fichiers_bce):
        raise SystemExit("Courbes BCE indisponibles : impossible de continuer.")
    courbes = lire_courbes_bce(fichiers_bce)
    derives["ecb-curves.csv"] = ecrire_csv(DOSSIER / "ecb-curves.csv", ["date", "rate2", "rate5", "rate10"], courbes)
    controles["dates_courbes"] = len(courbes)
    print(f"Courbes BCE : {len(courbes)} dates, du {courbes[0][0]} au {courbes[-1][0]}.")

    entreprises, bund = telecharger("bbk_entreprises", args.telecharger), telecharger("bbk_bund", args.telecharger)
    if entreprises and bund:
        spread = construire_spread(lire_serie_bundesbank(entreprises), lire_serie_bundesbank(bund),
                                   {c[0] for c in courbes})
        derives["spread-credit.csv"] = ecrire_csv(
            DOSSIER / "spread-credit.csv", ["date", "rendement_entreprises", "rendement_bund", "spread"], spread)
        controles["dates_spread"] = len(spread)
        print(f"Spread crédit : {len(spread)} dates communes avec les courbes, "
              f"{spread[-1][3] * 1e4:.0f} pb au {spread[-1][0]}.")
    else:
        print("Spread crédit : séries Bundesbank indisponibles, la VaR restera limitée au risque de taux.")

    ecrire_manifeste(derives, controles)
    print("Manifeste écrit : donnees/manifeste.json")


if __name__ == "__main__":
    main()
