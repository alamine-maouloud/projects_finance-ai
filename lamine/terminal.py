mkdir lamine && cd lamine
python -m venv .venv
###

python3 -m venv .venv
source .venv/bin/activate
cd ~/lamine
ls -la

###

mkdir -p scripts data tests lamine/core lamine/domains lamine/app (création des dossiers)
###

touch lamine/__init__.py lamine/core/__init__.py lamine/domains/__init__.py lamine/app/__init__.py (création des paquets vide)
###

(Création des fichiers txt et md) 

cat > requirements.txt <<'TXT' 
pandas>=2.1
numpy>=1.26
scikit-learn>=1.4
streamlit>=1.36
matplotlib>=3.8
pyyaml>=6.0
joblib>=1.3
pytest>=8.0
TXT
###



