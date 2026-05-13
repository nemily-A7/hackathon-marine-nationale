"""
export_data.py — Exporte les données réelles de detection_engine vers JSON
pour le dashboard React.

Lancer : python3 export_data.py
Sortie : dashboard/public/data/{ships,detections,zones}.json
"""
import sys, os, json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detection_engine import load_data, run_detection, DEFAULT_CONFIG

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
ZONES_PATH = os.path.join(BASE_DIR, "data", "zones_risques_2.csv")
OUT_DIR    = os.path.join(BASE_DIR, "dashboard", "public", "data")

os.makedirs(OUT_DIR, exist_ok=True)

print("Chargement des données CSV…")
ships, ais, radio, zones = load_data(DATA_DIR, ZONES_PATH)

# Seuil très bas pour exporter TOUTES les détections — React filtre ensuite
cfg = {**DEFAULT_CONFIG, "threshold": 0.1}

print("Exécution du moteur de détection…")
result = run_detection(cfg, ships, ais, radio, zones)

sdf = result["ships_df"]
det = result["detections"]

def to_json_safe(val):
    if val is None:
        return None
    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val

def df_to_json(df, cols):
    rows = []
    df2 = df[[c for c in cols if c in df.columns]].copy()
    for _, row in df2.iterrows():
        rows.append({k: to_json_safe(v) for k, v in row.items()})
    return rows

# ── Ships ──────────────────────────────────────────────────────────────────
SHIP_COLS = [
    "mmsi", "name", "type", "flag", "length", "year_built", "gross_tonnage",
    "destination", "last_status", "lat_ais", "lon_ais",
    "speed_max", "speed_mean", "rot_max", "rot_mean",
    "snr_mean", "signal_quality", "course_deviation",
    "n_sync_pairs", "nb_old_names", "speed_conflict_ratio",
    "ais_obligated", "nb_ais", "ais_off_ratio",
]
ships_json = df_to_json(sdf, SHIP_COLS)
with open(os.path.join(OUT_DIR, "ships.json"), "w", encoding="utf-8") as f:
    json.dump(ships_json, f, ensure_ascii=False, separators=(",", ":"))
print(f"✓ {len(ships_json)} navires exportés")

# ── Detections ─────────────────────────────────────────────────────────────
DET_COLS = [
    "mmsi", "name", "flag", "type", "lat", "lon",
    "fraud_type", "confidence", "confidence_final",
    "signal_quality", "description",
    "risk_zone_name", "risk_zone_type", "risk_zone_level",
]
det_json = df_to_json(det, DET_COLS)
with open(os.path.join(OUT_DIR, "detections.json"), "w", encoding="utf-8") as f:
    json.dump(det_json, f, ensure_ascii=False, separators=(",", ":"))
print(f"✓ {len(det_json)} détections exportées")

# ── Zones ──────────────────────────────────────────────────────────────────
zones_json = []
if zones is not None:
    for _, z in zones.iterrows():
        poly = z["polygon"]
        if isinstance(poly, str):
            import ast
            poly = ast.literal_eval(poly)
        zones_json.append({
            "id":      str(z.get("nom", "")).lower().replace(" ", "_"),
            "name":    z.get("nom", ""),
            "level":   z.get("niveau", ""),
            "type":    z.get("type", ""),
            "polygon": [[float(lat), float(lon)] for lat, lon in poly],
        })
with open(os.path.join(OUT_DIR, "zones.json"), "w", encoding="utf-8") as f:
    json.dump(zones_json, f, ensure_ascii=False, separators=(",", ":"))
print(f"✓ {len(zones_json)} zones exportées")

print(f"\nFichiers dans : {OUT_DIR}")
