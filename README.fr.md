*[English version](README.md)*

# mcrisk : un moteur Monte Carlo de mesure des risques bancaires

`mcrisk` simule, dans une seule base de code, les trois risques qui pèsent sur le capital d'une banque, et confronte chaque moteur à une solution de référence exacte :

| Risque | Ce qui est calculé | Techniques clés |
|---|---|---|
| **Crédit (portefeuille)** | Distribution des pertes, VaR / ES, capital économique, allocation d'Euler par contrepartie et par secteur, stress tests, comparaison avec l'IRB bâlois | Copules gaussienne et de Student multi-facteurs, LGD de récession (loi bêta), échantillonnage préférentiel de Glasserman-Li avec mélange défensif, rejeu exact en deux passes, noyau C++ par amincissement de Bernoulli |
| **Marché (FRTB IMA)** | VaR 99 % et ES 97,5 % à 10 jours, cascade des horizons de liquidité, IMCC, ES par composante, backtests hors échantillon | Réévaluation complète d'un portefeuille multi-actifs, simulation historique filtrée (GARCH), scénarios EWMA et Student-t, approximation delta-gamma, tests de Kupiec et de Christoffersen, feux tricolores bâlois |
| **Contrepartie (CCR / XVA)** | EE, ENE, PFE, EEPE, EAD (IMM), compensation (netting), collatéral CSA avec période de marge en risque, CVA / DVA, risque de corrélation défavorable (wrong-way risk) | Hull-White à un facteur calé sur une courbe Nelson-Siegel-Svensson et simulé exactement, fixings de swaps dépendant du chemin, intensité de défaut stochastique de Hull-White (2012) pour le wrong-way risk |
| **Bibliothèque de pricing** | Options européennes, asiatiques, américaines et sous Heston, swaptions | Variables antithétiques, variables de contrôle, QMC randomisé (Sobol + pont brownien), Longstaff-Schwartz, schéma QE d'Andersen |

Les portefeuilles, le book de trading et l'historique de marché sont **synthétiques** : ils sont générés par des processus documentés aux paramètres connus, ce qui permet de tester chaque modèle contre la vérité. Aucune donnée client ou fournisseur n'est utilisée.

## Principaux résultats

Exécution complète : `python -m mcrisk.report` (71 s sur un Apple M4, 10 threads).

**Crédit.** Un portefeuille corporate de 2 000 contreparties (54,8 Md€ d'EAD, 15 facteurs systématiques, 590 contreparties effectives), 2 millions de scénarios en 9,5 s :

| Modèle | EL | VaR 99,9 % | ES 99,9 % | Capital économique |
|---|---:|---:|---:|---:|
| Copule gaussienne | 233 | 1 615 ± 8 | 1 955 ± 12 | 1 382 |
| Copule de Student (ν = 8) | 233 | 4 001 ± 39 | 5 356 ± 62 | 3 768 |
| LGD de récession (bêta, ρ = 0,5) | 279 | 2 785 ± 21 | 3 493 ± 38 | 2 506 |
| *IRB bâlois / ASRF (un seul facteur)* | *233* | *1 973* | | *1 740* |

En M€, ± une erreur-type. La diversification sectorielle et régionale place la VaR multi-facteurs 18 % sous le quantile bâlois à un facteur. La dépendance de queue (copule de Student) la multiplie par 2,5 à PD inchangées. L'échantillonnage préférentiel divise la variance de l'ES 99,9 % par **environ 750** à 300 000 scénarios.

**Marché.** Un book de trading en euros à 16 facteurs de risque (actions au comptant, options sur actions, obligations souveraines et corporate) :

| Modèle de scénarios | VaR 99 % (10 j) | ES 97,5 % (10 j) |
|---|---:|---:|
| Historique (fenêtres chevauchantes) | 90,95 | 84,39 |
| Normal, EWMA 0,94 | 56,32 | 56,76 |
| Student-t (ν = 5) | 63,19 | 66,42 |
| **Historique filtrée (GARCH)** | **71,39** | **74,97** |

L'ES ajustée de la liquidité atteint 79,4 M€ et l'IMCC 95,1 M€ (28 % de diversification entre classes de risque). VaR 99 % à 1 jour hors échantillon sur 1 920 jours, dont deux régimes de crise :

| Modèle | Exceptions (19,2 attendues) | p de Kupiec | p de Christoffersen (cc) |
|---|---:|---:|---:|
| Simulation historique | 37 | 0,0003 ✗ | 0,0006 ✗ |
| Normal EWMA | 32 | 0,0074 ✗ | 0,016 ✗ |
| **Historique filtrée (GARCH)** | **25** | **0,20 ✓** | **0,32 ✓** |

**Contrepartie.** Six swaps en euros face à une même entreprise, dont des opérations déjà en vie (seasoned) et à départ différé :

| Configuration | EPE | EEPE | EAD (IMM) | PFE 97,5 % maximale |
|---|---:|---:|---:|---:|
| Non collatéralisé | 21,43 | 22,47 | 31,45 | 147,3 |
| CSA, seuils de 10 M€, MPoR de 10 jours | 8,00 | 11,02 | 15,43 | 32,4 |
| CSA + 15 M€ de marge initiale | 0,17 | 0,45 | 0,63 | 13,6 |

La CVA s'élève à 3,13 M€ (0,79 M€ sous CSA) et la DVA à 1,01 M€. Le wrong-way risk avec b = 1 augmente la CVA de 104 % ; à l'inverse, une corrélation favorable (right-way, b = −1) la réduit de 71 %. La compensation économise 34 % de l'EPE.

## Validation

Chaque estimation est comparée à une référence exacte ou semi-analytique. z mesure l'écart en nombre d'erreurs-types de l'estimation.

| Test | Référence | Monte Carlo | Exact | z |
|---|---|---:|---:|---:|
| P(L > 30), MC simple | Pool fini, quadrature exacte | 5,432e-3 ± 7,4e-5 | 5,507e-3 | −1,02 |
| P(L > 60), échantillonnage préférentiel | Pool fini, quadrature exacte | 2,3605e-4 ± 7,2e-7 | 2,3605e-4 | +0,01 |
| P(L > 100), échantillonnage préférentiel | Pool fini, quadrature exacte | 6,634e-6 ± 4,0e-8 | 6,674e-6 | −1,01 |
| ES 99,99 %, échantillonnage préférentiel | Pool fini, quadrature exacte | 80,933 ± 0,036 | 80,943 | −0,28 |
| Call européen, antithétique + contrôle | Black-Scholes | 11,338 ± 0,006 | 11,348 | −1,77 |
| Put américain, Longstaff-Schwartz | Arbre CRR, 5 000 pas | 8,696 ± 0,031 | 8,675 | +0,67 |
| Call en diffusion à sauts de Merton | Série de Poisson | 10,603 ± 0,016 | 10,627 | −1,50 |
| Call Heston K = 90, QE, Feller < 1 | Inversion de Gil-Pelaez | 15,692 ± 0,019 | 15,717 | −1,30 |
| Call Heston K = 110, QE, Feller < 1 | Inversion de Gil-Pelaez | 3,406 ± 0,010 | 3,416 | −0,99 |
| Swaption payeuse 5 ans × 10 ans (× 100) | Hull-White / Jamshidian | 4,874 ± 0,010 | 4,872 | +0,24 |
| E[D(0, 5 ans)] | Courbe P(0, 5 ans) | 0,87299 ± 8e-5 | 0,87303 | −0,52 |

La suite de tests (`pytest`, 58 tests) vérifie en plus de nombreuses propriétés :
- la copule de Student et la LGD bêta préservent la perte attendue ;
- les contributions d'Euler se somment exactement à la moyenne de queue ;
- les résultats sont identiques quel que soit le nombre de threads ;
- la valeur d'un swap actualisée par D(0, t) est une martingale ;
- le collatéral réduit l'exposition de façon monotone ;
- la CVA avec b = 0 reproduit exactement la CVA sous indépendance.

## Performance : le noyau C++ par amincissement

Le moteur NumPy tire une variable latente par contrepartie et par scénario, soit un coût en O(N) par scénario. Le noyau C++ (`cpp/src/credit_kernel.cpp`, exposé via pybind11) tire directement les **défauts**, par amincissement de Bernoulli exact :

1. les contreparties sont regroupées en blocs (même profil de facteurs, PD à un facteur 2 près) ;
2. conditionnellement aux facteurs, une borne supérieure peu coûteuse p_max des PD conditionnelles du bloc est calculée à partir des plages de sensibilités précalculées ;
3. les candidats sont tirés avec la probabilité p_max par sauts géométriques, puis acceptés avec la probabilité p_i / p_max.

La méthode est exacte, gère la variable de mélange de la copule de Student, et coûte O(blocs + défauts) par scénario. Chaque bloc de scénarios dispose de son propre flux xoshiro256** : les résultats ne dépendent pas du nombre de threads, et un bloc peut être rejoué à l'identique.

| Contreparties | Scénarios | NumPy (s) | C++ (s) | Gain |
|---:|---:|---:|---:|---:|
| 2 000 | 1 000 000 | 1,89 | 1,70 | ×1,1 |
| 10 000 | 400 000 | 3,98 | 1,46 | ×2,7 |
| 50 000 | 200 000 | 11,08 | 2,19 | ×5,1 |
| 200 000 | 100 000 | 23,94 | 4,99 | ×4,8 |

Ces temps proviennent de `python benchmarks/bench_credit.py` et varient d'environ 20 % d'une exécution à l'autre. La référence NumPy est déjà multi-thread et s'appuie sur BLAS : l'écart vient de l'algorithme, pas du langage.

## Démarrage rapide

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                 # compile aussi le noyau C++ optionnel
python setup.py build_ext --inplace     # recompile le noyau après une modification du C++
pytest -q                               # 58 tests, ~40 s
```

```bash
mcrisk credit --scenarios 1000000 --backend native --contributions
mcrisk credit --method is --scenarios 200000            # échantillonnage préférentiel
mcrisk credit --copula t --nu 6
mcrisk market --backtest
mcrisk ccr --csa
mcrisk report                                           # exécution complète -> out/results.json
python -m mcrisk.dashboard out/results.json out/dashboard.html
```

En tant que bibliothèque :

```python
from mcrisk.credit import CreditModel, simulate, synthetic_portfolio

model = CreditModel(synthetic_portfolio(5_000), copula="t", nu=8)
res = simulate(model, 1_000_000, backend="native", contributions=True)
print(res.summary())
var, es = res.risk_estimates(0.999)   # Estimate(value, stderr)
res.es_contrib                        # contribution d'Euler à l'ES de chaque contrepartie
```

## Organisation du code

```
mcrisk/
  rng.py, stats.py           flux reproductibles, QMC, pont brownien ; VaR/ES pondérées, barres d'erreur
  curves.py                  courbe zéro-coupon Nelson-Siegel-Svensson
  credit/                    portefeuille, modèle à facteurs, moteur (simple / préférentiel), IRB, références exactes, pont natif
  market/                    facteurs de risque + historique synthétique, book de trading, scénarios (HS/EWMA/t/FHS), FRTB, backtests
  ccr/                       swaps sous Hull-White, métriques d'exposition et CSA, CVA/DVA, wrong-way risk
  models/                    GBM, Merton, Heston (analytique + QE), Hull-White
  pricing/                   famille Black-Scholes, MC à variance réduite, Longstaff-Schwartz
  report.py, dashboard.py    exécution complète -> JSON -> tableau de bord HTML autonome
cpp/src/                     noyau crédit natif + bindings pybind11 ; pricer Black-Scholes d'origine en ligne de commande
tests/                       58 tests : validation statistique contre des formes fermées et des invariants
benchmarks/                  débit des deux moteurs crédit
```

## Hypothèses de modélisation et limites

- **Crédit.** Modèle en mode défaut, à un an. Il n'y a ni migration de notation ni valorisation en valeur de marché, et la LGD n'est corrélée entre contreparties qu'à travers le facteur systématique. L'échantillonnage préférentiel est implémenté pour la copule gaussienne à LGD fixe ; pour la copule de Student ou la LGD bêta, utiliser le MC simple (natif ou NumPy).
- **Marché.** Le GARCH est univarié, facteur par facteur, et la dépendance provient du rééchantillonnage de vecteurs de résidus complets. Le book est figé sur l'horizon. L'IMCC est calculé sur la fenêtre courante ; le ratio de calibration sur période stressée ES_R,S / ES_R,C du MAR33 n'est pas implémenté.
- **Contrepartie.** Actualisation mono-courbe, modèle de taux à un facteur (ni smile, ni multi-devises). Le montant minimal de transfert (MTA) est intégré aux seuils. L'exposition est calculée sur une grille bimensuelle, complétée par toutes les dates de flux.
- **Données.** Tout est synthétique, par choix. Pour utiliser des données réelles, il suffit de remplacer `synthetic_portfolio`, `synthetic_history` et les paramètres de la courbe.

## Références

- Glasserman, P. & Li, J. (2005). Importance sampling for portfolio credit risk. *Management Science*, 51(11).
- Hesterberg, T. (1995). Weighted average importance sampling and defensive mixture distributions. *Technometrics*, 37(2).
- Tasche, D. (2008). Capital allocation to business units and sub-portfolios: the Euler principle.
- BCBS (2005). An explanatory note on the Basel II IRB risk weight functions. BCBS (2019). *Minimum capital requirements for market risk* (MAR33).
- Barone-Adesi, G., Giannopoulos, K. & Vosper, L. (1999). VaR without correlations for portfolios of derivative securities. *Journal of Futures Markets*.
- Kupiec, P. (1995) ; Christoffersen, P. (1998). Backtesting des modèles de VaR.
- Andersen, L. (2008). Simple and efficient simulation of the Heston stochastic volatility model. *Journal of Computational Finance*.
- Albrecher, H. et al. (2007). The little Heston trap. *Wilmott Magazine*.
- Longstaff, F. & Schwartz, E. (2001). Valuing American options by simulation. *Review of Financial Studies*.
- Brigo, D. & Mercurio, F. (2006). *Interest Rate Models: Theory and Practice*. Springer.
- Hull, J. & White, A. (2012). CVA and wrong-way risk. *Financial Analysts Journal*, 68(5).
