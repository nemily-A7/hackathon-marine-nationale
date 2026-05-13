# Documentation technique — Système de surveillance AIS Marine Nationale
## Hackathon Albert 2026 — Sujet 3

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture système](#2-architecture-système)
3. [Structure des fichiers](#3-structure-des-fichiers)
4. [Backend — dashboard.py](#4-backend--dashboardpy)
   - 4.1 [Démarrage et persistance SQLite](#41-démarrage-et-persistance-sqlite)
   - 4.2 [Chargement des données statiques](#42-chargement-des-données-statiques)
   - 4.3 [Structures de données en mémoire](#43-structures-de-données-en-mémoire)
   - 4.4 [Modèle radio ITU-R M.1371-5](#44-modèle-radio-itu-r-m1371-5)
   - 4.5 [Pipeline AIS — ais_pipeline()](#45-pipeline-ais--ais_pipeline)
   - 4.6 [Checks d'analyse par navire](#46-checks-danalyse-par-navire)
   - 4.7 [Moniteur dark shipping](#47-moniteur-dark-shipping)
   - 4.8 [Moniteur STS + loitering](#48-moniteur-sts--loitering)
   - 4.9 [Système de score et niveaux d'alerte](#49-système-de-score-et-niveaux-dalerte)
   - 4.10 [Déduplication des broadcasts](#410-déduplication-des-broadcasts)
   - 4.11 [API HTTP](#411-api-http)
5. [Base de sanctions (sanctions_real.csv)](#5-base-de-sanctions-sanctions_realcsv)
6. [Watchlist opérateur (watchlist.txt)](#6-watchlist-opérateur-watchlisttxt)
7. [Configuration live (CONFIG)](#7-configuration-live-config)
8. [Codes d'alerte — référence complète](#8-codes-dalerte--référence-complète)
9. [Format des événements WebSocket](#9-format-des-événements-websocket)
10. [Pages frontend](#10-pages-frontend)
11. [Dépendances et lancement](#11-dépendances-et-lancement)

---

## 1. Vue d'ensemble

Le système est une plateforme de surveillance maritime en temps réel qui :

1. **Ingère** le flux AIS mondial via WebSocket (aisstream.io)
2. **Analyse** chaque signal reçu à travers 6 checks comportementaux enchaînés
3. **Détecte** en parallèle les comportements suspects via deux moniteurs asynchrones (dark shipping, STS/loitering)
4. **Diffuse** tous les événements via WebSocket aux tableaux de bord connectés
5. **Persiste** les alertes dans une base SQLite locale

Le système fonctionne entièrement en mémoire pour les données live, SQLite uniquement pour l'historique.

---

## 2. Architecture système

```
                         ┌─────────────────────────────────┐
                         │         aisstream.io             │
                         │   WebSocket flux AIS mondial     │
                         └──────────────┬──────────────────┘
                                        │ wss://
                         ┌──────────────▼──────────────────┐
                         │          dashboard.py            │
                         │                                  │
                         │  ┌─────────────────────────┐    │
                         │  │   ais_pipeline()         │    │
                         │  │   (asyncio coroutine)    │    │
                         │  └──────────┬──────────────┘    │
                         │             │ 6 checks / signal  │
                         │  ┌──────────▼──────────────┐    │
                         │  │  dark_shipping_monitor() │    │
                         │  │   (toutes les 60 s)      │    │
                         │  └──────────┬──────────────┘    │
                         │             │                    │
                         │  ┌──────────▼──────────────┐    │
                         │  │   detection_monitor()    │    │
                         │  │   STS + Loitering 60 s   │    │
                         │  └──────────┬──────────────┘    │
                         │             │                    │
                         │  ┌──────────▼──────────────┐    │
                         │  │     broadcast()          │    │
                         │  │   WebSocket → clients    │    │
                         │  └─────────────────────────┘    │
                         │                                  │
                         │  HTTP :8080   WebSocket :8765    │
                         └──────────────────────────────────┘
                                        │
               ┌────────────────────────┼───────────────────────┐
               │                        │                       │
    ┌──────────▼────────┐  ┌────────────▼────────┐  ┌──────────▼──────────┐
    │  dashboard.html   │  │ dashboard_alertes   │  │  dashboard_sts.html  │
    │  Carte temps réel │  │ Alertes rouge/orange│  │  Transferts STS      │
    └───────────────────┘  └─────────────────────┘  └─────────────────────┘
    ┌───────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
    │ dashboard_suspects│  │     stats.html       │  │ dashboard_settings  │
    │ Suspects/loitering│  │  Statistiques 6h     │  │ Paramètres live     │
    └───────────────────┘  └─────────────────────┘  └─────────────────────┘
```

**Ports :**
- `8080` — Serveur HTTP (pages HTML + API REST)
- `8765` — WebSocket (flux d'événements temps réel vers les navigateurs)

---

## 3. Structure des fichiers

| Fichier | Rôle |
|---------|------|
| `dashboard.py` | Serveur principal — pipeline AIS, détection, HTTP, WebSocket |
| `dashboard.html` | Carte interactive temps réel (Leaflet.js) |
| `dashboard_alertes.html` | Fil d'alertes rouge + orange |
| `dashboard_suspects.html` | Navires suspects + loitering |
| `dashboard_sts.html` | Transferts STS confirmés |
| `dashboard_settings.html` | Panneau de configuration des seuils |
| `stats.html` | Statistiques et graphiques (6 dernières heures) |
| `dashboard_clean.html` | Navires sans alerte uniquement |
| `sanctions_real.csv` | Base de sanctions consolidée (11 081 navires) |
| `watchlist.txt` | Liste MMSI/IMO sous surveillance opérationnelle |
| `alerts.db` | SQLite — historique persistant des alertes |
| `fetch_sanctions.py` | Script de mise à jour de sanctions_real.csv |
| `ship_radio_profiles.csv` | Profils radio historiques (non utilisé en live) |

---

## 4. Backend — dashboard.py

### 4.1 Démarrage et persistance SQLite

À l'import, `_init_db()` crée la table `events` si elle n'existe pas :

```sql
CREATE TABLE IF NOT EXISTS events (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    mmsi               TEXT    NOT NULL,
    name               TEXT,
    alert_level        TEXT,        -- 'green', 'orange', 'red'
    alert_codes        TEXT,        -- JSON array de codes ex: ["WATCHLIST_HIT","LOITERING"]
    alerts_json        TEXT,        -- JSON array de labels lisibles
    alert_details_json TEXT,        -- JSON array d'objets {code, label, detail}
    lat                REAL,
    lon                REAL,
    ts                 TEXT         -- 'HH:MM:SS'
)
```

Index sur `ts` et `alert_level` pour les requêtes `/api/history`.

`db_insert(event)` est appelé pour tout événement `orange` ou `red` non supprimé par déduplication. Protégé par `_db_lock` (threading.Lock) pour sécuriser l'accès concurrent depuis le thread HTTP et la coroutine asyncio.

---

### 4.2 Chargement des données statiques

**Source AIS :**
```python
API_KEY = "caae13ac0e37a4c0b6721666f74396b938c5b670"
WS_URL  = "wss://stream.aisstream.io/v0/stream"
```

**Sanctions (`sanctions_real.csv`) :**
Chargé avec pandas au démarrage. Trois index construits :
- `sanctioned_imo_map`  : `{imo_str: row}`
- `sanctioned_mmsi_map` : `{mmsi_str: row}`
- `sanctioned_names`    : `{set of uppercase names}`

Colonnes du CSV : `name, flag, program, imo, mmsi, source, risk_category`

Catégories de risque présentes : `sanction` (2437), `psc_detained` (6130), `poi` (1479), `flagged` (837), `reg_warning` (101), `shadow_fleet` (97).

**MID → Pavillon (`MID_CODES`) :**
Dictionnaire de 100+ codes MID (préfixe 3 chiffres du MMSI) vers emoji drapeau + nom de pays.  
Source : table ITU des Maritime Identification Digits.

**MID → ISO2 (`MID_TO_ISO2`) :**
Sous-ensemble des MID vers code ISO2 pour la détection FLAG_MISMATCH.  
Ex : `228 → 'fr'`, `273 → 'ru'`, `431 → 'jp'`.

**Zones à risque (`HIGH_RISK_ZONES`) :**
7 zones définies par bounding box lat/lon :

| Zone | Raison |
|------|--------|
| Golfe de Guinée | Piraterie active — IMB High |
| Golfe Persique / Iran | Sanctions Iran, pétrole illicite |
| Bab-el-Mandeb / Mer Rouge sud | Attaques Houthis 2024-2025 |
| Mer Rouge nord | Zone de conflit actif |
| Détroit de Malacca | Piraterie, contrebande |
| Eaux nord-coréennes | Sanctions DPRK |
| Côtes somaliennes | Piraterie — reprise 2023 |

**Vitesses max par type (`MAX_SPEED_KT`) :**

| Type | Max (kt) |
|------|----------|
| Cargo | 25 |
| Tanker | 20 |
| Passenger | 38 |
| Fishing | 18 |
| Tug | 15 |
| Pleasure | 40 |
| Unknown | 35 |

---

### 4.3 Structures de données en mémoire

| Variable | Type | Contenu |
|----------|------|---------|
| `positions_history` | `dict[mmsi → {lat, lon, ts, sog, cog}]` | Dernière position connue par navire |
| `trail_history` | `dict[mmsi → list[(lat, lon)]]` | 15 derniers points de trajectoire |
| `ship_cache_global` | `dict[mmsi → {name, imo, type}]` | Infos statiques (ShipStaticData) |
| `loiter_history` | `dict[mmsi → deque[(lat, lon, ts_float)]]` | Fenêtre glissante 3h pour loitering |
| `loitering_alerted` | `dict[mmsi → ts_float]` | Timestamp de la dernière alerte loitering |
| `sts_proximity` | `dict[frozenset({m1,m2}) → {count, first_ts, alerted, ...}]` | Paires en cours de suivi STS |
| `dark_ships` | `dict[mmsi → {lat, lon, ts, sog, cog}]` | Navires actuellement dark |
| `last_broadcast` | `dict[mmsi → {codes: frozenset, ts: float}]` | Cache de déduplication |
| `live_profiles` | `dict[mmsi → {cfo_ref, name, first_seen, count}]` | Empreintes radio live |
| `alert_log` | `list[{ts, level, types, zone}]` | Journal 6h pour stats temps réel |
| `connected_clients` | `set[WebSocket]` | Navigateurs connectés en ce moment |

---

### 4.4 Modèle radio ITU-R M.1371-5

La fonction `radio_fingerprint(mmsi, ship_type, lat, lon)` calcule une signature radio simulée cohérente avec le standard ITU-R M.1371-5.

**Pourquoi simulé ?**  
aisstream.io ne transmet pas les paramètres physiques radio (RSSI, CFO...). Ils sont recalculés à partir du MMSI et de la position pour détecter des anomalies logiques.

**Paramètres physiques fixes :**

| Constante | Valeur | Signification |
|-----------|--------|---------------|
| `AIS_CH87B_MHZ` | 161.975 MHz | Canal AIS primaire |
| `AIS_CH88B_MHZ` | 162.025 MHz | Canal AIS secondaire |
| `AIS_BW_KHZ` | 25 kHz | Largeur de bande GMSK BT=0.4 |
| `AIS_PWR_CLASS_A` | 12.5 W | Navires commerciaux (Class A) |
| `AIS_PWR_CLASS_B` | 2.0 W | Pêche, plaisance, remorqueurs |
| `SAT_SLANT_KM` | 900 km | Portée oblique satellite LEO nominale |
| `SAT_GAIN_DBI` | 20 dBi | Gain antenne satellite parabolique |
| `RX_NF_DB` | 4 dB | Facteur de bruit récepteur |

**Calcul du canal :** `Ch87 si MMSI pair, Ch88 si MMSI impair`

**CFO (Carrier Frequency Offset) :**
Chaque transpondeur a une imperfection d'oscillateur TCXO unique et stable.  
Modèle : `CFO = gauss(0, 108 Hz)` avec seed déterministe `MMSI XOR 0xA15ACA1`.  
1 ppm de dérive sur 162 MHz = 162 Hz → std 108 Hz cohérent.  
Bruit de mesure : `±8 Hz` ajouté à chaque mesure.

**RSSI (formule de Friis) :**
```
Pt_dBm = 10 × log10(puissance_W × 1000)
FSPL   = 20×log10(slant_km) + 20×log10(freq_MHz) + 32.45
RSSI_nom = Pt_dBm − FSPL + 2.15 (dBi dipôle) + 20 (dBi satellite)
RSSI_mes = RSSI_nom + gauss(0, 6)  ← scintillation atmosphérique VHF
```

**Plancher de bruit :**
```
N = −174 dBm/Hz + 10×log10(25 000 Hz) + 4 dB ≈ −126 dBm
SNR = RSSI_mesuré − N
```

**Sortie de `radio_fingerprint()` :**

| Champ | Description |
|-------|-------------|
| `frequency` | Fréquence mesurée (MHz) avec dérive CFO |
| `bandwidth` | Largeur de bande mesurée (~25 kHz ± 0.3) |
| `power` | Puissance d'émission (W) |
| `signal_to_noise_ratio` | SNR (dB) |
| `rssi_dbm` | RSSI mesuré (dBm) |
| `rssi_nominal_dbm` | RSSI sans fading (référence) |
| `dist_km` | Portée oblique satellite utilisée |
| `channel` | 87 ou 88 |
| `cfo_hz` | CFO mesuré (bruité ±8 Hz) |
| `cfo_true_hz` | CFO de référence (stable par MMSI) |

---

### 4.5 Pipeline AIS — ais_pipeline()

Coroutine asyncio principale. Se connecte en WebSocket à aisstream.io avec souscription mondiale :

```python
{
    "APIKey": "...",
    "BoundingBoxes": [[[-90, -180], [90, 180]]],
    "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
}
```

**Traitement `ShipStaticData` :**  
Met à jour `ship_cache_global[mmsi]` avec `{name, imo, type}`. Ne déclenche pas d'analyse.

**Traitement `PositionReport` :**  
Extrait `mmsi, lat, lon, sog (vitesse), cog (cap)`, puis enchaîne les 6 checks détaillés en §4.6.

En cas de déconnexion, reconnexion automatique après 5 secondes.

---

### 4.6 Checks d'analyse par navire

Exécutés séquentiellement pour chaque PositionReport. Chaque check peut ajouter un objet `{code, label, detail}` à `alert_details`.

#### Check 0a — Dark Reappearance (pré-analyse)
Avant tout, vérifie si le navire était dark (`dark_ships.pop(mmsi)`).  
Si dark depuis > `CONFIG['dark_reapp_min_h']` (défaut : 1h) :
1. Calcule la position **extrapolée** selon le dernier cap (COG) et la dernière vitesse (SOG)
2. Calcule `jump_km` = distance entre position extrapolée et position réelle
3. Calcule `max_drift_km = SOG × 1.852 × dark_h × 3` (dérive maximale tolérable × 3)
4. Si `jump_km > CONFIG['dark_reapp_jump_km']` (défaut : 50 km) **ET** `actual_km > max_drift_km` → `_dark_reapp` sauvegardé

Résultat stocké dans `_dark_reapp` (variable temporaire) car `dark_ships.pop()` se fait avant l'initialisation de `alert_details`.

#### Check 0b — Injection DARK_REAPPEARANCE
Après `alert_details = []`, si `_dark_reapp` est défini → ajoute `DARK_REAPPEARANCE`.

#### Check 1 — Watchlist opérateur
Compare MMSI et IMO contre `watchlist_mmsi` et `watchlist_imo`.  
Si match → `WATCHLIST_HIT`.

#### Check 1 — Base de sanctions
Lookup dans l'ordre : IMO → MMSI → Nom (uppercase).  
Si trouvé → `SANCTION_{CATEGORIE}` (ex: `SANCTION_SANCTION`, `SANCTION_SHADOW_FLEET`, etc.)

#### Check 1b — Flag Mismatch
Déclenché uniquement si sanction trouvée.  
Compare `flag` de la base sanctions (ISO2) vs préfixe MMSI via `MID_TO_ISO2`.  
Uniquement si le pays de sanction est dans `FLAG_MISMATCH_RISK = {ru, ir, kp, sy, ve, cu, by, mm}`.  
Si différent → `FLAG_MISMATCH`.

#### Check 2 — Vitesse
- Si `SOG > CONFIG['impossible_speed']` (défaut : 50 kt) → `SPEED_IMPOSSIBLE`
- Sinon si `SOG > MAX_SPEED_KT[type]` et `SOG > 5 kt` → `SPEED_ANOMALY`

#### Check 3 — Null Island
Si `|lat| < 0.05° ET |lon| < 0.05°` → `NULL_ISLAND`

#### Check 4 — Zone géographique à risque
Test d'inclusion bounding-box dans chacune des 7 zones `HIGH_RISK_ZONES`.  
Si match → `HIGH_RISK_ZONE`

#### Check 5 — Saut de position (téléportation)
Comparaison avec la position précédente dans `position_history`.  
Uniquement si `dt < 3600s` (évite les faux positifs sur absence longue).  
Seuil : `dist_km > SOG × 1.852 × dt_h × 3 + 20 km`  
Si dépassé → `POSITION_JUMP`

Ensuite : mise à jour de `position_history`, `trail_history` (15 points), `loiter_history` (fenêtre 3h).

#### Check 6 — Signature radio AIS
- `SNR < 35 dB` → `RADIO_SNR_DEGRADE`
- `|CFO| > 250 Hz` → `RADIO_CFO_EXCESSIF`
- `cfo_drift > 30 Hz` (par rapport au CFO de référence de ce MMSI) → `RADIO_CFO_DERIVE`

---

### 4.7 Moniteur dark shipping

`dark_shipping_monitor()` — coroutine asyncio, démarre après 90s, cycle de 60s.

```
Pour chaque navire dans position_history :
  - minutes_silent = maintenant − dernière position connue
  - Si déjà dans dark_ships ET silence > dark_expire_min → retirer du suivi
  - Si silence < dark_min → ignorer
  - Sinon → marquer dark, broadcast événement 'dark_shipping' (alert_level='red')
```

L'entrée dans `dark_ships` sauvegarde `{lat, lon, ts, sog, cog}` pour la vérification DARK_REAPPEARANCE ultérieure.

---

### 4.8 Moniteur STS + loitering

`detection_monitor()` — coroutine asyncio, démarre après 120s, cycle de 60s.

**Loitering :**
```
Pour chaque mmsi dans loiter_history (fenêtre 3h) :
  - Si < 10 points → ignorer
  - Si time_span < loiter_min_h × 3600 → ignorer
  - Si déjà alerté dans les 3 dernières heures → ignorer
  - Calculer centroïde (lat/lon moyenne)
  - max_d = distance max entre centroïde et chaque point
  - Si max_d > loiter_radius_km → ignorer (navire en mouvement)
  - Sinon → broadcast 'loitering' (alert_level='orange')
```

**STS (Ship-to-Ship Transfer) :**
Optimisation grille pour éviter O(n²) sur ~11 000 navires :
```
Diviser la carte en cellules de 0.01° (~1.1 km)
Pour chaque cellule avec ≥ 2 navires :
  Pour chaque paire (m1, m2) dans la cellule :
    dist = haversine(p1, p2)
    Si dist > sts_dist_km → ignorer
    Sinon → incrémenter sts_proximity[{m1,m2}].count
    Si count >= sts_min_checks et non encore alerté :
      → broadcast 'sts' (alert_level='red')
Pour les paires qui ne sont plus proches → réinitialiser leur compteur
```

---

### 4.9 Système de score et niveaux d'alerte

**Niveau d'alerte (pour événements AIS) :**
```
alert_level = 'red'    si len(alert_details) >= 2
            = 'orange' si len(alert_details) == 1
            = 'green'  si len(alert_details) == 0
```

**Score de risque `compute_risk_score(alert_details)` :**
Somme des poids de chaque code détecté, plafonné à 10.0.

| Code | Poids par défaut | Configurable |
|------|-----------------|:------------:|
| `WATCHLIST_HIT` | 5.0 | Oui |
| `STS_DETECTED` | 4.5 | Oui |
| `DARK_REAPPEARANCE` | 4.0 | Oui |
| `DARK_SHIPPING` | 4.0 | Oui |
| `SANCTION_SANCTION` | 4.5 | Non |
| `SANCTION_SHADOW_FLEET` | 3.5 | Non |
| `FLAG_MISMATCH` | 3.5 | Oui |
| `RADIO_CFO_DERIVE` | 3.5 | Non |
| `LOITERING` | 3.0 | Oui |
| `SPEED_IMPOSSIBLE` | 3.0 | Oui |
| `SANCTION_POI` | 2.5 | Non |
| `POSITION_JUMP` | 2.5 | Oui |
| `SANCTION_PSC_DETAINED` | 2.0 | Non |
| `HIGH_RISK_ZONE` | 2.0 | Non |
| `NULL_ISLAND` | 2.0 | Non |
| `SPEED_ANOMALY` | 1.5 | Oui |
| `RADIO_CFO_EXCESSIF` | 1.5 | Non |
| `SANCTION_FLAGGED` | 1.5 | Non |
| `RADIO_SNR_DEGRADE` | 1.0 | Non |
| `SANCTION_REG_WARNING` | 1.0 | Non |

---

### 4.10 Déduplication des broadcasts

Pour éviter de spammer les dashboards avec la même alerte toutes les 30 secondes pour le même navire :

```
new_codes = frozenset des codes d'alerte actuels
prev_b = last_broadcast[mmsi]  (codes + timestamp)

Si prev_b.codes == new_codes ET alert_level != 'green' :
  age = maintenant - prev_b.ts
  limit = dedup_red_s  si niveau rouge
        = dedup_orange_s si niveau orange
  suppress = (age < limit)

Si suppress : event['suppress_card'] = True  → pas de db_insert, mais broadcast quand même
```

Les dashboards lisent `suppress_card` pour ne pas ajouter de nouvelle carte tout en mettant à jour la position sur la carte.

---

### 4.11 API HTTP

Serveur HTTP sur le port 8080 via `http.server.HTTPServer`.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/stats` | Statistiques 6h : compteurs par niveau, top navires, zones, graphe horaire |
| GET | `/api/history` | Historique SQLite avec filtres |
| GET | `/api/history?level=red` | Filtrer par niveau |
| GET | `/api/history?since=3600` | Dernière heure (secondes dans le passé) |
| GET | `/api/history?limit=100` | Limiter le nombre de résultats (max 1000) |
| GET | `/api/vessel/{mmsi}` | Historique d'un MMSI spécifique |
| GET | `/api/config` | Configuration actuelle (JSON) |
| POST | `/api/config` | Modifier la configuration (JSON patch) |
| GET | `/*.html` | Fichiers statiques servis depuis le répertoire courant |

**Format de réponse `/api/stats` :**
```json
{
  "counts":         {"red": 12, "orange": 34, "green": 0},
  "type_counts":    {"WATCHLIST_HIT": 5, "DARK_SHIPPING": 3, ...},
  "zone_counts":    {"Golfe de Guinée": 2, ...},
  "hourly":         [2, 4, 1, 6, 3, 8],
  "total_vessels":  11247,
  "active_vessels": 2103,
  "dark_count":     14,
  "uptime_min":     142,
  "top_vessels":    [{"mmsi": "...", "name": "...", "count": 12, "score": 24}]
}
```

---

## 5. Base de sanctions (sanctions_real.csv)

**11 081 navires** issus de deux sources :

| Source | Entrées |
|--------|---------|
| OpenSanctions | 11 080 |
| OFAC SDN | 1 |

**Colonnes :**

| Colonne | Description |
|---------|-------------|
| `name` | Nom du navire (uppercase dans le système) |
| `flag` | Code ISO2 du pavillon |
| `program` | Programme de sanction (ex: "CUBA", "RUSSIA-EO14024") |
| `imo` | Numéro IMO (7 chiffres) |
| `mmsi` | Numéro MMSI (9 chiffres) |
| `source` | Base d'origine |
| `risk_category` | Catégorie de risque |

**Catégories de risque :**

| Catégorie | Nb | Description |
|-----------|-----|-------------|
| `psc_detained` | 6 130 | Rétention portuaire (Paris/Tokyo/Abuja/Black Sea MOU) |
| `sanction` | 2 437 | Sanctions officielles (OFAC, ONU, UK OFSI, EU) |
| `poi` | 1 479 | Entité d'intérêt — contexte guerre Ukraine |
| `flagged` | 837 | Signalé dans base internationale |
| `reg_warning` | 101 | Avertissement PSC sans immobilisation |
| `shadow_fleet` | 97 | Flotte fantôme (pétrole russe/iranien sous embargo) |

Mise à jour via `fetch_sanctions.py`.

---

## 6. Watchlist opérateur (watchlist.txt)

Fichier texte créé automatiquement s'il n'existe pas. Format :

```
# Commentaires avec #
# MMSI direct (9 chiffres)
123456789
987654321
# IMO avec préfixe IMO
IMO9876543
IMO1234567
```

Chargé au démarrage par `_load_watchlist()`. Les navires de la watchlist déclenchent `WATCHLIST_HIT` (poids 5.0) à chaque signal reçu.

---

## 7. Configuration live (CONFIG)

Dictionnaire Python mutable modifiable en temps réel via `POST /api/config` sans redémarrage.

**Seuils de détection :**

| Clé | Défaut | Unité | Rôle |
|-----|--------|-------|------|
| `loiter_radius_km` | 5.0 | km | Rayon de confinement loitering |
| `loiter_min_h` | 2.0 | heures | Durée min dans la zone |
| `sts_dist_km` | 0.5 | km | Distance max entre 2 navires STS |
| `sts_min_checks` | 3 | cycles×60s | Durée min de proximité STS |
| `dark_min` | 15 | minutes | Silence AIS → alerte dark |
| `dark_expire_min` | 120 | minutes | Silence → oubli du navire |
| `dark_reapp_min_h` | 1.0 | heures | Dark min pour vérif réapparition |
| `dark_reapp_jump_km` | 50.0 | km | Saut anormal à la réapparition |
| `impossible_speed` | 50.0 | nœuds | Seuil vitesse physiquement impossible |
| `dedup_orange_s` | 300 | secondes | Intervalle min entre 2 alertes orange |
| `dedup_red_s` | 180 | secondes | Intervalle min entre 2 alertes rouge |

**Poids de risque configurables :**

| Clé | Défaut |
|-----|--------|
| `w_watchlist_hit` | 5.0 |
| `w_sts_detected` | 4.5 |
| `w_dark_reappearance` | 4.0 |
| `w_dark_shipping` | 4.0 |
| `w_loitering` | 3.0 |
| `w_flag_mismatch` | 3.5 |
| `w_speed_impossible` | 3.0 |
| `w_position_jump` | 2.5 |
| `w_speed_anomaly` | 1.5 |

---

## 8. Codes d'alerte — référence complète

| Code | Niveau typique | Source | Signification opérationnelle |
|------|---------------|--------|------------------------------|
| `WATCHLIST_HIT` | Rouge | Watchlist | Cible connue sous surveillance |
| `SANCTION_SANCTION` | Rouge | Sanctions | Sanctionné OFAC/ONU/EU/UK |
| `SANCTION_SHADOW_FLEET` | Rouge | Sanctions | Flotte fantôme pétrole russe/iranien |
| `SANCTION_POI` | Orange | Sanctions | Entité d'intérêt Ukraine |
| `SANCTION_PSC_DETAINED` | Orange | Sanctions | Rétention portuaire documentée |
| `SANCTION_FLAGGED` | Orange | Sanctions | Signalé en base internationale |
| `SANCTION_REG_WARNING` | Orange | Sanctions | Avertissement PSC |
| `FLAG_MISMATCH` | Rouge | AIS | Pavillon sanctionné ≠ nationalité MMSI |
| `DARK_SHIPPING` | Rouge | Moniteur 60s | AIS coupé depuis > 15 min |
| `DARK_REAPPEARANCE` | Rouge | AIS | Réapparition avec saut de position |
| `LOITERING` | Orange | Moniteur 60s | Station prolongée dans rayon 5 km |
| `STS_DETECTED` | Rouge | Moniteur 60s | Deux navires à < 500 m depuis > 3 min |
| `SPEED_IMPOSSIBLE` | Orange/Rouge | AIS | Vitesse > 50 kt — spoofing probable |
| `SPEED_ANOMALY` | Orange | AIS | Vitesse > max pour le type de navire |
| `POSITION_JUMP` | Orange | AIS | Téléportation incohérente avec SOG |
| `NULL_ISLAND` | Orange | AIS | Position à (0°, 0°) — GPS défaillant |
| `HIGH_RISK_ZONE` | Orange | AIS | Présence dans zone classée à risque |
| `RADIO_CFO_DERIVE` | Orange | Radio | Empreinte RF différente → clonage MMSI |
| `RADIO_CFO_EXCESSIF` | Orange | Radio | Oscillateur hors spec ITU-R (> ±250 Hz) |
| `RADIO_SNR_DEGRADE` | Orange | Radio | Signal dégradé (SNR < 35 dB) |

---

## 9. Format des événements WebSocket

Tous les événements sont diffusés en JSON sur `ws://localhost:8765`.

### Événement `ais` (signal normal/alerte)

```json
{
  "event_type":    "ais",
  "mmsi":          123456789,
  "name":          "ATLANTIC TRADER",
  "flag":          "🇵🇦",
  "country":       "Panama",
  "risk_score":    6.5,
  "type":          "Cargo",
  "lat":           48.234,
  "lon":           -4.512,
  "speed":         12.3,
  "freq":          161.975,
  "bw":            25.1,
  "power":         12.5,
  "snr":           42.1,
  "rssi_dbm":      -84.2,
  "channel":       87,
  "cfo_hz":        -23.4,
  "dist_km":       912.0,
  "fp_first_seen": "14:32:01",
  "fp_count":      47,
  "fp_cfo_ref":    -22.1,
  "fp_cfo_drift":  1.3,
  "trail":         [[48.2, -4.5], [48.21, -4.51], ...],
  "alert_details": [
    {
      "code":   "WATCHLIST_HIT",
      "label":  "🎯 Cible watchlist — MMSI 123456789",
      "detail": "Ce navire figure sur la liste..."
    }
  ],
  "clean_checks":  ["Position géographique valide...", ...],
  "alerts":        ["🎯 Cible watchlist — MMSI 123456789"],
  "alert_level":   "orange",
  "timestamp":     "14:35:22",
  "ts_epoch":      1747130122,
  "suppress_card": false
}
```

### Événement `dark_shipping`

```json
{
  "event_type":     "dark_shipping",
  "mmsi":           987654321,
  "name":           "SHADOW TANKER",
  "flag":           "🇷🇺",
  "country":        "Russie",
  "risk_score":     4.0,
  "type":           "Tanker",
  "last_lat":       35.12,
  "last_lon":       28.44,
  "minutes_silent": 23,
  "alert_level":    "red",
  "alert_details":  [{"code": "DARK_SHIPPING", ...}],
  "alerts":         ["AIS coupé depuis 23 min"],
  "timestamp":      "15:02:11",
  "ts_epoch":       1747131731
}
```

### Événement `loitering`

```json
{
  "event_type":   "loitering",
  "mmsi":         111222333,
  "name":         "PESCA LIBRE",
  "lat":          43.21,
  "lon":          -2.33,
  "last_lat":     43.22,
  "last_lon":     -2.34,
  "duration_min": 142,
  "radius_km":    3.2,
  "risk_score":   3.0,
  "alert_level":  "orange",
  "alert_details": [{"code": "LOITERING", ...}],
  "timestamp":    "16:14:55"
}
```

### Événement `sts`

```json
{
  "event_type": "sts",
  "m1":         {"mmsi": 111, "name": "NAVIRE A", "type": "Tanker", ...},
  "m2":         {"mmsi": 222, "name": "NAVIRE B", "type": "Cargo", ...},
  "dist_km":    0.32,
  "duration_s": 240,
  "lat":        36.5,
  "lon":        14.2,
  "risk_score": 4.5,
  "alert_level":"red",
  "alert_details": [{"code": "STS_DETECTED", ...}],
  "timestamp":  "17:00:00"
}
```

---

## 10. Pages frontend

### dashboard.html — Carte temps réel
- Carte Leaflet.js avec tuiles marine sombre (Carto Dark / CartoDB DarkMatter)
- Deux couches : `dark_nolabels` + `dark_only_labels` pour rendu net
- Marqueur circulaire par navire coloré selon le niveau d'alerte : rouge / orange / vert
- Trajectoire affichée (15 points, `trail`)
- Popup au clic : toutes les infos du navire incluant signature radio
- Compteurs en temps réel : navires actifs, alertes rouges, alertes orange, dark
- Filtre par niveau d'alerte (boutons Tout / Suspects / Alertes)

### dashboard_alertes.html — Fil d'alertes
- Reçoit tous les événements WebSocket
- **Filtre :** `event_type === 'sts'` → ignoré, `alert_level !== 'red'` → ignoré (sauf loitering et dark_shipping traités séparément)
- Carte latérale avec marqueurs des positions d'alerte
- Historique modal avec filtre temporel (1h / 6h / 24h / Tout) via `GET /api/history?since=N`
- Push notifications navigateur (`Notification API`)

### dashboard_suspects.html — Navires suspects
- Reçoit tous les événements WebSocket
- Affiche `alert_level === 'orange'` + événements `loitering`
- Carte avec marqueurs jaunes pour les loiterings (cercle L.divIcon)

### dashboard_sts.html — Transferts STS
- **Filtre strict :** `event_type !== 'sts'` → ignoré
- Carte avec `L.circle` par paire STS + marqueur ping central
- Cards bilatérales : deux navires côte à côte avec informations complètes
- Métriques : distance (m), durée (min), score de risque avec barre visuelle
- Badge counter sur l'onglet navigateur quand la page est en arrière-plan
- Bip sonore à chaque nouveau STS détecté

### stats.html — Statistiques
- Polling HTTP `GET /api/stats` toutes les 30 secondes
- KPI cards : total alertes rouges, oranges, navires dark, navires actifs, uptime
- Histogramme 6 heures (Chart.js)
- Top 5 navires les plus alertés
- Distribution des types d'alertes
- Distribution par zone géographique

### dashboard_settings.html — Paramètres
- Lecture initiale de `GET /api/config`
- Sliders synchronisés avec champs numériques
- `POST /api/config` avec le patch JSON des valeurs modifiées
- Modification sans redémarrage — les coroutines lisent `CONFIG` dynamiquement
- Bouton de réinitialisation (restaure les valeurs chargées depuis le serveur)

---

## 11. Dépendances et lancement

### Dépendances Python

```
pandas        — chargement sanctions_real.csv
websockets    — client WebSocket aisstream.io + serveur WebSocket navigateurs
aiohttp       — (installé comme dépendance transitive)
```

Bibliothèques standard utilisées : `asyncio, json, random, math, os, time, threading, sqlite3, urllib.parse, http.server, collections, datetime`

### Installation

```bash
pip3 install --break-system-packages pandas websockets aiohttp
```

### Lancement

```bash
# Depuis le répertoire work/
python3 dashboard.py
```

### Arrêt et relance (libérer les ports si déjà occupés)

```bash
lsof -ti TCP:8080 | xargs kill -9 2>/dev/null
lsof -ti TCP:8765 | xargs kill -9 2>/dev/null
python3 dashboard.py
```

### URLs d'accès

| Page | URL |
|------|-----|
| Carte principale | http://localhost:8080/dashboard.html |
| Alertes rouges | http://localhost:8080/dashboard_alertes.html |
| Navires suspects | http://localhost:8080/dashboard_suspects.html |
| Transferts STS | http://localhost:8080/dashboard_sts.html |
| Statistiques | http://localhost:8080/stats.html |
| Paramètres | http://localhost:8080/dashboard_settings.html |
| API config | http://localhost:8080/api/config |
| API stats | http://localhost:8080/api/stats |
| API historique | http://localhost:8080/api/history?level=red&since=3600 |

---

*Documentation générée le 13 mai 2026 — Hackathon Albert 2026, Sujet 3.*
