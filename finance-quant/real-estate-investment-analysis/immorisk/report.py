"""Charts for the README, built from out/communes.csv and out/results.json."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from . import data, market, simulate, universe
from .config import OUT, Assumptions
from .pipeline import REFERENCE

INK = "#2b2b2b"
MUTED = "#8a8a8a"
LIGHT = "#d6d6d6"
ACCENT = "#b5542c"
SEQ = LinearSegmentedColormap.from_list("seq", ["#efe6dc", "#d9a47f", "#b5542c", "#6e2c14"])

plt.rcParams.update({
    "font.family": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "figure.dpi": 150, "savefig.bbox": "tight", "savefig.facecolor": "white",
})

def _pct(ax, axis="y"):
    fmt = matplotlib.ticker.PercentFormatter(1.0, decimals=0)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def map_irr(t: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    d = t.dropna(subset=["lon", "lat"]).sort_values("irr_median")
    d = d[(d["lon"].between(-5.5, 10)) & (d["lat"].between(41, 51.5))]
    size = 4 + 10 * np.sqrt(d["sales_per_year"] / d["sales_per_year"].max())
    sc = ax.scatter(d["lon"], d["lat"] , c=d["irr_median"], cmap=SEQ, vmin=0.0, vmax=0.07, s=size, linewidths=0)
    ax.set_aspect(1 / np.cos(np.radians(46.5)))
    ax.axis("off")
    cb = fig.colorbar(sc, ax=ax, shrink=0.5, pad=0.01)
    cb.outline.set_visible(False)
    cb.ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    cb.set_label("median IRR on equity, 15 years", color=INK)
    ax.set_title(f"{len(d):,} communes, one leveraged 37 m2 flat each")
    fig.savefig(path)
    plt.close(fig)


# cities labelled on the scatter, with offsets in points placed by hand so names do not collide
OFFSETS = {
    "Limoges": (8, 4), "Saint-Etienne": (8, -10), "Clermont-Ferrand": (10, 10), "Montpellier": (-20, 16),
    "Le Havre": (12, -12), "Paris 11e": (-58, 10), "Lyon 3e": (-50, -12), "Bordeaux": (4, -20),
}


def yield_vs_irr(t: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.scatter(t["gross_yield"], t["irr_median"], s=6, color=LIGHT, linewidths=0, label="all communes")
    ref = t[t["commune"].isin(REFERENCE)]
    ax.scatter(ref["gross_yield"], ref["irr_median"], s=24, color=ACCENT, linewidths=0, label="large cities")
    for _, r in ref.iterrows():
        name = REFERENCE[r["commune"]]
        if name in OFFSETS:
            ax.annotate(name, (r["gross_yield"], r["irr_median"]), xytext=OFFSETS[name], textcoords="offset points",
                        fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6, shrinkA=0, shrinkB=3))
    _pct(ax, "x")
    _pct(ax)
    ax.set_xlim(0.02, 0.16)
    ax.set_xlabel("gross yield (rent excluding charges / price)")
    ax.set_ylabel("median IRR on equity, 15 years")
    ax.set_title("A high yield is not a high return")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def backtest(res: dict, path):
    dec = pd.DataFrame(res["backtest"]["deciles"])
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.4), sharex=True)
    x = np.arange(len(dec))
    labels = [f"{y:.1%}" for y in dec["yield_2022"]]
    axes[0].bar(x, dec["price_change"], color=[ACCENT if v < 0 else MUTED for v in dec["price_change"]], width=0.7)
    axes[0].axhline(0, color=INK, lw=0.8)
    axes[0].set_title("Price change 2022 to 2025")
    axes[1].bar(x, dec["total_return_3y"], color=MUTED, width=0.7)
    axes[1].set_title("Price change plus three years of gross rent")
    for ax in axes:
        _pct(ax)
        ax.set_xticks(x, labels, rotation=60, fontsize=7.5)
        ax.set_xlabel("communes by 2022 gross yield (decile median)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def distributions(uni: pd.DataFrame, model, a: Assumptions, path, codes: dict, regimes: dict):
    from .finance import irr

    H, P = a.market.horizon_years, a.market.n_paths
    rng = np.random.default_rng([a.market.seed, 0])
    paths = market.simulate_market(model, P, H, a.market.price_growth, a.market.rent_growth, rng)
    irrs = []
    for code in codes:
        rows = uni[uni["commune"] == code]
        ar = a.with_(tax={"regime": regimes[code]})
        irrs.append(irr(simulate.cash_flows(rows, ar, paths, simulate.draw_local(rows, ar, model, P, H)).cash)[0])
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    grid = np.linspace(-0.15, 0.20, 400)
    shades = [ACCENT, INK, MUTED, "#c9a27e"]
    for i, (code, name) in enumerate(codes.items()):
        v = np.nan_to_num(irrs[i], nan=-1.0)
        w = np.clip(v, -0.4, 0.4)
        bw = 1.06 * w.std() * len(w) ** -0.2  # Silverman's rule
        dens = np.exp(-0.5 * ((grid[:, None] - w[None, :]) / bw) ** 2).sum(axis=1) / (len(w) * bw * np.sqrt(2 * np.pi))
        ax.plot(grid, dens, color=shades[i % 4], lw=1.8,
                label=f"{name}: median {np.median(v):.1%}, 1 in 20 below {np.quantile(v, 0.05):.1%}, P(loss) {np.mean(v < 0):.0%}")
    ax.axvline(0, color=INK, lw=0.6, ls=":")
    _pct(ax, "x")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("IRR on equity over 15 years")
    ax.set_title("Distribution of outcomes, 2,000 simulated paths")
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def build(a: Assumptions | None = None):
    a = a or Assumptions()
    charts = OUT / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    t = pd.read_csv(OUT / "communes.csv", dtype={"commune": str, "dep": str})
    res = json.loads((OUT / "results.json").read_text())
    map_irr(t, charts / "map_irr.png")
    yield_vs_irr(t, charts / "yield_vs_irr.png")
    backtest(res, charts / "backtest_yield.png")

    sales = data.load_sales(universe.CURRENT_YEARS)
    uni, _ = universe.build(a, sales=sales)
    mm = res["market_model"]
    model = market.MarketModel(np.array(mm["phi"]), np.array(mm["sigma_quarterly"]), np.array(mm["corr"]),
                               np.array(mm["start_quarterly"]), dep_sd=mm["dep_sd_annual"], commune_sd=mm["commune_sd_annual"])
    top = t.iloc[0]
    codes = {top["commune"]: top["name"], "87085": "Limoges", "75111": "Paris 11e", "42218": "Saint-Etienne"}
    distributions(uni, model, a, charts / "irr_distributions.png", codes, t.set_index("commune")["regime"].to_dict())
    return charts
