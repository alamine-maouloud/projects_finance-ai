"""Mise en forme des nombres à la française."""


def nombre(x: float, decimales: int = 0) -> str:
    texte = f"{x:,.{decimales}f}"
    return texte.replace(",", " ").replace(".", ",")


def eur(x: float) -> str:
    return f"{nombre(x)} EUR"


def pct(x: float, decimales: int = 2) -> str:
    return f"{nombre(x * 100, decimales)} %"
