# Réponses aux Questions — Hackathon Albert 2026 · Sujet 3

Ce dossier contient les réponses complètes aux deux parties du sujet.

## Structure

```
RéponsesQuest/
├── MiseEnJambe/
│   └── reponses_mise_en_jambe.py        ← Réponses Q1–Q12 (exploration + liens + visualisations)
│
└── Generalisation/
    ├── solutions_generalisation.ipynb   ← Notebook principal — réponses Q1–Q14
    ├── solutions_generalisation.py      ← Version script Python des réponses
    ├── analyse_generalisation.ipynb     ← Analyses complémentaires
    ├── RAPPORT_PIPELINE.md              ← Rapport technique du pipeline
    └── q1_*.png … q13_*.png             ← Visualisations générées
```

## Données requises

Les scripts s'appuient sur les fichiers CSV fournis dans `SujetsHackathon2026/Sujet3/` :
- `MiseEnJambe/` : `ships_small.csv`, `radio_signatures_small.csv`, `ais_data_small.csv`
- `Généralisation/` : `ships_large.csv`, `radio_signatures_large.csv`, `ais_data_large.csv`, `anomalies_large.csv`

## Lancement

```bash
# Mise en Jambe
cd RéponsesQuest/MiseEnJambe
python3 reponses_mise_en_jambe.py

# Généralisation (notebook)
cd RéponsesQuest/Generalisation
jupyter notebook solutions_generalisation.ipynb
```
