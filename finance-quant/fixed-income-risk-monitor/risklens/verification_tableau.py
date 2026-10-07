"""Vérifie que le tableau de bord calcule exactement comme le moteur Python.

Ouvre le fichier HTML dans un navigateur sans interface (Playwright), appelle le moteur
JavaScript embarqué et compare ses résultats à ceux du moteur Python.
Utilisation : python -m risklens.verification_tableau   (nécessite : pip install playwright ;
playwright install chromium)
"""
from __future__ import annotations

from pathlib import Path

from .verification_excel import valeurs_python


def playwright_disponible() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def valeurs_tableau(chemin: Path, configurations) -> tuple[list[dict], list[str]]:
    """Résultats du moteur JavaScript pour chaque configuration, et erreurs de la page."""
    from playwright.sync_api import sync_playwright
    resultats, erreurs = [], []
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.goto(Path(chemin).resolve().as_uri())
        page.wait_for_function("window.RiskLens !== undefined")
        for confiance, isin, montant, taux, spread in configurations:
            resultats.append(page.evaluate(
                "o => window.RiskLens.calculer(o)",
                dict(confiance=confiance, isin=isin, montant=montant, taux=taux, spread=spread)))
        navigateur.close()
    return resultats, erreurs


def comparer(chemin: Path, portefeuille, scenarios, configurations, tolerance: float = 0.01) -> list[str]:
    ecarts = []
    js, erreurs = valeurs_tableau(chemin, configurations)
    ecarts += [f"Erreur JavaScript : {e}" for e in erreurs]
    for conf, valeurs in zip(configurations, js):
        attendu = valeurs_python(portefeuille, scenarios, *conf)
        for cle, v in attendu.items():
            if abs(valeurs[cle] - v) > tolerance:
                ecarts.append(f"{conf} : {cle} tableau {valeurs[cle]} contre Python {v}")
    return ecarts


if __name__ == "__main__":
    from .__main__ import SORTIES, analyser
    r = analyser()
    configurations = [(0.99, r["isin_vente"], 20e6, 100, 150), (0.95, r["isin_vente"], 20e6, 100, 150),
                      (0.99, "DE0001102473", 50e6, 200, 0), (0.99, "DE0001102473", 0, -100, 250)]
    ecarts = comparer(SORTIES / "RiskLens.html", r["portefeuille"], r["scenarios"], configurations)
    print("Tableau de bord et moteur concordent." if not ecarts else "\n".join(ecarts))
