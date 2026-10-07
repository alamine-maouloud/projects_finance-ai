# RiskLens

Suivi du risque de taux et de crédit d'une poche obligataire réellement publiée : VaR, Expected
Shortfall, contributions, stress, aide à la décision et contrôles de données. Trois restitutions
calculent la même chose : le moteur Python, un classeur Excel en formules et un tableau de bord web.

Projet personnel, sans lien avec Rothschild & Co. Aucune recommandation d'investissement.

## La question traitée

Pour un analyste risques en gestion d'actifs : quelles lignes et quels facteurs portent le risque,
quelle perte produirait un choc de taux ou de crédit, quelle vente réduit le plus le risque par euro
vendu, et quelles anomalies de l'inventaire doivent être instruites ?

## Démarrage

```sh
pip install openpyxl pdfplumber
python -m risklens.extraction   # prépare les données (télécharge ce qui manque)
python -m risklens              # calcule, écrit sorties/RiskLens-Comite.xlsx et sorties/RiskLens.html
```

Ouvrir `sorties/RiskLens.html` dans un navigateur : un seul fichier, sans installation ni connexion.

## Données

| Source | Contenu | Statut |
|---|---|---|
| Inventaire publié de R-co Conviction Credit Euro au 30/06/2025 | 169 lignes de la section taux fixe EUR, rapprochées au sous-total de 2 592 226 795,78 EUR | Extrait |
| BCE, courbe AAA zone euro | Taux zéro-coupon 2, 5 et 10 ans, quotidiens | Extrait |
| Bundesbank, rendements quotidiens | Obligations d'entreprises (Nicht-MFIs) moins titres fédéraux cotés : spread crédit, 108 pb au 30/06/2025 | Extrait |

`python -m risklens.extraction` télécharge les fichiers bruts dans `donnees/brut`, contrôle
l'empreinte SHA-256 du PDF (il refuse un document modifié), rapproche chaque ligne de l'inventaire
(nominal x prix + coupon couru = valeur publiée) et le total au sous-total publié, joint les séries
strictement par date et écrit `donnees/manifeste.json` : adresses, empreintes des fichiers bruts et
dérivés, contrôles. Le moteur refuse tout fichier dérivé dont l'empreinte diffère du manifeste.

**Pourquoi la Bundesbank pour le spread.** Les indices crédit euro de référence (ICE, iBoxx) sont
sous licence. Sur FRED, les séries ICE BofA ne conservent plus que trois ans d'historique depuis
avril 2026, ce qui ne couvre pas la période 2021-2025, et leurs conditions d'utilisation restent
celles d'ICE. Les rendements quotidiens publiés par la Bundesbank sont ouverts et couvrent la période.
Limite assumée : c'est un indice d'émetteurs allemands, pas la composition du fonds.

## Univers modélisé

Toutes les lignes valorisées au 30/06/2025, à prix positif, d'échéance comprise entre la date de
référence et 12 ans : **167 lignes sur 169, soit 66,02 % de l'actif net publié**. Les deux lignes
exclues ont une valorisation nulle, et ce sont précisément des anomalies à instruire :

| Ligne | Constat |
|---|---|
| AGRIPOLE 5.0 11-19 | Échue en 2019, toujours en inventaire, valorisée à zéro, dernier prix du 16/12/2019 |
| CMC RAV 2.0 12-26 | Valorisée à zéro |

Aucun filtre n'est appliqué au code entre parenthèses qui suit le libellé dans le PDF (366, EUR, UST,
EXA, 999) : sa signification reste à confirmer.

## Méthode

- **Flux** : coupons annuels à la date anniversaire de l'échéance, remboursement in fine, ACT/365.25.
- **Courbe** : interpolation linéaire entre 2, 5 et 10 ans, taux constant au-delà de 10 ans (7 lignes).
- **Spread de calibration** : constant, ajusté par dichotomie pour retrouver le prix dirty publié.
- **Sensibilités** : dérivées du prix par rapport à chaque nœud de courbe ; duration de spread nulle
  pour le Bund.
- **Facteur de spread** : variation quotidienne du spread Bundesbank. Par défaut, chaque ligne y réagit
  en proportion de son propre spread (méthode Duration Times Spread : bêta = spread de la ligne /
  spread de l'indice) ; `python -m risklens --spread uniforme` impose un bêta de 1.
- **Pertes historiques** : sensibilités constantes appliquées aux 1 000 dernières variations
  observées, sur les dates communes aux sources, sans remplissage.
- **VaR et ES** : VaR au rang arrondi supérieur de confiance x 1 000 ; ES moyenne pondérée des
  1 000 x (1 - confiance) pires pertes, soit 10 journées à 99 %.
- **Contributions** : allocation d'Euler sur les mêmes journées de queue ; leur somme égale l'ES, par
  ligne comme par facteur.
- **Stress** : choc parallèle de taux et choc uniforme de spread (hors Bund), en approximation
  linéaire et en revalorisation des flux pour mesurer la convexité.
- **Backtest** : 250 VaR glissantes, chacune sur les 250 pertes précédentes, test de Kupiec.

## Résultats de référence (confiance 99 %, horizon 1 jour)

Calculés sur 1 000 variations quotidiennes, aux dates communes aux courbes BCE et au spread
Bundesbank (1 021 dates du 30/06/2021 au 30/06/2025). La colonne « taux seul » est obtenue sans le
facteur de spread, pour mesurer ce qu'il apporte.

| Indicateur | Taux et spread | Taux seul |
|---|---:|---:|
| VaR | 20 982 292 EUR (0,81 %) | 17 023 015 EUR (0,66 %) |
| Expected Shortfall | 29 274 800 EUR | 21 571 464 EUR |
| Backtest sur 250 jours | 4 exceptions pour 2,5 attendues, Kupiec p-value 0,38 | 3 exceptions, p-value 0,76 |

**Où se loge le risque de queue** (contributions d'Euler à l'ES, leur somme égale l'ES) :

| Facteur | Contribution | Part de l'ES |
|---|---:|---:|
| Taux 2 ans | 1 812 072 EUR | 6,2 % |
| Taux 5 ans | 6 351 137 EUR | 21,7 % |
| Taux 10 ans | 3 859 657 EUR | 13,2 % |
| Spread crédit | 17 251 934 EUR | 58,9 % |

Le spread porte près de 60 % de l'ES : pour un fonds crédit, c'est le premier risque. Les premiers
contributeurs sont des obligations d'entreprises longues à spread élevé (MALA HU 4.5 06-35,
KLES PR 5.07 07-35, APIC PR 5.375 10-34) ; le Bund, sans risque de spread, ne pèse plus que 2,6 %.

**Stress** (hypothétiques, choc de spread identique pour toutes les lignes hors Bund) :

| Scénario | Perte linéaire | dont crédit | Revalorisation des flux |
|---|---:|---:|---:|
| Taux +100 pb, spreads +150 pb | 305 562 032 EUR | 178 558 368 EUR | 283 116 697 EUR |
| Taux +200 pb | 254 007 327 EUR | 0 EUR | 238 936 712 EUR |
| Spreads +200 pb | 238 077 825 EUR | 238 077 825 EUR | 223 646 740 EUR |
| Taux -100 pb, spreads +250 pb | 170 593 617 EUR | 297 597 281 EUR | 162 212 115 EUR |

**Aide à la décision, vente de 20 M EUR :**

| Vente | Réduction d'ES par M EUR vendu |
|---|---:|
| Au prorata de toutes les lignes | 11 293 EUR |
| MALA HU 4.5 06-35, premier contributeur à l'ES | 22 092 EUR |
| KLES PR 5.07 07-35, ES par euro le plus élevé | 29 961 EUR |

Vendre la ligne au risque marginal le plus élevé réduit l'ES 2,65 fois plus qu'une vente au prorata.
Le premier contributeur n'est pas forcément la meilleure vente : une ligne peut contribuer beaucoup
parce qu'elle est grosse, pas parce qu'elle est risquée par euro.

## Les trois restitutions

**Tableau de bord** (`sorties/RiskLens.html`) : carte du risque par facteur, premiers contributeurs,
backtest, simulateur de vente, stress interactif, contrôles, sources et empreintes. Le moteur
JavaScript embarqué reprend les formules du moteur Python.

**Classeur Excel** (`sorties/RiskLens-Comite.xlsx`) : tout en formules, sans macro. Modifier la
confiance, les chocs, la ligne vendue ou le montant dans Paramètres met à jour Comité, Positions,
Calculs, Backtest et Contrôles. Onglets : Comité, Paramètres, Positions, Calculs, Historique, Flux,
Backtest, Contrôles, Inventaire, Émetteurs, Sources.

**Module VBA** (`vba/RiskLens.bas`, facultatif) : `VerifierRiskLens` recalcule les 1 000 pertes à
partir des poids, des sensibilités et des variations observées, sans lire les pertes du classeur, et
compare VaR et ES ; `ExporterNoteComite` exporte l'onglet Comité en PDF ; `ExporterResultatsCSV`
exporte les positions. Installation : enregistrer une copie en `.xlsm`, importer `RiskLens.bas` dans
l'éditeur Visual Basic, exécuter `InstallerCommandes`. Sous Mac, Excel peut demander l'autorisation
d'écrire dans le dossier du classeur.

## Vérifications

```sh
pip install pytest playwright && playwright install chromium
python -m pytest                          # 28 tests, dont 4 qui demandent LibreOffice et Playwright
python -m risklens.verification_excel     # classeur recalculé par LibreOffice contre le moteur
python -m risklens.verification_tableau   # tableau de bord contre le moteur
```

Les tests couvrent la non-régression sur la première version, les empreintes, la jointure stricte,
la calibration, les contributions, le capital, le backtest, le facteur de spread (sur une série de
test synthétique, utilisée uniquement pour vérifier les calculs), l'extraction, la concordance du
classeur et du tableau de bord avec le moteur, et l'absence de tiret long dans tout le projet. Les
tests qui demandent LibreOffice ou Playwright sont ignorés s'ils ne sont pas installés.

## Limites

- Le facteur de spread est un indice d'entreprises allemandes, pas la composition du fonds. Les
  rendements sont publiés au centième de point : les variations quotidiennes du spread sont donc
  arrondies au point de base.
- Avec la méthode DTS, une ligne en détresse réagit fortement : IM GROU 8.0 03-28, à 2 912 pb, bouge
  27 fois plus que l'indice. `python -m risklens --spread uniforme` sert de test de sensibilité.
- Dérivés exclus : si le fonds couvre sa duration par des contrats à terme, la VaR de taux de la
  poche surestime celle du fonds.
- Options de remboursement anticipé ignorées ; aucune notation ni donnée ESG dans les sources.
- Inventaire publié après la date de référence, séries téléchargées en 2026 : ce ne sont pas les
  données disponibles le 30/06/2025.
- Ce n'est ni la VaR du fonds, ni un contrôle de ses limites contractuelles ou réglementaires.

## Organisation

```
risklens/
  extraction.py            téléchargement, lecture du PDF, courbes BCE, spread, manifeste
  donnees.py               chargement, empreintes, univers, scénarios
  courbe.py                flux, calibration du spread, sensibilités par nœud
  portefeuille.py          positions, bêta de spread, ventes ciblées et au prorata
  risque.py                VaR, ES, contributions, backtest, test de Kupiec
  stress.py                stress linéaire et revalorisation
  decisions.py             comparaison de ventes, ES par million détenu
  controles.py             anomalies de l'inventaire, dispersion, rapprochements
  excel.py                 génération du classeur
  tableau_de_bord.py       génération du tableau de bord
  verification_excel.py    concordance classeur et moteur
  verification_tableau.py  concordance tableau de bord et moteur
  formats.py               affichage des nombres à la française
tests/test_risklens.py
vba/RiskLens.bas
donnees/                   fichiers dérivés, manifeste ; donnees/brut : fichiers sources
sorties/                   classeur, tableau de bord et résultats générés
```

## Sources

- Inventaire R-co Conviction Credit Euro au 30/06/2025 :
  https://docs.am.eu.rothschildandco.com/RASA_88e4b412-e3e1-e411-80c8-005056924e5f_FR_EN.pdf
- BCE, courbes de taux de la zone euro :
  https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/html/index.en.html
- Bundesbank, rendements quotidiens par catégorie de titres :
  https://www.bundesbank.de/de/statistiken/geld-und-kapitalmaerkte/zinssaetze-und-renditen/taegliche-umlaufsrenditen-festverzinslicher-schuldverschreibungen-inlaendischer-emittenten-nach-wertpapierarten-650674
