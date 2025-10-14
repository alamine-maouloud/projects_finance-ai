import pandas as pd
import numpy as np

print("Préparation des Données ")
print("Étape 1 : Traitement du fichier des loyers")

url_loyers = "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2023/20240115-134722/pred-app12-mef-dhup.csv"


df_loyers_brut = pd.read_csv(url_loyers, sep=';', decimal=',', encoding='latin-1')

print("Données brutes chargées. Voici un aperçu :")
display(df_loyers_brut.head())

url_ventes = "https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres/20250406-003027/valeursfoncieres-2023.txt.zip"



colonnes_rename_map = {
    'Valeur fonciere': 'valeur_fonciere',
    'Commune': 'nom_commune',
    'Code commune': 'code_commune',
    'Code departement': 'code_departement',
    'Surface reelle bati': 'surface_reelle_bati',
    'Nombre pieces principales': 'nombre_pieces_principales',
    'Type local': 'type_local',
    'Nature mutation': 'nature_mutation'
}

chunk_list = []
reader = pd.read_csv(
    url_ventes,
    compression='zip',
    sep='|',
    decimal=',',
    dtype={'Code commune': str, 'Code departement': str},
    low_memory=False,
    chunksize=100000
)

for chunk in reader:
    chunk.columns = chunk.columns.str.strip()

    chunk.rename(columns=colonnes_rename_map, inplace=True)
    
    colonnes_a_garder = list(colonnes_rename_map.values())
    if not all(col in chunk.columns for col in colonnes_a_garder):
        continue
    chunk = chunk[colonnes_a_garder]


    chunk = chunk[chunk['nature_mutation'] == 'Vente']
    chunk = chunk[chunk['type_local'] == 'Appartement']
    chunk = chunk[chunk['nombre_pieces_principales'].isin([1.0, 2.0])]
    
    chunk_list.append(chunk)


df_ventes = pd.concat(chunk_list, ignore_index=True)

df_ventes.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'], inplace=True)
df_ventes = df_ventes[(df_ventes['surface_reelle_bati'] > 10) & (df_ventes['valeur_fonciere'] > 10000)]

print("Fichier des ventes nettoyé. Il nous reste", len(df_ventes), "ventes pertinentes.")
print("\nVoici un aperçu des ventes individuelles après nettoyage :")
display(df_ventes.head(10)) 

df_ventes['prix_m2'] = (df_ventes['valeur_fonciere'] / df_ventes['surface_reelle_bati']).round()

df_ventes_agg = df_ventes.groupby(['code_commune', 'nom_commune', 'code_departement']).agg(
    prix_m2_moyen=('prix_m2', 'mean'),
    nombre_ventes=('valeur_fonciere', 'count')
).reset_index()

df_ventes_agg['prix_m2_moyen'] = df_ventes_agg['prix_m2_moyen'].round().astype(int)
df_ventes_agg = df_ventes_agg[df_ventes_agg['nombre_ventes'] >= 10]

df_ventes_tries = df_ventes_agg.sort_values('prix_m2_moyen', ascending=True)


print(f" Calcul du prix au m² terminé. Nous avons des données fiables pour {len(df_ventes_tries)} communes.")
print("\nPour montrer l'étendue des possibilités, voici le TOP 20 des communes les plus abordables :")
display(df_ventes_tries.head(20))

import pandas as pd
url_etudiants = "https://data.enseignementsup-recherche.gouv.fr/explore/dataset/fr-esr-atlas_regional-effectifs-d-etudiants-inscrits/download?format=csv"

df_etudiants_brut = pd.read_csv(url_etudiants, sep=';')

print("Données avant le nettoyage sur les étudiants.")
display(df_etudiants_brut.head())

colonnes_utiles = ['geo_id', 'geo_nom', 'effectif', 'annee_universitaire']
df_etudiants = df_etudiants_brut[colonnes_utiles].copy()

df_etudiants.rename(columns={
    'geo_id': 'code_commune',
    'geo_nom': 'nom_commune',
    'effectif': 'nombre_etudiants'
}, inplace=True)

annee_recente = df_etudiants['annee_universitaire'].max()
df_etudiants = df_etudiants[df_etudiants['annee_universitaire'] == annee_recente]
print(f"INFO : Année la plus récente sélectionnée : {annee_recente}")

df_etudiants_agg = df_etudiants.groupby(['code_commune', 'nom_commune'])['nombre_etudiants'].sum().reset_index()


df_etudiants_agg['code_commune'] = df_etudiants_agg['code_commune'].astype(str).str.zfill(5)

df_etudiants_tries = df_etudiants_agg.sort_values('nombre_etudiants', ascending=False)


print(f"\n Fichier des étudiants nettoyé. Nous avons des données pour {len(df_etudiants_tries)} communes.")
print("\nVoici le TOP 20 des villes étudiantes de France (hors Paris et ses arrondissements) :")
display(df_etudiants_tries[~df_etudiants_tries['nom_commune'].str.contains("Paris")].head(20))

url_gares = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/frequentation-gares/exports/csv?use_labels=true"


df_gares_brut = pd.read_csv(url_gares, sep=';')

print(" Données brutes sur les gares ")
display(df_gares_brut.head())

import pandas as pd

url = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/frequentation-gares/exports/csv?use_labels=true"
df = pd.read_csv(url, sep=';')

df = df.dropna(subset=['Nom de la gare', 'Total Voyageurs 2023', 'Total Voyageurs 2024'])

df['Croissance (%)'] = ((df['Total Voyageurs 2024'] - df['Total Voyageurs 2023']) / df['Total Voyageurs 2023'] * 100).round(1)
df = df[df['Total Voyageurs 2023'] > 1000]  

top_10 = df.nlargest(10, 'Total Voyageurs 2024')[['Nom de la gare', 'Code postal', 'Total Voyageurs 2024', 'Croissance (%)']]

print("TOP 10 GARES - FRÉQUENTATION 2024")
print("=" * 60)
for i, row in top_10.iterrows():
    print(f"{i+1:2d}. {row['Nom de la gare'][:25]:25} {row['Code postal']:6} {row['Total Voyageurs 2024']:>10,} voyageurs ({row['Croissance (%)']}%)")

hors_paris = df[~df['Nom de la gare'].str.contains('Paris')].nlargest(10, 'Total Voyageurs 2024')[['Nom de la gare', 'Code postal', 'Total Voyageurs 2024', 'Croissance (%)']]

print("\nTOP 10 HORS PARIS FRÉQUENTATION 2024")
print("=" * 60)
for i, row in hors_paris.iterrows():
    print(f"{i+1:2d}. {row['Nom de la gare'][:25]:25} {row['Code postal']:6} {row['Total Voyageurs 2024']:>10,} voyageurs (+{row['Croissance (%)']}%)")

top_croissance = df[df['Total Voyageurs 2024'] > 100000].nlargest(10, 'Croissance (%)')[['Nom de la gare', 'Code postal', 'Total Voyageurs 2024', 'Croissance (%)']]

print("\nTOP 10 CROISSANCE (gares > 100k voyageurs)")
print("=" * 60)
for i, row in top_croissance.iterrows():
    print(f"{i+1:2d}. {row['Nom de la gare'][:25]:25} {row['Code postal']:6} {row['Total Voyageurs 2024']:>10,} voyageurs (+{row['Croissance (%)']}%)")

bons_plans = df[
    (df['Total Voyageurs 2024'] > 500000) & 
    (df['Croissance (%)'] > 10)
][['Nom de la gare', 'Code postal', 'Total Voyageurs 2024', 'Croissance (%)']].head(10)

print("\nGare à potentiel")
print("=" * 60)
for i, row in bons_plans.iterrows():
    print(f"{i+1:2d}. {row['Nom de la gare'][:25]:25} {row['Code postal']:6} {row['Total Voyageurs 2024']:>10,} voyageurs (+{row['Croissance (%)']}%)")

print(f"\nSTATISTIQUES GLOBALES")
print(f"Nombre total de gares analysées : {len(df)}")
print(f"Gare la plus fréquentée : {df.loc[df['Total Voyageurs 2024'].idxmax(), 'Nom de la gare']}")
print(f"Plus forte croissance : {df['Croissance (%)'].max():.1f}%")

import pandas as pd
import os
import numpy as np

chemin_exact = '/Users/al-aminemaouloud/Desktop/donnees_communes.csv'

print(f" Recherche du fichier : {chemin_exact}")

if os.path.exists(chemin_exact):
    print("Fichier trouvé !")
    
    df = pd.read_csv(chemin_exact, sep=';')
    
    print(f"Données chargées : {df.shape}")
    print("Colonnes disponibles :", list(df.columns))
    
    print("\n=== APERÇU DES DONNÉES ===")
    print(df.head(5))
    
    print("\n=== NETTOYAGE EN COURS ===")
    
    colonnes_disponibles = df.columns.tolist()
    print(f"Colonnes dans ton fichier : {colonnes_disponibles}")
    
    if 'DEP' in df.columns and 'Commune' in df.columns:
        df_final = df[['DEP', 'Commune']].copy()
        
        if 'PTOT' in df.columns:
            df_final['population_total'] = pd.to_numeric(df['PTOT'], errors='coerce').fillna(0).astype(int)
        else:
            df_final['population_total'] = 10000
            print("Colonne PTOT non trouvée - population fictive utilisée")
        
        df_final = df_final.rename(columns={
            'DEP': 'departement',
            'Commune': 'commune'
        })
        
        print("Colonnes renommées")
        
        print(f"\n=== RÉSULTAT FINAL ===")
        print(f" {len(df_final)} communes")
        print(f" Départements : {df_final['departement'].nunique()}")
        
        print("\nAPERÇU DES DONNÉES :")
        print(df_final.head(10))
        
        print(f"\n PRÊT POUR L'APPLICATION !")
        
    else:
        print("Colonnes DEP ou Commune manquantes")
        print("Utilise les colonnes disponibles pour créer la structure :")
        df_final = pd.DataFrame({
            'departement': ['75', '77', '78', '91', '92', '93', '94', '95'],
            'commune': ['Paris', 'Melun', 'Versailles', 'Évry', 'Nanterre', 'Bobigny', 'Créteil', 'Cergy'],
            'population_total': [2000000, 40000, 85000, 50000, 90000, 50000, 90000, 60000]
        })
        print("Structure par défaut créée :")
        print(df_final)
        
else:
    print("Fichier non trouvé à ce chemin exact")

    print("\n TÉLÉCHARGEMENT ALTERNATIF")
    print("1. Va sur ton Bureau Mac")
    print("2. Fais un clic droit sur 'donnees_communes.csv'")
    print("3. Choisis 'Copier le chemin'")
    print("4. Colle le chemin exact ici")
    
    print("\n Création de données d'exemple pour tester l'application...")

    np.random.seed(42)
    n_communes = 500
    
    departements = ['75', '77', '78', '91', '92', '93', '94', '95', '13', '69', '31', '59', '33']
    communes_exemples = {
        '75': ['Paris'],
        '77': ['Melun', 'Meaux', 'Chelles', 'Pontault-Combault'],
        '78': ['Versailles', 'Sartrouville', 'Mantes-la-Jolie', 'Saint-Germain-en-Laye'],
        '91': ['Évry', 'Massy', 'Palaiseau', 'Savigny-sur-Orge'],
        '92': ['Nanterre', 'Boulogne-Billancourt', 'Courbevoie', 'Asnières-sur-Seine'],
        '93': ['Bobigny', 'Saint-Denis', 'Montreuil', 'Aubervilliers'],
        '94': ['Créteil', 'Vitry-sur-Seine', 'Champigny-sur-Marne', 'Ivry-sur-Seine'],
        '95': ['Cergy', 'Argenteuil', 'Sarcelles', 'Garges-lès-Gonesse'],
        '13': ['Marseille', 'Aix-en-Provence', 'Arles', 'Martigues'],
        '69': ['Lyon', 'Villeurbanne', 'Vénissieux', 'Saint-Priest'],
        '31': ['Toulouse', 'Colomiers', 'Tournefeuille', 'Blagnac'],
        '59': ['Lille', 'Roubaix', 'Tourcoing', 'Dunkerque'],
        '33': ['Bordeaux', 'Mérignac', 'Pessac', 'Talence']
    }
    
    data = []
    for i in range(n_communes):
        dept = np.random.choice(departements)
        commune = np.random.choice(communes_exemples[dept])
        
        data.append({
            'departement': dept,
            'commune': f"{commune}_{i}" if i > len(communes_exemples[dept]) else commune,
            'population_total': np.random.randint(1000, 200000),
            'budget_70m2': np.random.randint(50000, 500000),
            'rendement_brut_%': np.random.uniform(3.5, 7.5),
            'vacance_%': np.random.uniform(1, 12),
            'loyer_mensuel_estime': np.random.randint(400, 1500)
        })
    
    df_final = pd.DataFrame(data)
    print(f" Données d'exemple créées : {df_final.shape}")
    print(df_final.head(10))

print(f"\n{'='*50}")
print(" LANCEMENT DE  L'APPLICATION !")
print(f"{'='*50}")

if 'df_final' in locals():
    print(f"Données prêtes : {df_final.shape}")
    print(f"Communes : {len(df_final)}")
    print(f"Départements : {df_final['departement'].nunique()}")
    print(f"Budget moyen : {df_final['budget_70m2'].mean():,.0f}€")
    print(f"Rendement moyen : {df_final['rendement_brut_%'].mean():.1f}%")
else:
    print("Aucune donnée disponible")


print("VÉRIFICATION DES DONNÉES CHARGÉES")
print("=" * 60)

dataframes = {
    'Communes': df_final,
    'Ventes': df_ventes_agg, 
    'Étudiants': df_etudiants_agg,
    'Gares': df,  
    'Loyers': df_loyers_brut
}

print("RÉSUMÉ DES DONNÉES DISPONIBLES :")
print("=" * 50)

for nom, df in dataframes.items():
    try:
        if df is not None and not df.empty:
            print(f" {nom}:")
            print(f"  Dimensions: {df.shape[0]} lignes, {df.shape[1]} colonnes")
            print(f"   Colonnes: {list(df.columns)}")
            
            if 'commune' in df.columns:
                exemple = df.iloc[0]['commune'] if len(df) > 0 else 'Aucune donnée'
            elif 'nom_commune' in df.columns:
                exemple = df.iloc[0]['nom_commune'] if len(df) > 0 else 'Aucune donnée'
            elif 'Commune' in df.columns:
                exemple = df.iloc[0]['Commune'] if len(df) > 0 else 'Aucune donnée'
            elif 'Nom de la gare' in df.columns: 
                exemple = df.iloc[0]['Nom de la gare'] if len(df) > 0 else 'Aucune donnée'
            else:
                exemple = df.iloc[0][df.columns[0]] if len(df) > 0 else 'Aucune donnée'
                
            print(f"    Exemple: {exemple}")
            
            print(f"   Types (3 premiers):")
            for col in df.columns[:3]:
                print(f"      - {col}: {df[col].dtype}")
            print("-" * 40)
        else:
            print(f" {nom}: Données non chargées ou vides")
            print("-" * 40)
    except NameError:
        print(f" {nom}: DataFrame non défini")
        print("-" * 40)
    except Exception as e:
        print(f" {nom}: Erreur - {e}")
        print("-" * 40)

print("\n RECHERCHE DES COLONNES DE JOINTURE :")
print("=" * 50)

colonnes_jointure = {}
for nom, df in dataframes.items():
    try:
        if df is not None and not df.empty:
            colonnes_potentielles = []
            for col in df.columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['code', 'insee', 'commune', 'postal', 'departement']):
                    colonnes_potentielles.append(col)
            
            if colonnes_potentielles:
                print(f" {nom}: {colonnes_potentielles}")
                colonnes_jointure[nom] = colonnes_potentielles
            else:
                print(f"{nom}: Aucune colonne de jointure évidente - Colonnes: {list(df.columns)}")
        else:
            print(f" {nom}: Données manquantes")
    except NameError:
        print(f" {nom}: DataFrame non défini")

print(f"\n SYNTHÈSE DES COLONNES DE JOINTURE :")
for nom, colonnes in colonnes_jointure.items():
    print(f"   {nom}: {colonnes}")


print("CRÉATION D'UN SIMULATEUR")
print("=" * 50)


if 'df_final' in locals() and df_final is not None:
    print("Utilisation de tes données existantes (df_final)")
    df_analysis = df_final.copy()
else:
    print("Création de données de base pour le simulateur")
    import pandas as pd
    import numpy as np

    np.random.seed(42)
    n_communes = 500
    
    data = []
    departements = ['75', '77', '78', '91', '92', '93', '94', '95', '13', '69', '31', '59', '33']
    
    for i in range(n_communes):
        data.append({
            'departement': np.random.choice(departements),
            'commune': f'Commune_{i}',
            'population_total': np.random.randint(1000, 200000)
        })
    
    df_analysis = pd.DataFrame(data)

print(f"Données de base chargées : {df_analysis.shape}")

import numpy as np
np.random.seed(42) 


def estimer_prix(departement, population):
    prix_base = {
        '75': 8000, '77': 2200, '78': 3500, '91': 2800, '92': 5500, '93': 2500, '94': 4000, '95': 3000,
        '13': 3000, '69': 3000, '31': 2200, '59': 1800, '33': 2800
    }
    
    prix = prix_base.get(departement, 2000) 
    
    if population > 50000:
        prix *= 1.3 
    elif population > 20000:
        prix *= 1.1
    elif population < 2000:
        prix *= 0.8 
    
    prix *= np.random.uniform(0.9, 1.1)
    
    return int(prix)


df_analysis['prix_m2_moyen'] = df_analysis.apply(
    lambda x: estimer_prix(x['departement'], x['population_total']), axis=1
)


df_analysis['loyer_m2'] = df_analysis['prix_m2_moyen'] * np.random.uniform(0.003, 0.006, len(df_analysis))

df_analysis['rendement_brut'] = (df_analysis['loyer_m2'] * 12 / df_analysis['prix_m2_moyen'] * 100).round(2)


df_analysis['ratio_etudiants'] = np.random.uniform(0.01, 0.15, len(df_analysis))  
df_analysis['nombre_etudiants'] = (df_analysis['population_total'] * df_analysis['ratio_etudiants']).astype(int)

df_analysis['nombre_ventes'] = (df_analysis['population_total'] * np.random.uniform(0.001, 0.005, len(df_analysis))).astype(int)


df_analysis['budget_max_70m2'] = df_analysis['prix_m2_moyen'] * 70
df_analysis['score_transport'] = (df_analysis['population_total'] / df_analysis['population_total'].max() * 10).round(1)
df_analysis['score_liquidite'] = (df_analysis['nombre_ventes'] / df_analysis['nombre_ventes'].max() * 10).round(1)

print("Simulateur réaliste créé !")
print(f" {len(df_analysis)} communes avec données simulées réalistes")
print(f" Prix m² moyens : {df_analysis['prix_m2_moyen'].min():.0f}€ - {df_analysis['prix_m2_moyen'].max():.0f}€")
print(f"Rendements : {df_analysis['rendement_brut'].min():.1f}% - {df_analysis['rendement_brut'].max():.1f}%")

print(f"\n APERÇU DES DONNÉES :")
print(df_analysis[['departement', 'commune', 'population_total', 'prix_m2_moyen', 'rendement_brut', 'ratio_etudiants']].head(10))



import pandas as pd
import numpy as np
import ipywidgets as widgets
from IPython.display import display, clear_output
import matplotlib.pyplot as plt
import matplotlib.patches as patches

print(" APPLICATION")
print("=" * 60)


np.random.seed(42)
n_communes = 500

departements = ['75', '77', '78', '91', '92', '93', '94', '95', '13', '69', '31', '59', '33']
villes_exemples = {
    '75': ['Paris'],
    '77': ['Melun', 'Meaux', 'Chelles', 'Pontault-Combault'],
    '78': ['Versailles', 'Sartrouville', 'Mantes-la-Jolie', 'Saint-Germain-en-Laye'],
    '91': ['Évry', 'Massy', 'Palaiseau', 'Savigny-sur-Orge'],
    '92': ['Nanterre', 'Boulogne-Billancourt', 'Courbevoie', 'Asnières-sur-Seine'],
    '93': ['Bobigny', 'Saint-Denis', 'Montreuil', 'Aubervilliers'],
    '94': ['Créteil', 'Vitry-sur-Seine', 'Champigny-sur-Marne', 'Ivry-sur-Seine'],
    '95': ['Cergy', 'Argenteuil', 'Sarcelles', 'Garges-lès-Gonesse'],
    '13': ['Marseille', 'Aix-en-Provence', 'Arles', 'Martigues'],
    '69': ['Lyon', 'Villeurbanne', 'Vénissieux', 'Saint-Priest'],
    '31': ['Toulouse', 'Colomiers', 'Tournefeuille', 'Blagnac'],
    '59': ['Lille', 'Roubaix', 'Tourcoing', 'Dunkerque'],
    '33': ['Bordeaux', 'Mérignac', 'Pessac', 'Talence']
}

data = []
for i in range(n_communes):
    dept = np.random.choice(departements)
    ville_base = np.random.choice(villes_exemples[dept])
    
    data.append({
        'departement': dept,
        'commune': f"{ville_base}_{i}" if i > len(villes_exemples[dept]) else ville_base,
        'population_total': np.random.randint(1000, 200000),
        'budget_70m2': np.random.randint(50000, 500000),
        'rendement_brut_%': np.random.uniform(3.5, 7.5),
        'vacance_%': np.random.uniform(1, 12),
        'loyer_mensuel_estime': np.random.randint(400, 1500)
    })

df = pd.DataFrame(data)
print(f"Données créées : {df.shape}")


style = """
<style>
    .widget-label { font-weight: bold; color: #2c3e50; }
    .result-card { 
        background: white; 
        border-radius: 15px; 
        padding: 20px; 
        margin: 10px 0; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .stat-number { 
        font-size: 2em; 
        font-weight: bold; 
        color: #2c3e50; 
        text-align: center;
    }
    .stat-label { 
        text-align: center; 
        color: #7f8c8d; 
        font-size: 0.9em;
    }
    .progress-bar { 
        height: 8px; 
        background: #ecf0f1; 
        border-radius: 4px; 
        margin: 10px 0; 
        overflow: hidden;
    }
    .progress-fill { 
        height: 100%; 
        background: linear-gradient(90deg, #667eea, #764ba2); 
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    .filter-active { border-left-color: #27ae60 !important; }
    .filter-weak { border-left-color: #e74c3c !important; }
</style>
"""



budget_slider = widgets.IntSlider(value=300000, min=50000, max=800000, step=10000, description='💰 Budget max:')
rendement_slider = widgets.FloatSlider(value=5.0, min=3.0, max=8.0, step=0.1, description='📈 Rendement min:')
population_slider = widgets.IntSlider(value=100000, min=0, max=500000, step=10000, description='👥 Population max:')

departement_select = widgets.SelectMultiple(
    options=sorted(df['departement'].unique()),
    value=['75', '77', '78'],
    description='🗺️ Départements:',
    rows=6
)

result_output = widgets.Output()
chart_output = widgets.Output()



def create_stat_card(value, label, color="#2c3e50"):
    return widgets.VBox([
        widgets.HTML(f"<div class='stat-number' style='color: {color}'>{value}</div>"),
        widgets.HTML(f"<div class='stat-label'>{label}</div>")
    ], layout=widgets.Layout(width='120px', margin='10px'))

def appliquer_filtres(budget, rendement, population, departements_selectionnes):
    filtre_budget = df['budget_70m2'] <= budget
    filtre_rendement = df['rendement_brut_%'] >= rendement
    filtre_population = df['population_total'] <= population
    filtre_departement = df['departement'].isin(departements_selectionnes)
    
    filtre_complet = filtre_budget & filtre_rendement & filtre_population & filtre_departement
    communes_filtrees = df[filtre_complet]
    
    stats = {
        'budget': len(df[filtre_budget]),
        'rendement': len(df[filtre_rendement]),
        'population': len(df[filtre_population]),
        'departements': len(df[filtre_departement]),
        'final': len(communes_filtrees)
    }
    
    return stats, communes_filtrees

def creer_tableau_de_bord_simple(communes_filtrees):
    with chart_output:
        clear_output(wait=True)
        
        if len(communes_filtrees) == 0:
            display(widgets.HTML("<div style='text-align: center; padding: 40px; color: #7f8c8d;'>Aucune donnée à afficher</div>"))
            return
        
        display(widgets.HTML("<h2 style='color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;'>📊 ANALYSE DES RÉSULTATS</h2>"))
        
        top_10 = communes_filtrees.nlargest(10, 'rendement_brut_%')
        
        display(widgets.HTML("<h4>🏆 TOP 10 MEILLEURS RENDEMENTS</h4>"))
        
        table_html = """
        <div style='background: #f8f9fa; padding: 15px; border-radius: 10px;'>
            <table style='width: 100%; border-collapse: collapse;'>
                <thead>
                    <tr style='background: #3498db; color: white;'>
                        <th style='padding: 10px; text-align: left;'>Commune</th>
                        <th style='padding: 10px; text-align: center;'>Département</th>
                        <th style='padding: 10px; text-align: center;'>Rendement</th>
                        <th style='padding: 10px; text-align: center;'>Budget</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for idx, row in top_10.iterrows():
            table_html += f"""
                    <tr style='border-bottom: 1px solid #eee;'>
                        <td style='padding: 10px;'><strong>{row['commune']}</strong></td>
                        <td style='padding: 10px; text-align: center;'>{row['departement']}</td>
                        <td style='padding: 10px; text-align: center; color: #27ae60; font-weight: bold;'>{row['rendement_brut_%']:.1f}%</td>
                        <td style='padding: 10px; text-align: center;'>{row['budget_70m2']:,}€</td>
                    </tr>
            """
        
        table_html += """
                </tbody>
            </table>
        </div>
        """
        
        display(widgets.HTML(table_html))
        

        display(widgets.HTML(f"""
        <div style='background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;'>
            <h4 style='color: #2c3e50; margin-top: 0;'>📈 INDICATEURS CLÉS</h4>
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 15px;'>
                <div style='text-align: center;'>
                    <div style='font-size: 1.3em; font-weight: bold; color: #27ae60;'>{communes_filtrees['rendement_brut_%'].max():.1f}%</div>
                    <div style='color: #7f8c8d;'>Meilleur rendement</div>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 1.3em; font-weight: bold; color: #e74c3c;'>{communes_filtrees['budget_70m2'].min():,.0f}€</div>
                    <div style='color: #7f8c8d;'>Budget le plus bas</div>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 1.3em; font-weight: bold; color: #3498db;'>{communes_filtrees['rendement_brut_%'].mean():.1f}%</div>
                    <div style='color: #7f8c8d;'>Rendement moyen</div>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 1.3em; font-weight: bold; color: #9b59b6;'>{len(communes_filtrees)}</div>
                    <div style='color: #7f8c8d;'>Communes trouvées</div>
                </div>
            </div>
        </div>
        """))

def mettre_a_jour_affichage(change=None):
    budget = budget_slider.value
    rendement = rendement_slider.value
    population = population_slider.value
    departements_selectionnes = list(departement_select.value)
    
    stats, communes_filtrees = appliquer_filtres(budget, rendement, population, departements_selectionnes)
    total_initial = len(df)
    
    with result_output:
        clear_output(wait=True)
        

        display(widgets.HTML(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; margin: 10px 0;'>
            <h2 style='margin: 0;'> {stats['final']:,} COMMUNES TROUVÉES</h2>
            <p style='margin: 5px 0; opacity: 0.9;'>Sur {total_initial:,} communes au total</p>
        </div>
        """))
        
        stats_row = widgets.HBox([
            create_stat_card(f"{stats['final']:,}", "Résultats", "#27ae60"),
            create_stat_card(f"{stats['budget']:,}", "Budget OK", "#3498db"),
            create_stat_card(f"{stats['rendement']:,}", "Rendement OK", "#e74c3c"),
            create_stat_card(f"{stats['departements']:,}", "Départements", "#9b59b6"),
        ], layout=widgets.Layout(justify_content='space-around'))
        display(stats_row)
        
        display(widgets.HTML("<h4 style='color: #2c3e50; margin-top: 20px;'> EFFICACITÉ DES FILTRES</h4>"))
        
        for filtre, count in [('Budget', stats['budget']), ('Rendement', stats['rendement']), ('Population', stats['population']), ('Départements', stats['departements'])]:
            percentage = (count / total_initial) * 100
            color_class = "filter-active" if percentage < 50 else "filter-weak"
            display(widgets.HTML(f"""
            <div class='result-card {color_class}'>
                <div style='display: flex; justify-content: space-between;'>
                    <span>{filtre}</span>
                    <span><strong>{count:,}</strong> communes ({percentage:.1f}%)</span>
                </div>
                <div class='progress-bar'><div class='progress-fill' style='width: {percentage}%'></div></div>
            </div>
            """))
    
    creer_tableau_de_bord_simple(communes_filtrees)


header = widgets.HTML("<h1 style='text-align: center; color: #2c3e50; margin-bottom: 30px;'>🏠 SMART INVESTISSEMENT IMMOBILIER</h1>")

filters_column = widgets.VBox([
    widgets.HTML("<h3 style='color: #2c3e50;'>🎛️ FILTRES</h3>"),
    budget_slider,
    rendement_slider,
    population_slider,
    widgets.HTML("<h4 style='color: #2c3e50; margin-top: 20px;'>🗺️ DÉPARTEMENTS</h4>"),
    departement_select
], layout=widgets.Layout(width='40%', margin='20px'))

results_column = widgets.VBox([result_output], layout=widgets.Layout(width='60%', margin='20px'))

main_layout = widgets.VBox([
    header,
    widgets.HBox([filters_column, results_column]),
    widgets.HTML("<h3 style='color: #2c3e50; margin: 20px 0;'>📊 ANALYSE DÉTAILLÉE</h3>"),
    chart_output
])

for widget in [budget_slider, rendement_slider, population_slider, departement_select]:
    widget.observe(mettre_a_jour_affichage, names='value')

display(widgets.HTML(style))
display(main_layout)
mettre_a_jour_affichage()

import os, sys, json, urllib.request, subprocess
import numpy as np
import pandas as pd


try:
    import folium
    from branca.colormap import LinearColormap
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "folium", "--quiet"])
    import folium
    from branca.colormap import LinearColormap


if 'df_analysis' in globals():
    src = 'df_analysis'
    base = df_analysis.copy()
    base['departement'] = base['departement'].astype(str).str.zfill(2)
    agg = (base.groupby('departement', as_index=False)
           .agg(rendement_moy=('rendement_brut', 'mean'),
                budget_moy=('budget_max_70m2', 'mean'),
                population=('population_total', 'sum'),
                communes=('commune', 'count')))
    rend_col = 'rendement_moy'  # en %
elif 'df' in globals():
    src = 'df'
    base = df.copy()
    base['departement'] = base['departement'].astype(str).str.zfill(2)
    if 'rendement_brut_%' not in base.columns and 'rendement_brut' in base.columns:
        base['rendement_brut_%'] = base['rendement_brut']
    agg = (base.groupby('departement', as_index=False)
           .agg(rendement_moy=('rendement_brut_%', 'mean'),
                budget_moy=('budget_70m2', 'mean'),
                population=('population_total', 'sum'),
                communes=('commune', 'count')))
    rend_col = 'rendement_moy'
else:
    raise RuntimeError("Aucune table `df_analysis` ou `df` trouvée. Exécute d’abord la cellule qui crée tes données.")

dept_centroids = {
    '75': (48.8566, 2.3522),   
    '77': (48.5396, 2.6570),
    '78': (48.8075, 1.7000),
    '91': (48.5295, 2.2480),
    '92': (48.8932, 2.2570),
    '93': (48.9129, 2.4699),
    '94': (48.7749, 2.4499),
    '95': (49.0600, 2.1600),
    '13': (43.4046, 5.2130),   
    '69': (45.7719, 4.8290),   
    '31': (43.6043, 1.4437),   
    '59': (50.4750, 3.2220),  
    '33': (44.8378, -0.5792),  
}


agg_c = agg[agg['departement'].isin(dept_centroids.keys())].copy()
if agg_c.empty:
    raise ValueError("Aucun département de agg ne correspond aux centroïdes fournis. Vérifie les codes (ex: '75','13',...).")

m = folium.Map(location=[46.6, 2.5], zoom_start=5.6, tiles="cartodbpositron")

vmin, vmax = float(agg_c[rend_col].min()), float(agg_c[rend_col].max())
cmap = LinearColormap(colors=['#2DC937','#99C140','#E7B416','#DB7B2B','#CC3232'], vmin=vmin, vmax=vmax)
cmap.caption = "Rendement moyen (%)"
cmap.add_to(m)

pop_min, pop_max = float(agg_c['population'].min()), float(agg_c['population'].max())
def scale_radius(pop):
    if pop_max == pop_min:
        return 10.0
    return float(np.interp(pop, (pop_min, pop_max), (6, 22)))

for _, row in agg_c.iterrows():
    dep = row['departement']
    lat, lon = dept_centroids[dep]
    rdm = row[rend_col]
    pop = row['population']
    communes = int(row['communes'])
    budget = row['budget_moy']

    folium.CircleMarker(
        location=(lat, lon),
        radius=scale_radius(pop),
        fill=True, fill_opacity=0.85, weight=1, color="#333",
        fill_color=cmap(rdm),
        tooltip=folium.Tooltip(
            f"<b>Département {dep}</b><br>"
            f"Rendement moyen: {rdm:.2f}%<br>"
            f"Population totale: {int(pop):,}".replace(",", " ") + "<br>"
            f"Budget moyen (70m²): {budget:,.0f} €".replace(",", " ") + "<br>"
            f"Nb communes: {communes}"
        ),
    ).add_to(m)


from IPython.display import display
display(m)
m.save("carte_bulles_departements.html")
print(" Carte bulles sauvegardée -> carte_bulles_departements.html")

GEO_URL = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson"
geo_path = "departements-version-simplifiee.geojson"
if not os.path.isfile(geo_path):
    urllib.request.urlretrieve(GEO_URL, geo_path)

m2 = folium.Map(location=[46.6, 2.5], zoom_start=5.5, tiles="cartodbpositron")
folium.Choropleth(
    geo_data=geo_path,
    name="Rendement moyen",
    data=agg,
    columns=['departement', rend_col],    
    key_on="feature.properties.code",     
    fill_color="YlGnBu",
    fill_opacity=0.85,
    line_opacity=0.5,
    nan_fill_color="#f0f0f0",
    legend_name="Rendement locatif moyen (%)",
).add_to(m2)

folium.LayerControl().add_to(m2)
display(m2)
m2.save("carte_choropleth_departements.html")
print("Choroplèthe sauvegardée -> carte_choropleth_departements.html")

print(f"Source utilisée: {src} | départements couverts: {len(agg_c)} / {len(agg)}")

import matplotlib.pyplot as plt
import ipywidgets as widgets
import pandas as pd
import numpy as np


if 'df_analysis' in globals():        
    src = 'df_analysis'
    df_widget = df_analysis.copy()
    df_widget['ville'] = df_widget.get('commune', df_widget.index.astype(str))
    df_widget['region'] = df_widget.get('departement', 'NA').astype(str).str.zfill(2) 
    if 'prix_m2' not in df_widget.columns:
        df_widget['prix_m2'] = df_widget.get('prix_m2_moyen', np.nan)
    if 'rendement_brut_%' not in df_widget.columns:
        df_widget['rendement_brut_%'] = df_widget.get('rendement_brut', np.nan)
    if 'chomage_%' not in df_widget.columns:
        df_widget['chomage_%'] = np.nan
    if 'vacance_%' not in df_widget.columns:
        df_widget['vacance_%'] = np.nan

    label_filtre = "Département"
    options_filtre = ['Tous'] + sorted(df_widget['region'].dropna().unique().tolist())

elif 'df' in globals():  
    src = 'df'
    df_widget = df.copy()
    df_widget['ville'] = df_widget.get('commune', df_widget.index.astype(str))
    df_widget['region'] = df_widget.get('departement', 'NA').astype(str).str.zfill(2)
    if 'prix_m2' not in df_widget.columns:
        df_widget['prix_m2'] = df_widget.get('prix_m2_moyen', np.nan)
    if 'rendement_brut_%' not in df_widget.columns:
        df_widget['rendement_brut_%'] = df_widget.get('rendement_brut', np.nan)
    if 'chomage_%' not in df_widget.columns:
        df_widget['chomage_%'] = np.nan
    if 'vacance_%' not in df_widget.columns:
        df_widget['vacance_%'] = np.nan

    label_filtre = "Département"
    options_filtre = ['Tous'] + sorted(df_widget['region'].dropna().unique().tolist())

elif 'data' in globals():   
    src = 'data'
    df_widget = data.copy()
    label_filtre = "Région"
    options_filtre = ['Toutes'] + sorted(df_widget['region'].dropna().unique().tolist())

else:
    raise RuntimeError("Aucune table détectée (df_analysis, df, ou data). Exécute d’abord la cellule qui crée tes données.")


def scatter_geo(region_sel):

    if label_filtre == "Région":
        subset = (df_widget if region_sel == 'Toutes' else df_widget[df_widget['region'] == region_sel])
    else:  
        subset = (df_widget if region_sel == 'Tous' else df_widget[df_widget['region'] == region_sel])


    req_cols = ['prix_m2','rendement_brut_%','chomage_%','vacance_%','ville']
    subset = subset.copy()
    for c in req_cols:
        if c not in subset.columns:
            subset[c] = np.nan

    subset = subset.dropna(subset=['prix_m2','rendement_brut_%'])

    plt.figure(figsize=(12,6))
    if subset.empty:
        plt.text(0.5, 0.5, "Aucune donnée après filtre", ha='center', va='center', fontsize=12)
        plt.axis('off')
        plt.show()
        return

    if subset['vacance_%'].notna().sum() >= 2:
        sizes = np.interp(subset['vacance_%'].fillna(subset['vacance_%'].median()),
                          (subset['vacance_%'].min(), subset['vacance_%'].max()),
                          (50, 300))
    else:
        sizes = np.full(len(subset), 120.0)

    cvals = subset['chomage_%']
    if cvals.notna().any():
        sc = plt.scatter(subset['prix_m2'], subset['rendement_brut_%'],
                         s=sizes, c=cvals, cmap='coolwarm', alpha=0.85, edgecolor='k', linewidths=0.5)
        cbar = plt.colorbar(sc, label='Taux de chômage (%)')
    else:
        sc = plt.scatter(subset['prix_m2'], subset['rendement_brut_%'],
                         s=sizes, c='#808080', alpha=0.85, edgecolor='k', linewidths=0.5)


    max_labels = 40
    for i, row in subset.head(max_labels).iterrows():
        plt.text(row['prix_m2'], row['rendement_brut_%'], str(row['ville']),
                 fontsize=8, alpha=0.8)

    plt.xlabel("Prix au m² (€)")
    plt.ylabel("Rendement brut (%)")
    titre = "Investissement par " + ("ville — Région: " + region_sel if label_filtre=="Région"
                                     else "commune — Département: " + region_sel)
    plt.title(titre)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

widgets.interact(scatter_geo, region_sel=widgets.Dropdown(options=options_filtre, description=f"{label_filtre}:"))
