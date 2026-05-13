# Dashboard AIS — Marine Nationale
## Hackathon Albert 2026 · Sujet 3

Plateforme de surveillance maritime temps réel basée sur le flux AIS mondial (aisstream.io).

## Fichiers

| Fichier | Rôle |
|---------|------|
| `dashboard.py` | Serveur principal — pipeline AIS, détection, HTTP + WebSocket |
| `dashboard.html` | Carte interactive temps réel |
| `dashboard_alertes.html` | Fil d'alertes rouges |
| `dashboard_suspects.html` | Navires suspects + loitering |
| `dashboard_sts.html` | Transferts STS (Ship-to-Ship) |
| `dashboard_settings.html` | Paramètres de détection ajustables en live |
| `dashboard_clean.html` | Navires sans alerte |
| `stats.html` | Statistiques sur 6 heures |
| `fetch_sanctions.py` | Mise à jour de la base de sanctions |
| `realtime_pipeline.py` | Pipeline temps réel standalone |
| `regenerate_radio_profiles.py` | Regénération des profils radio |
| `sanctions_real.csv` | Base de sanctions consolidée (11 081 navires — OFAC, ONU, UK, OpenSanctions) |
| `ship_radio_profiles.csv` | Profils radio aggrégés par navire |
| `watchlist.txt` | MMSI / IMO sous surveillance opérationnelle |
| `DOCUMENTATION.md` | Documentation technique complète |

## Installation

```bash
pip3 install pandas websockets aiohttp
```

## Lancement

```bash
# Libérer les ports si nécessaire
lsof -ti TCP:8080 | xargs kill -9 2>/dev/null
lsof -ti TCP:8765 | xargs kill -9 2>/dev/null

# Démarrer le serveur
python3 dashboard.py
```

## Accès

| Interface | URL |
|-----------|-----|
| Carte temps réel | http://localhost:8080/dashboard.html |
| Alertes | http://localhost:8080/dashboard_alertes.html |
| Suspects | http://localhost:8080/dashboard_suspects.html |
| STS | http://localhost:8080/dashboard_sts.html |
| Statistiques | http://localhost:8080/stats.html |
| Paramètres | http://localhost:8080/dashboard_settings.html |

## Architecture

```
aisstream.io (WebSocket)
      ↓
dashboard.py
  ├── ais_pipeline()         — Analyse chaque signal AIS (6 checks)
  ├── dark_shipping_monitor()— Détecte les coupures AIS suspectes (60s)
  └── detection_monitor()    — Détecte STS + loitering (60s)
      ↓
WebSocket :8765 → navigateurs
HTTP     :8080  → pages HTML + API REST
```

## Capacités de détection

| Type | Alerte | Description |
|------|--------|-------------|
| WATCHLIST_HIT | 🔴 Rouge | Cible connue de la watchlist opérateur |
| DARK_SHIPPING | 🔴 Rouge | AIS coupé depuis > 15 min |
| STS_DETECTED | 🔴 Rouge | Deux navires à < 500 m depuis > 3 min |
| DARK_REAPPEARANCE | 🔴 Rouge | Réapparition avec saut de position inexpliqué |
| FLAG_MISMATCH | 🔴 Rouge | Pavillon sanctionné ≠ nationalité MMSI |
| SANCTION_* | 🟠/🔴 | Navire dans base de sanctions internationale |
| LOITERING | 🟠 Orange | Errance prolongée dans rayon 5 km |
| SPEED_IMPOSSIBLE | 🟠 Orange | Vitesse > 50 kt — spoofing probable |
| HIGH_RISK_ZONE | 🟠 Orange | Présence dans zone classée à risque |
| RADIO_CFO_DERIVE | 🟠 Orange | Empreinte RF suspecte — clonage MMSI |

Documentation complète : [DOCUMENTATION.md](DOCUMENTATION.md)
