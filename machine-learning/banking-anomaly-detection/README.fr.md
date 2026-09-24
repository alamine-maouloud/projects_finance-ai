*[English version](README.md)*

# Détection de fraude sur cartes et paiements, évaluée comme une équipe fraude

`txanomaly` est un banc d'essai de détection de fraude sur les transactions par carte et les virements. Il génère une banque synthétique réaliste dont la fraude est connue, construit des variables comportementales qui ne regardent que le passé de chaque client, compare règles de premier niveau, Isolation Forest, régression logistique et gradient boosting, et les mesure comme on mesure un service fraude : alertes par jour, précision, et argent réellement économisé.

Les données sont **synthétiques par choix**. Chaque fraude a une typologie et un incident connus, ce qui permet de mesurer la détection par mode opératoire, et aucune donnée client n'est utilisée.

## Principaux résultats

3 000 clients, 557 553 transactions sur 120 jours, taux de fraude de 0,24 % (326 incidents). Les modèles apprennent sur 64 jours après 14 jours d'amorçage, puis sont testés sur les 42 jours suivants (194 040 transactions, 435 fraudes, 108 incidents). Les analystes examinent **0,2 % des transactions de chaque jour**, soit environ 10 alertes par jour :

| Détecteur | PR-AUC [intervalle à 95 %] | Précision | Fraudes détectées | Incidents détectés | Pertes évitées | Gain net |
|---|---:|---:|---:|---:|---:|---:|
| Isolation Forest sur champs bruts (approche d'origine) | 0,019 [0,010 ; 0,036] | 6 % | 5 % | 15 % | 8 % | 9,7 k€ |
| Règles de premier niveau | 0,130 [0,098 ; 0,162] | 20 % | 19 % | 50 % | 51 % | 75,9 k€ |
| Isolation Forest sur variables comportementales | 0,209 [0,166 ; 0,258] | 29 % | 28 % | 63 % | 67 % | 99,8 k€ |
| Régression logistique | 0,397 [0,320 ; 0,464] | 41 % | 39 % | 69 % | 68 % | 101,6 k€ |
| **Gradient boosting** | **0,864 [0,823 ; 0,894]** | **70 %** | **67 %** | **85 %** | **76 %** | **112,9 k€** |

Les intervalles viennent d'un bootstrap sur les clients. Le gain net correspond aux pertes évitées moins 4 € de coût d'examen par alerte. Une PR-AUC tirée au hasard vaut 0,002 (le taux de fraude).

Ce que montre le banc d'essai :

- **Les variables comptent plus que l'algorithme.** Le même Isolation Forest passe de 0,019 à 0,209 de PR-AUC quand il voit des variables comportementales (montant rapporté à l'historique du client, vélocité, nouveauté du marchand, de l'appareil ou du bénéficiaire, déplacement impossible) plutôt que les champs bruts.
- **Les étiquettes aussi.** Un modèle supervisé, entraîné sur la fraude confirmée du passé, bat le meilleur détecteur non supervisé d'un facteur quatre en PR-AUC.
- **Les arnaques au virement autorisé restent difficiles.** C'est le téléphone du client lui-même qui envoie l'argent : seuls le bénéficiaire et le montant sortent de l'ordinaire. 50 % de ces pertes sont évitées, contre 95 à 100 % pour le test de cartes et la prise de contrôle de compte.

Pertes évitées par typologie, au même budget :

| Détecteur | Test de cartes | Prise de contrôle | Skimming | Carte volée | Arnaque au virement |
|---|---:|---:|---:|---:|---:|
| Isolation Forest, champs bruts | 0 % | 0 % | 61 % | 0 % | 0 % |
| Règles | 49 % | 96 % | 17 % | 61 % | 32 % |
| Gradient boosting | 100 % | 95 % | 77 % | 75 % | 50 % |

Quand le budget augmente, le gradient boosting évite 49 % des pertes à 0,1 % des transactions examinées, 76 % à 0,2 % et 91 % à 0,5 %.

## Chaque alerte est accompagnée de ses motifs

Chaque alerte est expliquée par occultation : chaque famille de variables liées (montant, vélocité, nouveauté, géographie, session, paiements sans contact…) est remise à sa valeur normale, et la baisse du score mesure sa contribution. Les trois premières deviennent des phrases sur lesquelles un analyste peut agir (générées en anglais) :

| Mode opératoire | Transaction | Motifs donnés |
|---|---|---|
| Carte volée | en magasin, 45,76 € | 4 paiements juste sous le plafond sans contact en 2 heures ; 2 paiements dans l'heure, 3 en 24 heures ; 8,3 h d'écart avec les horaires habituels, la nuit |
| Test de cartes | en ligne, 1,20 € | 4 paiements de moins de 5 € dans les 10 dernières minutes, 6 nouveaux marchands dans l'heure ; 6 paiements dans l'heure |
| Skimming | retrait, 460 € | premier paiement chez ce marchand ; 1 375 km/h depuis le dernier paiement carte présente (déplacement impossible) |
| Prise de contrôle | virement, 242 € | session en ligne depuis l'étranger alors que la carte a été utilisée ailleurs ; dépense sur 24 h égale à 24 fois le paiement habituel |
| Arnaque au virement | virement, 1 300 € | montant rond ou juste sous un seuil, 45,9 fois le paiement médian du client ; dépense sur 24 h égale à 145 fois le paiement habituel |

Le premier motif correspond au mode opératoire : le schéma sans contact arrive en tête de toutes les alertes « carte volée », le montant en tête de toutes les alertes « arnaque au virement ».

## Fonctionnement

**Données** (`txanomaly/data.py`). Chaque client a un segment, un domicile, un niveau de dépense, des commerces et sites habituels, des horaires d'activité, un à trois appareils et quelques bénéficiaires réguliers. Cinq modes opératoires sont injectés sous forme d'incidents :

| Mode opératoire | Schéma |
|---|---|
| Test de cartes | une rafale de micro-paiements en ligne chez de nouveaux marchands depuis un nouvel appareil, puis de gros achats |
| Prise de contrôle de compte | un nouvel appareil et une session à l'étranger, des achats ou virements importants vers de nouveaux bénéficiaires |
| Skimming | une carte contrefaite utilisée dans des commerces et distributeurs à l'étranger pendant que la vraie carte sert au domicile |
| Carte volée | des paiements sans contact locaux juste sous le plafond sans code, puis des achats plus importants |
| Arnaque au virement | le téléphone du client envoie un à trois gros virements vers un nouveau bénéficiaire |

Les clients légitimes voyagent aussi, paient depuis l'étranger, changent de téléphone, font des micro-paiements dans des applications, paient leur loyer et envoient parfois un gros virement à une nouvelle personne. Aucun champ ne trahit donc la fraude à lui seul : la meilleure variable prise isolément atteint une ROC-AUC de 0,74.

**Variables** (`txanomaly/features.py`). Vingt-cinq variables comportementales par transaction, calculées uniquement à partir des transactions antérieures du même client :

- **montant** : rapporté à la médiane glissante du client (globale et par canal), et score z ;
- **vélocité** : nombre de paiements et dépense sur 10 minutes, 1 heure et 24 heures ;
- **nouveauté** : première utilisation d'un marchand, d'un appareil, d'un bénéficiaire ou d'un pays ;
- **temps et lieu** : écart aux horaires habituels, distance au domicile, vitesse depuis le dernier paiement carte présente, session à l'étranger alors que la carte était ailleurs ;
- **sans contact** : paiements répétés juste sous le plafond.

Les fenêtres temporelles sont vectorisées par recherche dichotomique sur une clé (client, temps), ce qui calcule toutes les variables de 560 000 transactions en 1,7 s. Un test vérifie l'absence de fuite d'information : ajouter des données futures ne modifie jamais une variable passée. Ce test a détecté une vraie fuite pendant le développement (une médiane de repli calculée sur l'ensemble des données).

**Détecteurs** (`txanomaly/models.py`). Des règles de premier niveau pondérées, un Isolation Forest sur champs bruts, un Isolation Forest sur variables comportementales, une régression logistique équilibrée, et un gradient boosting par histogrammes, avec gestion native des variables catégorielles et arrêt anticipé sur la PR-AUC.

**Évaluation** (`txanomaly/evaluate.py`) :

- un découpage temporel, car un découpage aléatoire fait fuiter le futur de chaque client dans l'apprentissage ;
- un budget d'alertes quotidien, pour que chaque détecteur dispose de la même capacité d'analyse ;
- des pertes évitées calculées en bloquant la carte dès sa première alerte ;
- un bootstrap sur les clients, car les fraudes se concentrent sur les clients compromis ;
- l'importance des variables du gradient boosting par permutation.

## Démarrage rapide

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app]"
pytest -q                          # 18 tests, environ 10 s
txanomaly report                   # banc d'essai complet dans out/ (environ 80 s) ; --quick pour 1 000 clients
txanomaly app                      # tableau de bord d'investigation (Streamlit)
txanomaly generate --out data/transactions.csv.gz
```

Le tableau de bord présente plusieurs vues :
- la file d'alertes du jour avec leurs motifs ;
- les performances par typologie ;
- les pertes évitées en fonction du budget ;
- la chronologie d'un client ;
- la comparaison des modèles.

Le détecteur, le budget d'alertes et le coût d'examen sont réglables.

## Organisation du code

```
txanomaly/
  data.py        clients, marchands, comportements légitimes et incidents de fraude synthétiques
  features.py    variables comportementales causales
  models.py      règles, Isolation Forest, régression logistique, gradient boosting
  evaluate.py    découpage temporel, budget d'alertes, pertes évitées, bootstrap
  explain.py     motifs d'alerte par occultation
  pipeline.py    exécution de bout en bout
  report.py      banc d'essai écrit dans out/results.json et out/alerts.csv
  cli.py         txanomaly generate | report | app
app/streamlit_app.py   tableau de bord d'investigation
tests/                 données, variables (dont fuite), évaluation, modèles, motifs
```

## Limites

- Données synthétiques : les scores absolus (en particulier une PR-AUC de 0,86) sont plus élevés que sur de vrais portefeuilles, où la fraude est plus rare, plus variée et s'adapte aux contrôles. La comparaison entre approches et la méthode d'évaluation restent valables ; les chiffres, non.
- Les étiquettes sont connues immédiatement. En production, la fraude confirmée arrive avec des jours ou des semaines de retard et une partie n'est jamais déclarée, ce dont un modèle de production doit tenir compte.
- Le modèle est entraîné une seule fois. La fraude réelle dérive, ce qui impose un réentraînement périodique et une surveillance de la composition des alertes.
- Les motifs par occultation sont indépendants du modèle et peu coûteux, mais ce ne sont pas des valeurs de Shapley : les interactions entre familles ne sont pas réparties.

## Références

- Bolton, R. & Hand, D. (2002). Statistical fraud detection: a review. *Statistical Science*, 17(3).
- Dal Pozzolo, A., Caelen, O., Le Borgne, Y.-A., Waterschoot, S. & Bontempi, G. (2014). Learned lessons in credit card fraud detection from a practitioner perspective. *Expert Systems with Applications*, 41(10).
- Liu, F. T., Ting, K. M. & Zhou, Z.-H. (2008). Isolation Forest. *IEEE ICDM*.
- Saito, T. & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLoS ONE*, 10(3).
