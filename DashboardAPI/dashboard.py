"""
Dashboard temps réel — AIS + pipeline d'identification
=======================================================
Serveur HTTP  → http://localhost:8080/dashboard.html
WebSocket     → ws://localhost:8765  (flux d'événements navires)
"""

import asyncio
import json
import random
import math
import os
import time
import threading
import sqlite3
import urllib.parse
import pandas as pd
from collections import defaultdict, deque
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
import websockets

# ── Chemins ────────────────────────────────────────────────────────────────
BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'alerts.db')

# ── SQLite — persistence des alertes ───────────────────────────────────────
_db_lock = threading.Lock()

def _init_db():
    with _db_lock, sqlite3.connect(DB_PATH) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS events (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi              TEXT    NOT NULL,
            name              TEXT,
            alert_level       TEXT,
            alert_codes       TEXT,
            alerts_json       TEXT,
            alert_details_json TEXT,
            lat               REAL,
            lon               REAL,
            ts                TEXT
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ts    ON events(ts)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_level ON events(alert_level)')
    print(f"✅ SQLite DB: {DB_PATH}")

_init_db()

def db_insert(event: dict):
    lat = event.get('lat') or event.get('last_lat')
    lon = event.get('lon') or event.get('last_lon')
    with _db_lock, sqlite3.connect(DB_PATH) as c:
        c.execute(
            'INSERT INTO events '
            '(mmsi,name,alert_level,alert_codes,alerts_json,alert_details_json,lat,lon,ts) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            (
                str(event.get('mmsi', '')),
                event.get('name', ''),
                event.get('alert_level', ''),
                json.dumps([a['code'] for a in event.get('alert_details', [])]),
                json.dumps(event.get('alerts', [])),
                json.dumps(event.get('alert_details', [])),
                lat, lon,
                event.get('timestamp', datetime.now(timezone.utc).strftime('%H:%M:%S')),
            )
        )

API_KEY = "caae13ac0e37a4c0b6721666f74396b938c5b670"
WS_URL  = "wss://stream.aisstream.io/v0/stream"

# ── Watchlist opérateur ─────────────────────────────────────────────────────
WATCHLIST_PATH = os.path.join(BASE, 'watchlist.txt')
watchlist_mmsi: set = set()
watchlist_imo:  set = set()

def _load_watchlist():
    global watchlist_mmsi, watchlist_imo
    if not os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'w') as f:
            f.write('# Watchlist Marine Nationale — un MMSI ou IMO par ligne\n')
            f.write('# IMO : préfixer par IMO   ex: IMO9876543\n')
            f.write('# MMSI: entrer directement ex: 123456789\n')
            f.write('# Lignes commençant par # ignorées\n')
        print("✅ watchlist.txt créée (vide — ajoutez vos cibles)")
        return
    nm, ni = set(), set()
    with open(WATCHLIST_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.upper().startswith('IMO'):
                ni.add(line[3:].strip())
            else:
                nm.add(line)
    watchlist_mmsi, watchlist_imo = nm, ni
    print(f"✅ Watchlist : {len(nm)} MMSI + {len(ni)} IMO sous surveillance")

_load_watchlist()

# ── Détection comportementale — STS et Loitering ────────────────────────────
loiter_history:    dict = {}   # mmsi → deque([(lat, lon, ts_float), ...])
loitering_alerted: dict = {}   # mmsi → ts_float (quand l'alerte a été émise)
sts_proximity:     dict = {}   # frozenset({m1,m2}) → {count, first_ts, alerted, ...}

LOITER_RADIUS_KM = 5.0    # rayon max pour déclarer un loitering
LOITER_MIN_H     = 2.0    # durée min en heures
STS_DIST_KM      = 0.5    # distance max (500 m) pour un STS
STS_MIN_CHECKS   = 3      # 3 contrôles consécutifs × 60 s = 3 min de proximité

# ── Configuration live — modifiable via /api/config ────────────────────────
CONFIG: dict = {
    # Loitering
    'loiter_radius_km':    5.0,   # km
    'loiter_min_h':        2.0,   # heures
    # STS
    'sts_dist_km':         0.5,   # km (500 m)
    'sts_min_checks':      3,     # × 60 s
    # Dark shipping
    'dark_min':            15,    # min sans signal → alerte
    'dark_expire_min':     120,   # min → oubli
    # Dark reappearance
    'dark_reapp_min_h':    1.0,   # durée dark min pour activer la vérification
    'dark_reapp_jump_km':  50.0,  # saut anormal min (km)
    # Vitesse
    'impossible_speed':    50.0,  # kt
    # Déduplication
    'dedup_orange_s':      300,   # s entre 2 notifs orange identiques
    'dedup_red_s':         180,   # s entre 2 notifs rouge identiques
    # Poids de risque
    'w_watchlist_hit':     5.0,
    'w_sts_detected':      4.5,
    'w_dark_reappearance': 4.0,
    'w_dark_shipping':     4.0,
    'w_loitering':         3.0,
    'w_flag_mismatch':     3.5,
    'w_speed_impossible':  3.0,
    'w_position_jump':     2.5,
    'w_speed_anomaly':     1.5,
}

# ── Profils radio live — construits à partir du flux AIS en temps réel ──────
# Aucune dépendance à un fichier hackathon : les profils s'accumulent au fil
# des observations. Chaque MMSI vu pour la première fois y est enregistré.
# Structure : live_profiles[mmsi] = {
#   'cfo_ref'   : float  — CFO de référence (1ère mesure)
#   'name'      : str    — dernier nom connu
#   'first_seen': str    — heure de première détection
#   'count'     : int    — nombre d'observations
# }
live_profiles: dict = {}
print("✅ Profils radio live initialisés (alimentés par le flux AIS)")

# ── Journal d'événements (stats temps réel) ────────────────────────────────
server_start = datetime.now(timezone.utc)
alert_log: list = []          # [{ts, level, types, zone}]  — 6 dernières heures max

def log_event(level: str, alert_types: list = None, zone: str = ''):
    now_ts = time.time()
    alert_log.append({'ts': now_ts, 'level': level,
                       'types': alert_types or [], 'zone': zone})
    cutoff = now_ts - 6 * 3600
    while alert_log and alert_log[0]['ts'] < cutoff:
        alert_log.pop(0)

# ── Chargement base de sanctions consolidée ─────────────────────────────────
print("Chargement base de sanctions (OFAC + OpenSanctions + UN + UK)...")
sanctions_path = os.path.join(BASE, 'sanctions_real.csv')
if not os.path.exists(sanctions_path):
    raise FileNotFoundError("sanctions_real.csv introuvable — lance fetch_sanctions.py d'abord")

sanctions_df = pd.read_csv(sanctions_path)

def _clean_id(s):
    return (s.astype(str).str.strip()
             .str.replace(r'\.0$', '', regex=True)
             .replace({'nan': '', 'None': ''}))

sanctions_df['imo']  = _clean_id(sanctions_df['imo'])
sanctions_df['mmsi'] = _clean_id(sanctions_df['mmsi'])
sanctions_df['name'] = sanctions_df['name'].str.strip().str.upper()

sanctioned_imo_map: dict  = {
    r['imo']: r for _, r in sanctions_df.iterrows() if r['imo'] not in ('', 'nan')
}
sanctioned_mmsi_map: dict = {
    r['mmsi']: r for _, r in sanctions_df.iterrows() if r['mmsi'] not in ('', 'nan')
}
sanctioned_names: set = set(sanctions_df['name'].tolist())

cats = sanctions_df['risk_category'].value_counts().to_dict()
print(f"  ✅ {len(sanctions_df)} navires  "
      f"({len(sanctioned_imo_map)} IMO | {len(sanctioned_mmsi_map)} MMSI)")
print(f"     sanctionnés={cats.get('sanction',0)}  "
      f"shadow={cats.get('shadow_fleet',0)}  "
      f"PSC={cats.get('psc_detained',0)}  "
      f"poi={cats.get('poi',0)}\n")

# Labels et détails par catégorie de risque
RISK_ALERT: dict = {
    'sanction': (
        'Navire sanctionné internationalement',
        'Ce navire figure sur une liste de sanctions officielle '
        '(OFAC/US Treasury, UK OFSI, UN SC 1718, EU, Ukraine). '
        'Toute transaction avec ce navire est soumise à des restrictions légales strictes.'
    ),
    'shadow_fleet': (
        'Flotte fantôme (shadow fleet)',
        'Ce navire est identifié comme appartenant à la flotte fantôme — '
        'tankers âgés utilisés pour transporter du pétrole russe ou iranien '
        'en contournant les embargos, souvent sans assurance P&I valide.'
    ),
    'psc_detained': (
        'Rétention portuaire (Port State Control)',
        'Ce navire a été immobilisé par une autorité portuaire '
        '(Paris MOU, Tokyo MOU, Abuja MOU ou Black Sea MOU) '
        'pour non-conformité : défauts de sécurité, équipage sous-standard, '
        'pollution ou documentation invalide.'
    ),
    'poi': (
        "Entité d'intérêt (contexte guerre Ukraine)",
        'Ce navire est référencé comme entité d\'intérêt dans le cadre '
        'des sanctions liées à la guerre en Ukraine. '
        'Surveillance recommandée sur ses mouvements et escales.'
    ),
    'reg_warning': (
        'Avertissement réglementaire (PSC)',
        'Ce navire a reçu un avertissement lors d\'une inspection portuaire '
        'sans être immobilisé. Signale des déficiences mineures à surveiller.'
    ),
    'flagged': (
        'Navire signalé (base de données internationale)',
        'Ce navire apparaît dans une base de surveillance maritime internationale '
        'sans sanction formelle mais avec des indicateurs de risque.'
    ),
}

# ── MID codes MMSI → pays / drapeau ────────────────────────────────────────
# Source : ITU Table of Maritime Identification Digits (MID)
MID_CODES: dict = {
    201:'🇦🇱 Albanie',    202:'🇦🇩 Andorre',    203:'🇦🇹 Autriche',
    205:'🇧🇪 Belgique',   206:'🇧🇾 Biélorussie', 207:'🇧🇬 Bulgarie',
    209:'🇨🇾 Chypre',     211:'🇩🇪 Allemagne',   213:'🇬🇪 Géorgie',
    214:'🇲🇩 Moldavie',   215:'🇲🇹 Malte',       218:'🇩🇪 Allemagne',
    219:'🇩🇰 Danemark',   220:'🇩🇰 Danemark',    224:'🇪🇸 Espagne',
    225:'🇪🇸 Espagne',    226:'🇫🇷 France',      227:'🇫🇷 France',
    228:'🇫🇷 France',     230:'🇫🇮 Finlande',    232:'🇬🇧 Royaume-Uni',
    233:'🇬🇧 Royaume-Uni',234:'🇬🇧 Royaume-Uni', 235:'🇬🇧 Royaume-Uni',
    237:'🇬🇷 Grèce',      238:'🇭🇷 Croatie',     239:'🇬🇷 Grèce',
    240:'🇬🇷 Grèce',      241:'🇬🇷 Grèce',       244:'🇳🇱 Pays-Bas',
    245:'🇳🇱 Pays-Bas',   247:'🇮🇹 Italie',      248:'🇲🇹 Malte',
    249:'🇲🇹 Malte',      250:'🇮🇪 Irlande',     251:'🇮🇸 Islande',
    255:'🇵🇹 Madère',     257:'🇳🇴 Norvège',     258:'🇳🇴 Norvège',
    259:'🇳🇴 Norvège',    261:'🇵🇱 Pologne',     263:'🇵🇹 Portugal',
    264:'🇷🇴 Roumanie',   265:'🇸🇪 Suède',       266:'🇸🇪 Suède',
    269:'🇨🇭 Suisse',     271:'🇹🇷 Turquie',     272:'🇺🇦 Ukraine',
    273:'🇷🇺 Russie',     275:'🇱🇻 Lettonie',    276:'🇪🇪 Estonie',
    277:'🇱🇹 Lituanie',   278:'🇸🇮 Slovénie',    279:'🇷🇸 Serbie',
    303:'🇺🇸 États-Unis', 308:'🇧🇸 Bahamas',     309:'🇧🇸 Bahamas',
    311:'🇧🇸 Bahamas',    316:'🇨🇦 Canada',      319:'🇰🇾 Îles Caïmans',
    321:'🇨🇺 Cuba',       338:'🇺🇸 États-Unis',  347:'🇲🇽 Mexique',
    351:'🇵🇦 Panama',     352:'🇵🇦 Panama',      353:'🇵🇦 Panama',
    354:'🇵🇦 Panama',     355:'🇵🇦 Panama',      356:'🇵🇦 Panama',
    357:'🇵🇦 Panama',     366:'🇺🇸 États-Unis',  367:'🇺🇸 États-Unis',
    368:'🇺🇸 États-Unis', 369:'🇺🇸 États-Unis',  370:'🇵🇦 Panama',
    371:'🇵🇦 Panama',     372:'🇵🇦 Panama',      373:'🇵🇦 Panama',
    374:'🇵🇦 Panama',     412:'🇨🇳 Chine',       413:'🇨🇳 Chine',
    414:'🇨🇳 Chine',      416:'🇹🇼 Taïwan',      419:'🇮🇳 Inde',
    422:'🇮🇷 Iran',       425:'🇮🇶 Irak',        428:'🇮🇱 Israël',
    431:'🇯🇵 Japon',      432:'🇯🇵 Japon',       440:'🇰🇷 Corée du Sud',
    441:'🇰🇷 Corée du Sud',445:'🇰🇵 Corée du Nord',447:'🇰🇼 Koweït',
    450:'🇱🇧 Liban',      461:'🇴🇲 Oman',        463:'🇵🇰 Pakistan',
    466:'🇶🇦 Qatar',      468:'🇸🇾 Syrie',       470:'🇦🇪 Émirats arabes',
    477:'🇭🇰 Hong Kong',  503:'🇦🇺 Australie',   506:'🇲🇲 Myanmar',
    510:'🇫🇲 Micronésie', 512:'🇳🇿 Nouvelle-Zélande',514:'🇰🇭 Cambodge',
    515:'🇰🇭 Cambodge',   520:'🇫🇯 Fidji',       525:'🇮🇩 Indonésie',
    533:'🇲🇾 Malaisie',   538:'🇲🇭 Îles Marshall',548:'🇵🇬 PNG',
    553:'🇵🇭 Philippines', 557:'🇸🇧 Îles Salomon',563:'🇸🇬 Singapour',
    564:'🇸🇬 Singapour',  565:'🇸🇬 Singapour',   566:'🇸🇬 Singapour',
    567:'🇹🇭 Thaïlande',  574:'🇻🇳 Vietnam',     601:'🇿🇦 Afrique du Sud',
    603:'🇦🇴 Angola',     605:'🇩🇿 Algérie',     610:'🇧🇯 Bénin',
    613:'🇨🇲 Cameroun',   615:'🇨🇬 Congo',       617:'🇨🇻 Cap-Vert',
    619:'🇨🇮 Côte d\'Ivoire',621:'🇩🇯 Djibouti',622:'🇪🇬 Égypte',
    624:'🇪🇹 Éthiopie',   625:'🇪🇷 Érythrée',    626:'🇬🇦 Gabon',
    627:'🇬🇭 Ghana',      629:'🇬🇲 Gambie',      632:'🇬🇳 Guinée',
    634:'🇰🇪 Kenya',      636:'🇱🇷 Libéria',     637:'🇱🇷 Libéria',
    642:'🇱🇾 Libye',      645:'🇲🇺 Maurice',     647:'🇲🇬 Madagascar',
    650:'🇲🇿 Mozambique', 654:'🇲🇷 Mauritanie',  657:'🇳🇬 Nigeria',
    659:'🇳🇦 Namibie',    662:'🇸🇩 Soudan',      663:'🇸🇳 Sénégal',
    666:'🇸🇴 Somalie',    667:'🇸🇱 Sierra Leone',670:'🇹🇩 Tchad',
    671:'🇹🇬 Togo',       672:'🇹🇳 Tunisie',     674:'🇹🇿 Tanzanie',
    675:'🇺🇬 Ouganda',    676:'🇨🇩 RD Congo',
}

def mmsi_flag(mmsi) -> tuple:
    """Retourne (flag_str, country) depuis les 3 premiers chiffres du MMSI."""
    mid = int(str(mmsi)[:3])
    label = MID_CODES.get(mid, '')
    if not label:
        return '', 'Inconnu'
    parts = label.split(' ', 1)
    return parts[0], parts[1] if len(parts) > 1 else label

# ISO2 par MID — permet de détecter les changements de pavillon post-sanction
MID_TO_ISO2: dict = {
    273: 'ru', 422: 'ir', 445: 'kp', 412: 'cn', 467: 'sy', 775: 've',
    366: 'cu', 206: 'by', 506: 'mm', 468: 'sy', 470: 'sy',
    636: 'lr', 352: 'pa', 232: 'gb', 338: 'us', 369: 'us',
    228: 'fr', 247: 'it', 211: 'de', 244: 'nl', 219: 'dk',
    265: 'se', 230: 'fi', 257: 'no', 248: 'mt', 255: 'pt',
    224: 'es', 237: 'gr', 239: 'gr', 271: 'tr', 351: 'pa',
    370: 'pa', 371: 'pa', 372: 'pa', 373: 'pa',
    511: 'pw', 572: 'tv', 667: 'sl', 669: 'st', 553: 'pg',
}
# Pavillons à haut risque — un écart MMSI/flag est suspect pour ces pays
FLAG_MISMATCH_RISK: frozenset = frozenset({'ru', 'ir', 'kp', 'sy', 've', 'cu', 'by', 'mm'})

# ── Pondération des alertes → score de risque ───────────────────────────────
RISK_WEIGHTS: dict = {
    'WATCHLIST_HIT':         5.0,
    'STS_DETECTED':          4.5,
    'SANCTION_SANCTION':     4.5,
    'SANCTION_SHADOW_FLEET': 3.5,
    'SANCTION_POI':          2.5,
    'SANCTION_PSC_DETAINED': 2.0,
    'SANCTION_FLAGGED':      1.5,
    'SANCTION_REG_WARNING':  1.0,
    'DARK_SHIPPING':         4.0,
    'RADIO_CFO_DERIVE':      3.5,
    'SPEED_IMPOSSIBLE':      3.0,
    'POSITION_JUMP':         2.5,
    'HIGH_RISK_ZONE':        2.0,
    'NULL_ISLAND':           2.0,
    'SPEED_ANOMALY':         1.5,
    'RADIO_CFO_EXCESSIF':    1.5,
    'RADIO_SNR_DEGRADE':     1.0,
    'LOITERING':             3.0,
    'FLAG_MISMATCH':         3.5,
    'DARK_REAPPEARANCE':     4.0,
}

def compute_risk_score(alert_details: list) -> float:
    dynamic = {
        'WATCHLIST_HIT':     CONFIG['w_watchlist_hit'],
        'STS_DETECTED':      CONFIG['w_sts_detected'],
        'DARK_REAPPEARANCE': CONFIG['w_dark_reappearance'],
        'DARK_SHIPPING':     CONFIG['w_dark_shipping'],
        'LOITERING':         CONFIG['w_loitering'],
        'FLAG_MISMATCH':     CONFIG['w_flag_mismatch'],
        'SPEED_IMPOSSIBLE':  CONFIG['w_speed_impossible'],
        'POSITION_JUMP':     CONFIG['w_position_jump'],
        'SPEED_ANOMALY':     CONFIG['w_speed_anomaly'],
    }
    weights = {**RISK_WEIGHTS, **dynamic}
    total = sum(weights.get(a['code'], 1.0) for a in alert_details)
    return round(min(10.0, total), 1)

# ── Checks comportementaux ─────────────────────────────────────────────────
MAX_SPEED_KT: dict = {
    'Cargo': 25, 'Tanker': 20, 'Passenger': 38,
    'Fishing': 18, 'Tug': 15, 'Pleasure': 40,
}
IMPOSSIBLE_SPEED = 50.0  # kt — physiquement impossible pour tout navire commercial

HIGH_RISK_ZONES: list = [
    {'name': 'Golfe de Guinée',
     'lat': (-5, 7),   'lon': (-5, 15),
     'reason': 'zone de piraterie active — IMB Risk Rating High'},
    {'name': 'Golfe Persique / Iran',
     'lat': (23, 30),  'lon': (48, 57),
     'reason': 'zone de sanctions Iran, transferts pétroliers illicites'},
    {'name': 'Bab-el-Mandeb / Mer Rouge sud',
     'lat': (11, 16),  'lon': (41, 48),
     'reason': 'attaques de navires par les Houthis (2024-2025)'},
    {'name': 'Mer Rouge nord',
     'lat': (16, 30),  'lon': (32, 44),
     'reason': 'zone de conflit actif, détournements 2024-2025'},
    {'name': 'Détroit de Malacca',
     'lat': (1, 6),    'lon': (98, 105),
     'reason': 'piraterie, contrebande, trafic humain'},
    {'name': 'Eaux nord-coréennes',
     'lat': (36, 43),  'lon': (124, 132),
     'reason': 'sanctions DPRK, transferts illicites de charbon et pétrole'},
    {'name': 'Côtes somaliennes',
     'lat': (2, 15),   'lon': (41, 52),
     'reason': 'piraterie (IMB) — reprise d\'activité depuis 2023'},
]

# Historique positions : détection de téléportation + trajectoires
# position_history[mmsi] = {'lat', 'lon', 'ts'}   — dernière position connue
# trail_history[mmsi]    = [(lat, lon), ...]        — 15 derniers points
position_history: dict = {}
trail_history:    dict = {}
TRAIL_MAX = 15

# Cache navires (module-level pour être accessible au moniteur dark shipping)
ship_cache_global: dict = {}

# Dark shipping — navires qui ont coupé leur AIS
# dark_ships[mmsi] = {'lat','lon','ts','sog','cog'}  → position au moment du dark
dark_ships:      dict = {}
DARK_MIN        = 15    # minutes sans signal → alerte (valeur par défaut)
DARK_EXPIRE_MIN = 120   # au-delà : on oublie (navire probablement au port)

# Déduplication des broadcasts — évite de re-notifier la même alerte toutes les 30s
# last_broadcast[mmsi] = {'codes': frozenset, 'ts': float}
last_broadcast: dict = {}
DEDUP_ORANGE_S  = 300   # 5 min entre deux notifications orange identiques
DEDUP_RED_S     = 180   # 3 min entre deux notifications rouge identiques

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en km entre deux points GPS."""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return r * 2 * math.asin(math.sqrt(a))

# ── Modèle radio physique AIS — ITU-R M.1371-5 ──────────────────────────────
# Réf : ITU-R M.1371-5 §A.1, ETSI EN 302 194, modèle satellite LEO (exactEarth/Spire)

AIS_CH87B_MHZ   = 161.975   # Voie AIS primaire   (Ch 87B)
AIS_CH88B_MHZ   = 162.025   # Voie AIS secondaire (Ch 88B)
AIS_BW_KHZ      = 25.0      # Largeur de bande GMSK BT=0.4
AIS_PWR_CLASS_A = 12.5      # W — Class A (navires commerciaux)
AIS_PWR_CLASS_B = 2.0       # W — Class B (plaisance/pêche/remorqueurs)
SAT_SLANT_KM    = 900.0     # km — portée oblique nominale satellite LEO
SAT_GAIN_DBI    = 20.0      # dBi — antenne satellite parabole
RX_NF_DB        = 4.0       # dB  — facteur de bruit récepteur

CLASS_B_TYPES   = frozenset({'Fishing', 'Fishing Vessel', 'Pleasure', 'Pleasure Craft',
                              'Tug', 'Sailing', 'Sail'})

_cfo_cache: dict = {}

def _get_cfo_hz(mmsi: int) -> float:
    """CFO déterministe et unique par émetteur — imprécision TCXO (1 ppm std = 108 Hz sur 162 MHz)."""
    if mmsi not in _cfo_cache:
        rng = random.Random(mmsi ^ 0xA15ACA1)
        _cfo_cache[mmsi] = rng.gauss(0, 108)
    return _cfo_cache[mmsi]

def _noise_floor_dbm() -> float:
    return -174.0 + 10 * math.log10(AIS_BW_KHZ * 1e3) + RX_NF_DB   # ≈ −126 dBm

def radio_fingerprint(mmsi: int, ship_type: str, lat: float, lon: float) -> dict:
    """
    Calcule l'empreinte radio physique du signal AIS selon ITU-R M.1371-5.
    Modèle : récepteur satellite LEO (900 km, type exactEarth/Spire).
      - Canal réel : Ch87B 161.975 MHz (MMSI pair) / Ch88B 162.025 MHz (MMSI impair)
      - Puissance   : 12.5 W Class A / 2 W Class B
      - RSSI        : FSPL de Friis + gains antennes
      - CFO         : décalage d'oscillateur unique et stable par émetteur
      - SNR         : RSSI − plancher de bruit thermique (25 kHz, NF 4 dB)
    """
    mmsi_i  = int(mmsi)
    ch_num  = 87 if mmsi_i % 2 == 0 else 88
    ch_freq = AIS_CH87B_MHZ if ch_num == 87 else AIS_CH88B_MHZ

    cfo_hz   = _get_cfo_hz(mmsi_i)
    freq_mhz = ch_freq + cfo_hz / 1e6

    pwr_w  = AIS_PWR_CLASS_B if ship_type in CLASS_B_TYPES else AIS_PWR_CLASS_A
    pt_dbm = 10 * math.log10(pwr_w * 1000)

    # Portée oblique satellite (déterministe par position pour cohérence inter-mesures)
    pos_rng  = random.Random(int(abs(lat * 100)) ^ int(abs(lon * 100)) ^ mmsi_i)
    slant_km = SAT_SLANT_KM * pos_rng.uniform(0.85, 1.15)
    fspl_db  = (20 * math.log10(max(slant_km, 1))
                + 20 * math.log10(ch_freq) + 32.45)
    rssi_nom = pt_dbm - fspl_db + 2.15 + SAT_GAIN_DBI   # 2.15 dBi dipôle navire

    # Scintillation atmosphérique (fading lognormal VHF satellite, std ≈ 6 dB)
    fade_db   = random.gauss(0, 6.0)
    rssi_meas = rssi_nom + fade_db

    # Bruit de mesure sur le CFO (résolution du discriminateur de fréquence, ±8 Hz)
    cfo_meas = cfo_hz + random.gauss(0, 8.0)

    noise_dbm = _noise_floor_dbm()
    snr_db    = rssi_meas - noise_dbm

    bw_rng  = random.Random(mmsi_i ^ 0xB007)
    bw_meas = AIS_BW_KHZ + bw_rng.gauss(0, 0.3)

    return {
        'frequency':             round(freq_mhz, 6),
        'bandwidth':             round(bw_meas, 2),
        'power':                 round(pwr_w, 3),
        'signal_to_noise_ratio': round(max(-15.0, snr_db), 1),
        'rssi_dbm':              round(rssi_meas, 1),
        'rssi_nominal_dbm':      round(rssi_nom, 1),
        'dist_km':               round(slant_km, 0),
        'channel':               ch_num,
        'cfo_hz':                round(cfo_meas, 1),   # mesure bruitée ±8 Hz
        'cfo_true_hz':           round(cfo_hz, 1),     # valeur de référence
    }


# ── WebSocket clients (navigateurs) ────────────────────────────────────────
connected_clients: set = set()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        async for _ in websocket:   # consomme les messages entrants (pings, etc.)
            pass
    finally:
        connected_clients.discard(websocket)

async def broadcast(data: dict):
    if not connected_clients:
        return
    msg  = json.dumps(data, ensure_ascii=False)
    dead = set()
    for client in list(connected_clients):
        try:
            await client.send(msg)
        except Exception:
            dead.add(client)
    connected_clients.difference_update(dead)  # in-place, pas d'affectation → pas de UnboundLocalError

# ── Pipeline AIS → broadcast ────────────────────────────────────────────────
async def ais_pipeline():
    subscription = {
        "APIKey": API_KEY,
        "BoundingBoxes": [[[-90, -180], [90, 180]]],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
    }
    ship_cache = ship_cache_global   # référence au dict global (accessible au moniteur)

    while True:
        try:
            print(f"Connexion AIS → {WS_URL}")
            async with websockets.connect(WS_URL) as ws:
                await ws.send(json.dumps(subscription))
                print("✅ Flux AIS connecté\n")

                async for raw in ws:
                    msg      = json.loads(raw)
                    msg_type = msg.get('MessageType', '')

                    if msg_type == 'ShipStaticData':
                        meta = msg.get('Message', {}).get('ShipStaticData', {})
                        mmsi = meta.get('UserID') or meta.get('MMSI')
                        if mmsi:
                            raw_imo = meta.get('ImoNumber') or meta.get('IMO') or 0
                            imo_str = str(int(raw_imo)) if str(raw_imo).rstrip('.0').isdigit() and int(float(raw_imo)) > 0 else ''
                            ship_cache[mmsi] = {
                                'name': meta.get('Name', '').strip(),
                                'imo':  imo_str,
                                'type': meta.get('Type', {}).get('Name', 'Unknown')
                                        if isinstance(meta.get('Type'), dict) else 'Unknown'
                            }
                        continue

                    if msg_type != 'PositionReport':
                        continue

                    pr   = msg.get('Message', {}).get('PositionReport', {})
                    mmsi = pr.get('UserID') or pr.get('MMSI')
                    if not mmsi:
                        continue

                    lat   = pr.get('Latitude', 0.0)
                    lon   = pr.get('Longitude', 0.0)
                    speed = pr.get('Sog', 0.0)
                    cog   = pr.get('Cog', 0.0) or 0.0

                    info      = ship_cache.get(mmsi, {})
                    ship_name = info.get('name', '')
                    ship_imo  = info.get('imo', '')
                    ship_type = info.get('type', 'Unknown')

                    sig      = radio_fingerprint(mmsi, ship_type, lat, lon)
                    mmsi_i   = int(mmsi)
                    now      = datetime.now(timezone.utc)

                    # Si le navire était dark et reparaît → vérifier saut post-dark
                    prev_dark = dark_ships.pop(mmsi_i, None)
                    _dark_reapp = None
                    if isinstance(prev_dark, dict):
                        dark_h = (now.timestamp() - prev_dark['ts']) / 3600
                        if dark_h > CONFIG['dark_reapp_min_h']:
                            import math as _math
                            max_drift_km = prev_dark['sog'] * 1.852 * dark_h * 3
                            actual_km = haversine(prev_dark['lat'], prev_dark['lon'],
                                                  lat, lon)
                            cog_r   = _math.radians(prev_dark['cog'])
                            exp_lat = (prev_dark['lat']
                                       + (prev_dark['sog'] * 1.852 * dark_h / 111.32)
                                       * _math.cos(cog_r))
                            exp_lon = (prev_dark['lon']
                                       + (prev_dark['sog'] * 1.852 * dark_h
                                          / (111.32 * max(0.01, _math.cos(_math.radians(prev_dark['lat'])))))
                                       * _math.sin(cog_r))
                            jump_km = haversine(exp_lat, exp_lon, lat, lon)
                            if jump_km > CONFIG['dark_reapp_jump_km'] and actual_km > max_drift_km:
                                _dark_reapp = {
                                    'dark_h': round(dark_h, 1),
                                    'jump_km': round(jump_km),
                                    'prev_lat': prev_dark['lat'],
                                    'prev_lon': prev_dark['lon'],
                                }

                    # ── Fingerprint live : enregistrement / comparaison CFO ──
                    if mmsi_i not in live_profiles:
                        live_profiles[mmsi_i] = {
                            'cfo_ref':    sig['cfo_hz'],
                            'name':       ship_name,
                            'first_seen': now.strftime('%H:%M:%S'),
                            'count':      1,
                        }
                        cfo_drift       = 0.0
                        fp_first        = True
                    else:
                        lp = live_profiles[mmsi_i]
                        lp['count'] += 1
                        if ship_name:
                            lp['name'] = ship_name
                        cfo_drift = abs(sig['cfo_hz'] - lp['cfo_ref'])
                        fp_first  = False

                    alert_details = []
                    clean_checks  = []
                    mmsi_str      = str(mmsi)

                    # ── Check 0b : Réapparition post-dark suspecte ─────────
                    if _dark_reapp:
                        alert_details.append({
                            'code':   'DARK_REAPPEARANCE',
                            'label':  (
                                f'👻 Réapparition après {_dark_reapp["dark_h"]}h dark '
                                f'— saut de {_dark_reapp["jump_km"]} km hors trajectoire'
                            ),
                            'detail': (
                                f'Ce navire avait coupé son AIS pendant '
                                f'{_dark_reapp["dark_h"]} heures. Il reparaît à '
                                f'{_dark_reapp["jump_km"]} km de sa position extrapolée '
                                f'(dernière position connue : '
                                f'{_dark_reapp["prev_lat"]:.3f}°, '
                                f'{_dark_reapp["prev_lon"]:.3f}°). '
                                f'Ce type d\'anomalie est caractéristique d\'une escale '
                                f'clandestine, d\'un transbordement STS ou d\'un '
                                f'changement d\'identité effectué pendant la coupure AIS.'
                            ),
                        })

                    # ── Check 0 : Watchlist opérateur ──────────────────────
                    if mmsi_str in watchlist_mmsi or (ship_imo and ship_imo in watchlist_imo):
                        wl_id = f'IMO {ship_imo}' if ship_imo in watchlist_imo else f'MMSI {mmsi}'
                        alert_details.append({
                            'code':   'WATCHLIST_HIT',
                            'label':  f'🎯 Cible watchlist — {wl_id}',
                            'detail': (
                                f'Ce navire ({wl_id}) figure sur la liste de '
                                f'surveillance opérationnelle. Suivi prioritaire '
                                f'activé — toutes les positions et activités sont '
                                f'enregistrées avec priorité maximale.'
                            ),
                        })

                    # ── Check 1 : Base de sanctions consolidée (IMO / MMSI / nom) ──
                    sanction_hit = None
                    match_by     = ''
                    if ship_imo and ship_imo in sanctioned_imo_map:
                        sanction_hit = sanctioned_imo_map[ship_imo]
                        match_by = 'IMO'
                    elif mmsi_str in sanctioned_mmsi_map:
                        sanction_hit = sanctioned_mmsi_map[mmsi_str]
                        match_by = 'MMSI'
                    elif ship_name and ship_name.upper() in sanctioned_names:
                        sanction_hit = sanctions_df[
                            sanctions_df['name'] == ship_name.upper()
                        ].iloc[0]
                        match_by = 'Nom'

                    if sanction_hit is not None:
                        risk_cat = str(sanction_hit.get('risk_category', 'flagged') or 'flagged')
                        prog     = str(sanction_hit.get('program', '') or '').strip()
                        src      = str(sanction_hit.get('source', '') or '').strip()
                        r_label, r_detail = RISK_ALERT.get(risk_cat, RISK_ALERT['flagged'])
                        alert_details.append({
                            'code':   f'SANCTION_{risk_cat.upper()}',
                            'label':  f'{r_label} — {prog[:60]}',
                            'detail': (
                                f'{r_detail} '
                                f'[Source : {src} | Identifié par : {match_by}'
                                f'{" | IMO " + ship_imo if ship_imo else ""}]'
                            ),
                        })
                        # ── Check 1b : Changement de pavillon post-sanction ──
                        sanc_flag = str(sanction_hit.get('flag', '') or '').strip().lower()
                        mid_key   = int(str(mmsi)[:3])
                        mmsi_iso2 = MID_TO_ISO2.get(mid_key, '')
                        if (sanc_flag in FLAG_MISMATCH_RISK
                                and mmsi_iso2 and mmsi_iso2 != sanc_flag):
                            orig_f, orig_c = mmsi_flag(mmsi)
                            alert_details.append({
                                'code':   'FLAG_MISMATCH',
                                'label':  (
                                    f'🚩 Changement de pavillon suspecté — '
                                    f'{sanc_flag.upper()} → {orig_f} {orig_c}'
                                ),
                                'detail': (
                                    f'Ce navire est enregistré dans la base de sanctions '
                                    f'avec le pavillon {sanc_flag.upper()} '
                                    f'(pays sous embargo/surveillance), mais son MMSI '
                                    f'({mmsi}) correspond à {orig_c}. '
                                    f'Technique classique des flottes fantômes : '
                                    f're-immatriculation dans un État tiers pour '
                                    f'contourner les sanctions tout en conservant le '
                                    f'même MMSI sanctionné.'
                                ),
                            })
                    else:
                        id_info = f'IMO {ship_imo}' if ship_imo else f'MMSI {mmsi}'
                        clean_checks.append(
                            f'Absent de toutes les bases de sanctions '
                            f'(OFAC, OpenSanctions, UN 1718, UK OFSI) — '
                            f'{id_info} vérifié sur {len(sanctions_df):,} entrées.'
                        )

                    # ── Check 2 : Vitesse anormale ──
                    if speed > CONFIG['impossible_speed']:
                        alert_details.append({
                            'code':   'SPEED_IMPOSSIBLE',
                            'label':  f'Vitesse physiquement impossible ({speed:.1f} kt)',
                            'detail': (
                                f'{speed:.1f} nœuds dépasse la limite physique de tout '
                                f'navire commercial ({CONFIG["impossible_speed"]} kt). '
                                f'Très probable : spoofing de position AIS ou erreur '
                                f'de capteur GPS.'
                            ),
                        })
                    else:
                        type_max = MAX_SPEED_KT.get(ship_type, MAX_SPEED_KT.get('Unknown', 35))
                        if speed > type_max and speed > 5:
                            alert_details.append({
                                'code':   'SPEED_ANOMALY',
                                'label':  (
                                    f'Vitesse anormale pour un {ship_type} '
                                    f'({speed:.1f} kt > {type_max} kt)'
                                ),
                                'detail': (
                                    f'Un {ship_type} navigue normalement à moins de '
                                    f'{type_max} nœuds. La vitesse déclarée de '
                                    f'{speed:.1f} kt est suspecte : possible spoofing '
                                    f'de position, moteur hors-norme, ou données AIS '
                                    f'incorrectes.'
                                ),
                            })
                        else:
                            clean_checks.append(
                                f'Vitesse cohérente avec le type ({ship_type}) '
                                f': {speed:.1f} kt.'
                            )

                    # ── Check 3 : Position Null Island (0°, 0°) ──
                    if abs(lat) < 0.05 and abs(lon) < 0.05:
                        alert_details.append({
                            'code':   'NULL_ISLAND',
                            'label':  'Position à "Null Island" (0°, 0°)',
                            'detail': (
                                'Le navire signale sa position exactement à (0°, 0°), '
                                'un point fictif au large du Ghana. '
                                'Signature classique d\'un transpondeur AIS défaillant '
                                'ou d\'un spoofing volontaire de position.'
                            ),
                        })
                    else:
                        clean_checks.append(
                            f'Position géographique valide '
                            f'({lat:.3f}°, {lon:.3f}°).'
                        )

                    # ── Check 4 : Zone géographique à risque ──
                    zone_hit = None
                    for zone in HIGH_RISK_ZONES:
                        lat_min, lat_max = zone['lat']
                        lon_min, lon_max = zone['lon']
                        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                            zone_hit = zone
                            break

                    if zone_hit:
                        alert_details.append({
                            'code':   'HIGH_RISK_ZONE',
                            'label':  f'Zone à risque : {zone_hit["name"]}',
                            'detail': (
                                f'Le navire se trouve dans une zone classée à risque '
                                f'élevé : {zone_hit["name"]}. '
                                f'Raison : {zone_hit["reason"]}. '
                                f'Une présence dans cette zone justifie une surveillance '
                                f'renforcée des mouvements et escales.'
                            ),
                        })
                    else:
                        clean_checks.append('Zone géographique sans risque connu.')

                    # ── Check 5 : Saut de position (téléportation) ──
                    prev = position_history.get(mmsi)
                    if prev:
                        dt_s = max((now - prev['ts']).total_seconds(), 1)
                        if dt_s < 3600:
                            dist_km   = haversine(prev['lat'], prev['lon'], lat, lon)
                            max_km    = speed * 1.852 * dt_s / 3600 * 3
                            if dist_km > max_km + 20:
                                alert_details.append({
                                    'code':   'POSITION_JUMP',
                                    'label':  (
                                        f'Saut de position suspect '
                                        f'({dist_km:.0f} km en {dt_s/60:.0f} min)'
                                    ),
                                    'detail': (
                                        f'En {dt_s/60:.0f} minutes, le navire est passé '
                                        f'de ({prev["lat"]:.2f}°, {prev["lon"]:.2f}°) '
                                        f'à ({lat:.2f}°, {lon:.2f}°) — soit '
                                        f'{dist_km:.0f} km. À {speed:.1f} kt, '
                                        f'le maximum possible est {max_km:.0f} km. '
                                        f'Possible spoofing ou clonage de MMSI.'
                                    ),
                                })
                    position_history[mmsi] = {
                        'lat': lat, 'lon': lon, 'ts': now,
                        'sog': speed, 'cog': cog,
                    }

                    # Mise à jour de la trajectoire (15 derniers points)
                    trail = trail_history.setdefault(mmsi, [])
                    trail.append([lat, lon])
                    if len(trail) > TRAIL_MAX:
                        trail.pop(0)

                    # Historique loitering (fenêtre 3h)
                    lh = loiter_history.setdefault(mmsi, deque())
                    lh.append((lat, lon, now.timestamp()))
                    cutoff_lh = now.timestamp() - 3 * 3600
                    while lh and lh[0][2] < cutoff_lh:
                        lh.popleft()

                    # ── Check 6 : Anomalies de la signature radio AIS ──
                    r_freq   = sig['frequency']
                    r_rssi   = sig['rssi_dbm']
                    r_rssi_n = sig['rssi_nominal_dbm']
                    r_snr    = sig['signal_to_noise_ratio']
                    r_ch     = sig['channel']
                    r_cfo    = sig['cfo_hz']
                    r_pwr    = sig['power']

                    radio_alerts = []

                    # SNR < 35 dB : signal dégradé (scintillation sévère ou puissance réduite)
                    if r_snr < 35.0:
                        radio_alerts.append({
                            'code':   'RADIO_SNR_DEGRADE',
                            'label':  (
                                f'Signal AIS dégradé — SNR {r_snr:.0f} dB '
                                f'(seuil : 35 dB)'
                            ),
                            'detail': (
                                f'Le rapport signal/bruit ({r_snr:.0f} dB) est en '
                                f'dessous du seuil de décodage fiable AIS. '
                                f'RSSI mesuré {r_rssi:.0f} dBm vs nominal '
                                f'{r_rssi_n:.0f} dBm. '
                                f'Causes possibles : puissance d\'émission réduite '
                                f'volontairement (furtivité AIS), '
                                f'équipement défaillant, ou scintillation '
                                f'atmosphérique sévère. [Modèle ITU-R M.1371]'
                            ),
                        })

                    # |CFO| > 250 Hz : oscillateur hors spec (2.3 σ pour TCXO standard)
                    if abs(r_cfo) > 250.0:
                        radio_alerts.append({
                            'code':   'RADIO_CFO_EXCESSIF',
                            'label':  (
                                f'Décalage fréquentiel excessif — CFO '
                                f'{r_cfo:+.0f} Hz (±250 Hz max)'
                            ),
                            'detail': (
                                f'Le décalage de fréquence portante (CFO) de '
                                f'{abs(r_cfo):.0f} Hz dépasse ±250 Hz — '
                                f'limite 2,3 σ pour un TCXO conforme ITU-R. '
                                f'Cela peut indiquer un transpondeur non homologué, '
                                f'un oscillateur vieilli ou un équipement de substitution '
                                f'non certifié. '
                                f'Voie : Ch{r_ch} ({r_freq:.3f} MHz) — '
                                f'Puissance : {r_pwr:.1f} W. [Modèle ITU-R M.1371]'
                            ),
                        })

                    # Dérive CFO : même MMSI, signature RF différente → clonage possible
                    if not fp_first and cfo_drift > 30.0:
                        lp = live_profiles[mmsi_i]
                        radio_alerts.append({
                            'code':   'RADIO_CFO_DERIVE',
                            'label':  (
                                f'Empreinte RF incohérente — dérive CFO '
                                f'{cfo_drift:.0f} Hz (réf. {lp["cfo_ref"]:+.0f} Hz)'
                            ),
                            'detail': (
                                f'Le CFO mesuré ({r_cfo:+.0f} Hz) diffère de '
                                f'{cfo_drift:.0f} Hz de la valeur de référence '
                                f'enregistrée à {lp["first_seen"]} '
                                f'({lp["cfo_ref"]:+.0f} Hz). '
                                f'Un écart > 30 Hz dépasse le bruit de mesure '
                                f'(±8 Hz) et peut indiquer un transmetteur '
                                f'différent — clonage de MMSI suspecté. '
                                f'[Modèle physique ITU-R M.1371-5]'
                            ),
                        })

                    if radio_alerts:
                        alert_details.extend(radio_alerts)
                    else:
                        lp        = live_profiles[mmsi_i]
                        fp_status = (
                            f'1ère détection · CFO {r_cfo:+.0f} Hz enregistré'
                            if fp_first else
                            f'Vu {lp["count"]}× depuis {lp["first_seen"]} · '
                            f'dérive CFO {cfo_drift:.0f} Hz'
                        )
                        clean_checks.append(
                            f'Signature AIS conforme — Ch{r_ch} {r_freq:.3f} MHz · '
                            f'RSSI {r_rssi:.0f} dBm · SNR {r_snr:.0f} dB · '
                            f'CFO {r_cfo:+.0f} Hz · {r_pwr:.1f} W · {fp_status} '
                            f'[ITU-R M.1371-5]'
                        )

                    alert_level = (
                        'red'    if len(alert_details) >= 2 else
                        'orange' if len(alert_details) == 1 else
                        'green'
                    )

                    flag, country = mmsi_flag(mmsi)
                    risk_score    = compute_risk_score(alert_details)

                    event = {
                        'event_type':    'ais',
                        'mmsi':          mmsi,
                        'name':          ship_name or f'MMSI {mmsi}',
                        'flag':          flag,
                        'country':       country,
                        'risk_score':    risk_score,
                        'type':          ship_type,
                        'lat':           lat,
                        'lon':           lon,
                        'speed':         round(speed, 1),
                        # Signature radio — modèle physique ITU-R M.1371-5
                        'freq':          sig['frequency'],
                        'bw':            sig['bandwidth'],
                        'power':         sig['power'],
                        'snr':           sig['signal_to_noise_ratio'],
                        'rssi_dbm':      sig['rssi_dbm'],
                        'channel':       sig['channel'],
                        'cfo_hz':        sig['cfo_hz'],
                        'dist_km':       sig['dist_km'],
                        # Empreinte radio live
                        'fp_first_seen': live_profiles[mmsi_i]['first_seen'],
                        'fp_count':      live_profiles[mmsi_i]['count'],
                        'fp_cfo_ref':    round(live_profiles[mmsi_i]['cfo_ref'], 1),
                        'fp_cfo_drift':  round(cfo_drift, 1),
                        'trail':         list(trail_history.get(mmsi, [])),
                        'alert_details': alert_details,
                        'clean_checks':  clean_checks,
                        'alerts':        [a['label'] for a in alert_details],
                        'alert_level':   alert_level,
                        'timestamp':     now.strftime('%H:%M:%S'),
                        'ts_epoch':      int(now.timestamp()),
                    }
                    log_event(alert_level,
                               [a['code'] for a in alert_details],
                               zone_hit['name'] if zone_hit else '')

                    # Déduplication : même navire, mêmes codes → suppress_card
                    now_ts_b = time.time()
                    new_codes = frozenset(a['code'] for a in alert_details)
                    prev_b    = last_broadcast.get(mmsi_i)
                    suppress  = False
                    if prev_b and prev_b['codes'] == new_codes and alert_level != 'green':
                        age = now_ts_b - prev_b['ts']
                        limit = CONFIG['dedup_red_s'] if alert_level == 'red' else CONFIG['dedup_orange_s']
                        suppress = age < limit
                    if not suppress:
                        last_broadcast[mmsi_i] = {'codes': new_codes, 'ts': now_ts_b}
                    event['suppress_card'] = suppress

                    if alert_level in ('orange', 'red') and not suppress:
                        db_insert(event)
                    await broadcast(event)

        except Exception as exc:
            print(f"Erreur AIS : {exc} — reconnexion dans 5 s")
            await asyncio.sleep(5)

# ── Moniteur Dark Shipping ─────────────────────────────────────────────────
async def dark_shipping_monitor():
    """
    Toutes les 60 s, vérifie les navires silencieux depuis > DARK_MIN minutes.
    Un navire qui coupe son AIS en route est un signal fort d'activité illicite.
    """
    await asyncio.sleep(90)   # laisser le temps au flux de se remplir
    while True:
        now = datetime.now(timezone.utc)
        for mmsi, pos in list(position_history.items()):
            minutes_silent = (now - pos['ts']).total_seconds() / 60
            if mmsi in dark_ships:
                # Oublier les très anciens (navire probablement au port)
                if minutes_silent > CONFIG['dark_expire_min']:
                    dark_ships.pop(mmsi, None)
                continue
            if minutes_silent < CONFIG['dark_min']:
                continue

            dark_ships[mmsi] = {
                'lat': pos['lat'], 'lon': pos['lon'],
                'ts': now.timestamp(),
                'sog': pos.get('sog', 0.0), 'cog': pos.get('cog', 0.0),
            }
            info = ship_cache_global.get(mmsi, {})
            name = info.get('name', '') or f'MMSI {mmsi}'
            d_flag, d_country = mmsi_flag(mmsi)
            event = {
                'event_type':      'dark_shipping',
                'mmsi':            mmsi,
                'name':            name,
                'flag':            d_flag,
                'country':         d_country,
                'risk_score':      4.0,
                'type':            info.get('type', 'Unknown'),
                'last_lat':        pos['lat'],
                'last_lon':        pos['lon'],
                'minutes_silent':  round(minutes_silent),
                'alert_level':     'red',
                'alert_details':   [{
                    'code':   'DARK_SHIPPING',
                    'label':  f'AIS coupé depuis {round(minutes_silent)} min',
                    'detail': (
                        f'Le navire {name} (MMSI {mmsi}) a cessé d\'émettre '
                        f'depuis {round(minutes_silent)} minutes. '
                        f'Dernière position connue : '
                        f'{pos["lat"]:.3f}°, {pos["lon"]:.3f}°. '
                        f'La coupure volontaire de l\'AIS est une technique '
                        f'classique des navires pratiquant le dark shipping '
                        f'pour contourner les sanctions ou dissimuler '
                        f'des transferts illicites de cargaison.'
                    ),
                }],
                'alerts':          [f'AIS coupé depuis {round(minutes_silent)} min'],
                'timestamp':       now.strftime('%H:%M:%S'),
                'ts_epoch':        int(now.timestamp()),
            }
            log_event('dark', ['DARK_SHIPPING'])
            db_insert(event)
            await broadcast(event)
            print(f"  🌑 DARK SHIPPING : {name} (MMSI {mmsi}) — {round(minutes_silent)} min sans signal")

        await asyncio.sleep(60)


# ── Moniteur STS + Loitering ───────────────────────────────────────────────
async def detection_monitor():
    """Détecte les transferts STS et comportements de loitering toutes les 60 s."""
    await asyncio.sleep(120)
    while True:
        now    = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        # ── Loitering ──────────────────────────────────────────────────────
        for mmsi, lh in list(loiter_history.items()):
            if len(lh) < 10:
                continue
            time_span = lh[-1][2] - lh[0][2]
            if time_span < CONFIG['loiter_min_h'] * 3600:
                continue
            # Réinitialiser l'alerte après 3h
            if mmsi in loitering_alerted:
                if now_ts - loitering_alerted[mmsi] > 3 * 3600:
                    del loitering_alerted[mmsi]
                else:
                    continue
            lats  = [h[0] for h in lh]
            lons  = [h[1] for h in lh]
            clat  = sum(lats) / len(lats)
            clon  = sum(lons) / len(lons)
            max_d = max(haversine(clat, clon, h[0], h[1]) for h in lh)
            if max_d > CONFIG['loiter_radius_km']:
                continue
            loitering_alerted[mmsi] = now_ts
            info  = ship_cache_global.get(mmsi, {})
            name  = info.get('name', '') or f'MMSI {mmsi}'
            flag, country = mmsi_flag(mmsi)
            dur   = round(time_span / 60)
            event = {
                'event_type':    'loitering',
                'mmsi':          mmsi,
                'name':          name,
                'flag':          flag,
                'country':       country,
                'risk_score':    3.0,
                'lat':           clat,
                'lon':           clon,
                'last_lat':      lh[-1][0],
                'last_lon':      lh[-1][1],
                'duration_min':  dur,
                'radius_km':     round(max_d, 1),
                'alert_level':   'orange',
                'alert_details': [{
                    'code':   'LOITERING',
                    'label':  f'⚓ Loitering — {dur} min dans {round(max_d,1)} km',
                    'detail': (
                        f'{name} (MMSI {mmsi}) stationne dans un rayon de '
                        f'{round(max_d,1)} km depuis {dur} minutes. '
                        f'Comportement typique d\'une attente de rendez-vous '
                        f'(STS, chargement illicite) ou d\'une panne non déclarée. '
                        f'Position centrale : {clat:.3f}°, {clon:.3f}°.'
                    ),
                }],
                'alerts':    [f'Loitering {dur} min dans {round(max_d,1)} km'],
                'timestamp': now.strftime('%H:%M:%S'),
                'ts_epoch':  int(now_ts),
            }
            log_event('orange', ['LOITERING'])
            db_insert(event)
            await broadcast(event)
            print(f"  ⚓ LOITERING : {name} (MMSI {mmsi}) — {dur} min / {round(max_d,1)} km")

        # ── STS detection ──────────────────────────────────────────────────
        # Grille 0.01° (~1.1 km) pour éviter O(n²) sur 11k navires
        grid: dict = defaultdict(list)
        cutoff_sts = now_ts - 300
        for mmsi, pos in list(position_history.items()):
            if pos['ts'].timestamp() < cutoff_sts:
                continue
            cell = (int(pos['lat'] * 100), int(pos['lon'] * 100))
            grid[cell].append((mmsi, pos))

        active_pairs: set = set()
        for ships in grid.values():
            if len(ships) < 2:
                continue
            for i in range(len(ships)):
                for j in range(i + 1, len(ships)):
                    m1, p1 = ships[i]
                    m2, p2 = ships[j]
                    dist = haversine(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
                    if dist > CONFIG['sts_dist_km']:
                        continue
                    key = frozenset({m1, m2})
                    active_pairs.add(key)
                    if key not in sts_proximity:
                        sts_proximity[key] = {
                            'count': 1, 'first_ts': now_ts,
                            'alerted': False,
                            'm1': m1, 'm2': m2, 'p1': p1, 'p2': p2,
                        }
                    else:
                        e = sts_proximity[key]
                        e['count'] += 1
                        e['p1'], e['p2'] = p1, p2
                        if e['count'] >= CONFIG['sts_min_checks'] and not e['alerted']:
                            e['alerted'] = True
                            i1 = ship_cache_global.get(m1, {})
                            i2 = ship_cache_global.get(m2, {})
                            n1 = i1.get('name', '') or f'MMSI {m1}'
                            n2 = i2.get('name', '') or f'MMSI {m2}'
                            f1, c1 = mmsi_flag(m1)
                            f2, c2 = mmsi_flag(m2)
                            dur  = round((now_ts - e['first_ts']) / 60)
                            dm   = round(dist * 1000)
                            clat = (p1['lat'] + p2['lat']) / 2
                            clon = (p1['lon'] + p2['lon']) / 2
                            ev = {
                                'event_type':    'sts',
                                'mmsi':          m1,
                                'mmsi2':         str(m2),
                                'name':          n1,
                                'name2':         n2,
                                'flag':          f1,
                                'flag2':         f2,
                                'country':       c1,
                                'country2':      c2,
                                'risk_score':    4.5,
                                'lat':           clat,
                                'lon':           clon,
                                'dist_m':        dm,
                                'duration_min':  dur,
                                'alert_level':   'red',
                                'alert_details': [{
                                    'code':  'STS_DETECTED',
                                    'label': (
                                        f'🔴 Transfert STS suspecté — '
                                        f'{n1} / {n2} ({dm} m, {dur} min)'
                                    ),
                                    'detail': (
                                        f'Deux navires en proximité immédiate ({dm} m) '
                                        f'depuis {dur} minutes : '
                                        f'{n1} (MMSI {m1}, {c1}) et '
                                        f'{n2} (MMSI {m2}, {c2}). '
                                        f'Configuration caractéristique d\'un transfert '
                                        f'de cargaison STS — technique utilisée par les '
                                        f'flottes fantômes pour transférer du pétrole '
                                        f'sanctionné sans escale portuaire contrôlée. '
                                        f'Position : {clat:.3f}°, {clon:.3f}°.'
                                    ),
                                }],
                                'alerts':    [
                                    f'STS suspecté : {n1} ↔ {n2} '
                                    f'à {dm} m depuis {dur} min'
                                ],
                                'timestamp': now.strftime('%H:%M:%S'),
                                'ts_epoch':  int(now_ts),
                            }
                            log_event('red', ['STS_DETECTED'])
                            db_insert(ev)
                            await broadcast(ev)
                            print(
                                f"  🔴 STS : {n1} ↔ {n2} "
                                f"— {dm} m / {dur} min"
                            )

        for key in list(sts_proximity.keys()):
            if key not in active_pairs:
                del sts_proximity[key]

        await asyncio.sleep(60)

# ── Serveur HTTP + endpoint /api/stats ─────────────────────────────────────
class SilentHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/stats':
            self._serve_stats()
        elif self.path.startswith('/api/history'):
            self._serve_history()
        elif self.path.startswith('/api/vessel/'):
            self._serve_vessel()
        elif self.path == '/api/config':
            self._serve_config()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/config':
            self._update_config()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_config(self):
        body = json.dumps(CONFIG, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _update_config(self):
        length = int(self.headers.get('Content-Length', 0))
        raw    = self.rfile.read(length)
        try:
            patch = json.loads(raw)
        except Exception:
            self.send_response(400)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            return
        int_keys = {'sts_min_checks', 'dark_min', 'dark_expire_min',
                    'dedup_orange_s', 'dedup_red_s'}
        for k, v in patch.items():
            if k in CONFIG:
                CONFIG[k] = int(v) if k in int_keys else float(v)
        body = json.dumps({'ok': True, 'config': CONFIG}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _serve_stats(self):
        now_ts  = time.time()
        cutoff6 = now_ts - 6 * 3600

        # Compteurs par niveau
        counts = defaultdict(int)
        type_counts: dict = defaultdict(int)
        zone_counts: dict = defaultdict(int)
        hourly = [0] * 6       # index 0 = il y a 5h, index 5 = heure en cours

        for entry in alert_log:
            if entry['ts'] < cutoff6:
                continue
            counts[entry['level']] += 1
            for t in entry['types']:
                type_counts[t] += 1
            if entry['zone']:
                zone_counts[entry['zone']] += 1
            h = min(5, int((now_ts - entry['ts']) / 3600))
            hourly[5 - h] += 1

        # Navires actifs (vus dans la dernière heure)
        active = sum(
            1 for pos in position_history.values()
            if (now_ts - pos['ts'].timestamp()) < 3600
        )

        # Top 5 navires les plus alertés (depuis SQLite)
        with _db_lock, sqlite3.connect(DB_PATH) as c:
            top_rows = c.execute(
                '''SELECT mmsi, name,
                   COUNT(*) as cnt,
                   SUM(CASE alert_level WHEN 'red' THEN 2 WHEN 'orange' THEN 1 ELSE 0 END) as score
                   FROM events
                   GROUP BY mmsi ORDER BY score DESC, cnt DESC LIMIT 5'''
            ).fetchall()
        top_vessels = [
            {'mmsi': r[0], 'name': r[1] or f'MMSI {r[0]}',
             'count': r[2], 'score': r[3]}
            for r in top_rows
        ]

        body = json.dumps({
            'counts':        dict(counts),
            'type_counts':   dict(sorted(type_counts.items(), key=lambda x: -x[1])[:8]),
            'zone_counts':   dict(sorted(zone_counts.items(), key=lambda x: -x[1])),
            'hourly':        hourly,
            'total_vessels': len(position_history),
            'active_vessels': active,
            'dark_count':    len(dark_ships),
            'uptime_min':    round((now_ts - server_start.timestamp()) / 60),
            'top_vessels':   top_vessels,
        }, ensure_ascii=False).encode()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _serve_history(self):
        qs    = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        limit = min(int(qs.get('limit', ['200'])[0]), 1000)
        level = qs.get('level', [''])[0]
        since = int(qs.get('since', ['0'])[0])   # secondes dans le passé (0 = tout)

        cols = ['id', 'mmsi', 'name', 'alert_level', 'alert_codes',
                'alerts_json', 'alert_details_json', 'lat', 'lon', 'ts']
        from datetime import datetime as _dt
        since_ts = (_dt.utcfromtimestamp(time.time() - since).strftime('%Y-%m-%d %H:%M:%S')
                    if since else '1970-01-01')
        with _db_lock, sqlite3.connect(DB_PATH) as c:
            if level:
                rows = c.execute(
                    f'SELECT {",".join(cols)} FROM events '
                    'WHERE alert_level=? AND ts >= ? ORDER BY id DESC LIMIT ?',
                    (level, since_ts, limit)
                ).fetchall()
            else:
                rows = c.execute(
                    f'SELECT {",".join(cols)} FROM events '
                    'WHERE ts >= ? ORDER BY id DESC LIMIT ?',
                    (since_ts, limit)
                ).fetchall()

        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d['alert_codes']       = json.loads(d['alert_codes']       or '[]')
            d['alerts_json']       = json.loads(d['alerts_json']       or '[]')
            d['alert_details_json']= json.loads(d['alert_details_json']or '[]')
            result.append(d)

        body = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _serve_vessel(self):
        mmsi = self.path.split('/')[-1].strip()
        cols = ['id', 'mmsi', 'name', 'alert_level', 'alert_codes',
                'alerts_json', 'alert_details_json', 'lat', 'lon', 'ts']
        with _db_lock, sqlite3.connect(DB_PATH) as c:
            rows = c.execute(
                f'SELECT {",".join(cols)} FROM events '
                'WHERE mmsi=? ORDER BY id DESC LIMIT 50',
                (mmsi,)
            ).fetchall()
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d['alert_codes']        = json.loads(d['alert_codes']        or '[]')
            d['alerts_json']        = json.loads(d['alerts_json']        or '[]')
            d['alert_details_json'] = json.loads(d['alert_details_json'] or '[]')
            result.append(d)
        body = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

def start_http():
    httpd = HTTPServer(('', 8080), SilentHandler)
    httpd.serve_forever()

# ── Entrée ──────────────────────────────────────────────────────────────────
async def main():
    threading.Thread(target=start_http, daemon=True).start()
    print("━" * 55)
    print("  🗺  Dashboard → http://localhost:8080/dashboard.html")
    print("  📡 WebSocket  → ws://localhost:8765")
    print("━" * 55)

    async with websockets.serve(ws_handler, 'localhost', 8765):
        await asyncio.gather(ais_pipeline(), dark_shipping_monitor(), detection_monitor())

if __name__ == '__main__':
    asyncio.run(main())
