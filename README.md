# Metrology tools

## Prérequis
- Python 3.10 ou supérieur
- `git`

## Installation
```bash
git clone <URL_DU_DEPOT>
cd met-tools
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Exemple d’usage
Générer le graphique des temps de chargement:
```bash
python 24_data/process_data.py
```

Géolocaliser IPv4 routeurs vers fandom.com:
```bash
python geoloc/get_loc_ipv4.py
```

## Mise à jour des dépendances
```bash
pip install -U -r requirements.txt
```
