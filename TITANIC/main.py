import os
import pandas as pd
import numpy as np
import re
import re

import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.ensemble import ExtraTreesClassifier

from sklearn.model_selection import StratifiedKFold
from collections import defaultdict
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import accuracy_score
from scipy.stats import randint, uniform

# Base learners
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
# --- SAFETY RESET (à exécuter si 'train'/'test' ne sont pas encore définis) ---


# chemins VS Code
DATA_DIR = 'data'
TRAIN_PATH = os.path.join(DATA_DIR, 'train.csv')
TEST_PATH  = os.path.join(DATA_DIR, 'test.csv')
assert os.path.exists(TRAIN_PATH) and os.path.exists(TEST_PATH), "Place train.csv et test.csv dans ./data/"

# charge les données si besoin
if 'train' not in globals():
    train = pd.read_csv(TRAIN_PATH)
if 'test' not in globals():
    test  = pd.read_csv(TEST_PATH)

print("Train/Test chargés :", train.shape, test.shape)

# Your EDA code here. 
# Examples: 
# - train_df.info()
# - train_df.describe()
# - sns.countplot(x='Survived', data=train_df)
# - sns.catplot(x='Sex', col='Survived', kind='count', data=train_df)
train.info()
train.describe()
X_full = train_te[num_feats].copy()

X_full['Sex_num'] = (train['Sex'] == 'female').astype(int)
X_full['Embarked_num'] = (
    train['Embarked']
    .map({'S': 0, 'C': 1, 'Q': 2})
    .fillna(-1)
    .astype(int)
)

# y = label cible
y = train_te['Survived'].astype(int)

# ------------------------------------------------------------------
# 3.1 Corrélations numériques (Pearson) sur toutes les colonnes numériques de X_full
# ------------------------------------------------------------------
num_cols = X_full.select_dtypes(include=[np.number]).columns.tolist()
corr_num = X_full[num_cols].corr(method="pearson")

plt.figure(figsize=(14, 10))
sns.heatmap(corr_num.abs(), cmap="viridis", center=0, annot=False)
plt.title("Heatmap corrélation (Pearson) — toutes les features numériques")
plt.show()

plot_df = pd.DataFrame({
    "Age":       train_fe_base["Age"].fillna(train_fe_base["Age"].median()).values,
    "Fare":      train_fe_base["Fare"].fillna(train_fe_base["Fare"].median()).values,
    "Survived":  train["Survived"].values,
    "Sex":       train["Sex"].values,   # 'male'/'female'
    "Pclass":    train_fe_base["Pclass"].values
})

plt.figure(figsize=(10, 6))
sns.scatterplot(data=plot_df, x="Age", y="Fare", hue="Survived", style="Sex", alpha=0.6)
plt.title("Interaction Age, Fare, Sexe vs Survie")
plt.show()

plt.figure(figsize=(10, 6))
sns.scatterplot(data=plot_df, x="Age", y="Pclass", hue="Survived", alpha=0.5)
plt.title("Interaction Age × Pclass vs Survie")
plt.ylabel("Pclass")
plt.show()


# Your data cleaning and feature engineering code here.
# Examples:
# - Handle missing 'Age' values
# - Convert 'Sex' to numerical values
# - Create a 'FamilySize' feature


RANDOM_STATE = 42

def extract_title(name: str) -> str:
    if pd.isna(name): 
        return 'Unknown'
    m = re.search(r",\s*([^\.]+)\.", str(name))
    t = m.group(1).strip() if m else 'Unknown'
    mapping = {
        'Mlle':'Miss','Ms':'Miss','Mme':'Mrs',
        'Lady':'Royal','Countess':'Royal','Sir':'Royal','Don':'Royal','Dona':'Royal','Jonkheer':'Royal','the Countess':'Royal',
        'Capt':'Officer','Col':'Officer','Major':'Officer','Dr':'Officer','Rev':'Officer'
    }
    return mapping.get(t, t)

def ticket_prefix(ticket: str) -> str:
    if pd.isna(ticket): return 'UNK'
    t = re.sub(r"\.", "", str(ticket)).replace("/", " ")
    parts = [p for p in t.split() if not p.isdigit()]
    return parts[0].upper() if parts else 'NUM'

def cabin_deck(cabin: str) -> str:
    if pd.isna(cabin): return 'U'
    return str(cabin).split()[0][0]

def multi_cabin(cabin: str) -> int:
    if pd.isna(cabin): return 0
    return 1 if len(str(cabin).split()) > 1 else 0

def surname(name: str) -> str:
    if pd.isna(name): return 'UNK'
    return str(name).split(',')[0].strip().upper()

def preprocess_base(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Fill Embarked (mode global)
    if out['Embarked'].isna().any():
        out['Embarked'] = out['Embarked'].fillna(out['Embarked'].mode(dropna=True).iloc[0])

    # Title / Family / Ticket / Cabin basics
    out['Title']   = out['Name'].apply(extract_title)
    out['Surname'] = out['Name'].apply(surname)
    out['FamilySize'] = out['SibSp'] + out['Parch'] + 1
    out['IsAlone'] = (out['FamilySize'] == 1).astype(int)
    counts_ticket = out['Ticket'].value_counts()
    out['TicketGroupSize'] = out['Ticket'].map(counts_ticket).clip(1, 10)  # cap
    out['TicketIsShared'] = (out['TicketGroupSize'] > 1).astype(int)
    out['TicketPrefix'] = out['Ticket'].apply(ticket_prefix)
    out['CabinDeck'] = out['Cabin'].apply(cabin_deck)
    out['CabinMissing'] = out['Cabin'].isna().astype(int)
    out['CabinMulti'] = out['Cabin'].apply(multi_cabin)

    # FamilyID = Surname + TicketPrefix (plus robuste que Surname seul)
    out['FamilyID'] = (out['Surname'] + '_' + out['TicketPrefix']).astype('category')

    # Fill Fare by class median, then log1p
    if out['Fare'].isna().any():
        out['Fare'] = out.groupby('Pclass')['Fare'].transform(lambda s: s.fillna(s.median()))
    out['Fare'] = out['Fare'].fillna(out['Fare'].median())
    out['FarePP'] = out['Fare'] / out['FamilySize'].replace(0, 1)
    out['Fare_log1p'] = np.log1p(out['Fare'])

    # Age imputation par groupe (Title, Pclass, Sex, Embarked)
    grp = out.groupby(['Title','Pclass','Sex','Embarked'])['Age'].transform('median')
    out['Age'] = out['Age'].fillna(grp)
    out['Age'] = out['Age'].fillna(out['Age'].median())
    out['AgeMissing'] = df['Age'].isna().astype(int)

    # Bins / interactions utiles
    out['AgeBin'] = pd.cut(out['Age'], bins=[-1, 12, 18, 25, 35, 45, 60, 80], labels=False)
    out['Sex_is_female'] = (out['Sex'] == 'female').astype(int)
    out['PclassSex'] = out['Pclass'] * (out['Sex_is_female']*2 - 1)
    out['AgePclass'] = out['Age'] * out['Pclass']

    # Role familiales
    out['Child'] = (out['Age'] < 16).astype(int)
    out['Mother'] = ((out['Sex'] == 'female') & (out['Parch'] > 0) & (out['Title'].isin(['Mrs','Miss'])==False)).astype(int)

    return out

train_fe_base = preprocess_base(train)
test_fe_base  = preprocess_base(test)

print("Base FE -> Train:", train_fe_base.shape, " Test:", test_fe_base.shape)

# Colonnes à target-encoder (cardinalité > 2 et corrélées au label)
te_cols = ['Title','TicketPrefix','CabinDeck','FamilyID']

def oof_target_encode(train_df, test_df, y, cols, n_splits=5, smoothing=50):
    """
    OOF target encoding: moyenne de Survived par catégorie, calculée en KFold sur le train,
    puis mappée au test. 'smoothing' réduit le bruit pour les catégories rares.
    """
    train_enc = train_df.copy()
    test_enc  = test_df.copy()

    global_mean = y.mean()
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)

    for col in cols:
        oof_vals = np.zeros(len(train_df))
        for tr_idx, va_idx in skf.split(train_df, y):
            tr_mean = (
                train_df.iloc[tr_idx]
                .assign(_y=y.iloc[tr_idx].values)
                .groupby(col)['_y']
                .agg(['mean','count'])
            )
            # smoothing de la moyenne
            tr_mean['te'] = (tr_mean['mean']*tr_mean['count'] + global_mean*smoothing) / (tr_mean['count'] + smoothing)
            mapping = tr_mean['te']
            oof_vals[va_idx] = train_df.iloc[va_idx][col].map(mapping).fillna(global_mean).values

        # fit sur tout le train pour encoder le test
        full = (
            train_df
            .assign(_y=y.values)
            .groupby(col)['_y']
            .agg(['mean','count'])
        )
        full['te'] = (full['mean']*full['count'] + global_mean*smoothing) / (full['count'] + smoothing)
        test_mapping = full['te']

        train_enc[f'TE_{col}'] = oof_vals
        test_enc[f'TE_{col}']  = test_df[col].map(test_mapping).fillna(global_mean)

    return train_enc, test_enc

train_te, test_te = oof_target_encode(train_fe_base, test_fe_base, train_fe_base['Survived'], te_cols, n_splits=5, smoothing=50)
print("TE columns added:", [f'TE_{c}' for c in te_cols])

# Catégorielles simples à OHE (faible cardinalité)
ohe_simple = ['Sex','Embarked']

num_feats = [
    'Pclass','Age','SibSp','Parch','Fare','FarePP','Fare_log1p',
    'FamilySize','IsAlone','TicketGroupSize','TicketIsShared',
    'CabinMissing','CabinMulti','AgeMissing','AgePclass','PclassSex','Child','Mother','AgeBin'
] + [f'TE_{c}' for c in te_cols]

FEATURES_TE = num_feats + ohe_simple  # OHE sera appliqué seulement à ohe_simple

X = train_te[FEATURES_TE].copy()
y = train_te['Survived'].copy()
X_test = test_te[FEATURES_TE].copy()



numeric_cols = [c for c in num_feats]  # déjà numériques
categorical_cols = ohe_simple          # petites catégories

numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler(with_mean=False))
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=True))
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_cols),
        ('cat', categorical_transformer, categorical_cols)
    ]
)

print("Total features (before OHE expansion):", len(FEATURES_TE))

# Your model training code here.
# Examples:
# - from sklearn.model_selection import train_test_split
# - from sklearn.linear_model import LogisticRegression
# - Define features (X) and target (y)
# - Split data, train model, check accuracy



has_xgb, has_lgbm = False, False
try:
    from xgboost import XGBClassifier
    has_xgb = True
except:
    pass
try:
    from lightgbm import LGBMClassifier
    has_lgbm = True
except:
    pass

candidates = {}

candidates['RF'] = Pipeline([
    ('pre', preprocessor),
    ('clf', RandomForestClassifier(random_state=RANDOM_STATE))
])

candidates['GBC'] = Pipeline([
    ('pre', preprocessor),
    ('clf', GradientBoostingClassifier(random_state=RANDOM_STATE))
])

candidates['SVC'] = Pipeline([
    ('pre', preprocessor),
    ('clf', SVC(probability=True, kernel='rbf', random_state=RANDOM_STATE))
])

candidates['LR'] = Pipeline([
    ('pre', preprocessor),
    ('clf', LogisticRegression(max_iter=1000, C=1.0, solver='lbfgs', random_state=RANDOM_STATE))
])

if has_xgb:
    candidates['XGB'] = Pipeline([
        ('pre', preprocessor),
        ('clf', XGBClassifier(
            objective='binary:logistic', eval_metric='logloss',
            n_jobs=-1, random_state=RANDOM_STATE
        ))
    ])

if has_lgbm:
    candidates['LGBM'] = Pipeline([
        ('pre', preprocessor),
        ('clf', LGBMClassifier(n_jobs=-1, random_state=RANDOM_STATE))
    ])

# RandomizedSearch grids
param_spaces = {
    'RF': {
        'clf__n_estimators': randint(400, 1200),
        'clf__max_depth': randint(3, 12),
        'clf__min_samples_split': randint(2, 10),
        'clf__min_samples_leaf': randint(1, 6),
        'clf__max_features': ['sqrt','log2', None],
    },
    'GBC': {
        'clf__n_estimators': randint(200, 900),
        'clf__learning_rate': uniform(0.01, 0.15),
        'clf__max_depth': randint(2, 5),
        'clf__subsample': uniform(0.7, 0.3),
    },
    'SVC': {
        'clf__C': uniform(0.2, 5.0),
        'clf__gamma': ['scale'] + list(np.logspace(-3, -1, 5)),
        'clf__kernel': ['rbf'],
    },
    'LR': {
        'clf__C': uniform(0.2, 3.0),
        'clf__penalty': ['l2'],
        'clf__solver': ['lbfgs','liblinear']
    }
}

if has_xgb:
    param_spaces['XGB'] = {
        'clf__n_estimators': randint(300, 1200),
        'clf__max_depth': randint(3, 6),
        'clf__learning_rate': uniform(0.01, 0.2),
        'clf__subsample': uniform(0.7, 0.3),
        'clf__colsample_bytree': uniform(0.7, 0.3),
        'clf__reg_alpha': uniform(0.0, 0.5),
        'clf__reg_lambda': uniform(0.5, 1.0),
    }

if has_lgbm:
    param_spaces['LGBM'] = {
        'clf__n_estimators': randint(400, 1600),
        'clf__learning_rate': uniform(0.01, 0.2),
        'clf__num_leaves': randint(15, 63),
        'clf__subsample': uniform(0.7, 0.3),
        'clf__colsample_bytree': uniform(0.7, 0.3),
        'clf__reg_alpha': uniform(0.0, 0.5),
        'clf__reg_lambda': uniform(0.0, 1.0),
    }

skf = StratifiedKFold(n_splits=10, shuffle=True, random_state=RANDOM_STATE)

best_models = {}
for name, pipe in candidates.items():
    n_iter = 60 if name in ['XGB','LGBM'] else 40
    params = param_spaces.get(name, {})
    if not params:  # pas de RS pour LR simple etc. => fit direct + CV internal
        rs = None
        pipe.fit(X, y)  # simple fit
        scores = cross_val_score(pipe, X, y, cv=skf, scoring='accuracy', n_jobs=-1)
        best_models[name] = (pipe, scores.mean())
        print(f"{name} CV acc: {scores.mean():.4f}")
        continue

    rs = RandomizedSearchCV(
        estimator=pipe,
        param_distributions=params,
        n_iter=n_iter,
        scoring='accuracy',
        cv=skf,
        n_jobs=-1,
        random_state=RANDOM_STATE,
        verbose=0
    )
    rs.fit(X, y)
    best_models[name] = (rs.best_estimator_, rs.best_score_)
    print(f"{name} best CV acc: {rs.best_score_:.4f} | best params: {rs.best_params_}")

# Choisir top-3 pour le stacking
sorted_base = sorted(best_models.items(), key=lambda kv: kv[1][1], reverse=True)
top3 = [(k, v[0]) for k,v in sorted_base[:3]]
print("Top-3 for stack:", [k for k,_ in top3])

from sklearn.ensemble import StackingClassifier, VotingClassifier

estimators = [(name, mdl) for name, mdl in top3]

stack = StackingClassifier(
    estimators=estimators,
    final_estimator=LogisticRegression(max_iter=1000, C=1.0, solver='lbfgs', random_state=RANDOM_STATE),
    n_jobs=-1,
    passthrough=False
)

vote = VotingClassifier(estimators=estimators, voting='soft')

def cv_proba(model, X, y, cv):
    """Retourne OOF proba + score moyen."""
    oof = np.zeros(len(X))
    scores = []
    for tr, va in cv.split(X, y):
        Xtr, Xva = X.iloc[tr], X.iloc[va]
        ytr, yva = y.iloc[tr], y.iloc[va]
        m = model
        m.fit(Xtr, ytr)
        p = m.predict_proba(Xva)[:,1]
        oof[va] = p
        preds = (p >= 0.5).astype(int)
        scores.append(accuracy_score(yva, preds))
    return oof, np.mean(scores)

# Compare stack vs vote
oof_stack, acc_stack = cv_proba(stack, X, y, skf)
oof_vote,  acc_vote  = cv_proba(vote,  X, y, skf)
print(f"Stack 10-fold acc@0.5: {acc_stack:.4f}")
print(f"Vote  10-fold acc@0.5: {acc_vote:.4f}")

best_model = stack if acc_stack >= acc_vote else vote
oof, _ = (oof_stack, acc_stack) if best_model is stack else (oof_vote, acc_vote)

# Optimisation du seuil sur l'OOF (peut gratter ~0.002–0.01)
ths = np.linspace(0.35, 0.7, 71)
accs = [(t, accuracy_score(y, (oof >= t).astype(int))) for t in ths]
t_best, acc_best = max(accs, key=lambda x: x[1])
print(f"Best threshold on OOF: {t_best:.3f} → acc {acc_best:.4f}")

# Your submission generation code here.
# - Process the test_df in the same way as train_df
# - model.predict(X_test)
# - Create a submission DataFrame and save to 'submission.csv'
# Fit sur tout le train
best_model.fit(X, y)

# Probas test + seuil optimisé
test_proba = best_model.predict_proba(X_test)[:,1]
test_pred = (test_proba >= t_best).astype(int)

submission = pd.DataFrame({
    'PassengerId': test['PassengerId'],
    'Survived': test_pred
})
submission.to_csv('submission.csv', index=False)
print("Saved submission.csv")
submission.head()







