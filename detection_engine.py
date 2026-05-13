"""
detection_engine.py — Moteur de détection de fraude maritime V2
Toute la logique est paramétrée via un dict `config`.
"""
import os
import ast
import pandas as pd
import numpy as np

# ─── Configuration par défaut ─────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "threshold": 0.5,
    "speed_max_by_type": {
        "Container Ship": 25, "Tanker": 16, "Bulk Carrier": 15,
        "General Cargo": 18, "Passenger Ship": 30, "Fishing Vessel": 14,
        "Tugboat": 14, "Pilot Vessel": 28, "Sailboat": 12,
        "Yacht": 22, "Military": 35, "Other": 20,
    },
    "default_speed_max": 20,
    "overspeed_margin": 1.2,
    "rot_max_by_type": {
        "Container Ship": 20, "Tanker": 10, "Bulk Carrier": 10,
        "General Cargo": 15, "Passenger Ship": 25, "Fishing Vessel": 40,
        "Tugboat": 60, "Pilot Vessel": 60, "Sailboat": 30,
        "Yacht": 35, "Military": 60, "Other": 30,
    },
    "default_rot_max": 30,
    "rot_threshold_multiplier": 1.5,
    "sync_window_seconds": 3600,
    "dist_min_km": 50,
    "dist_max_km": 500,
    "no_sync_temp_factor": 0.6,
    "snr_high": 30,
    "snr_mid": 15,
    "dest_angle_tolerance": 45,
    "boost_by_niveau": {1: 0.02, 2: 0.05, 3: 0.10, 4: 0.15},
}

PORT_COORDS = {
    "Hambourg":    (53.55,  10.00),
    "Tokyo":       (35.65, 139.75),
    "Singapour":   ( 1.28, 103.83),
    "Shanghai":    (31.23, 121.47),
    "Suez":        (30.00,  32.55),
    "Dubaï":       (25.27,  55.33),
    "Marseille":   (43.30,   5.35),
    "New York":    (40.67, -74.00),
    "Los Angeles": (33.73,-118.27),
    "Rotterdam":   (51.93,   4.48),
}

# ─── Utilitaires géographiques ────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def bearing_degrees(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = np.sin(dlon) * np.cos(lat2)
    y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360


def angular_diff(a, b):
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def point_in_polygon(lat, lon, polygon):
    n = len(polygon)
    inside = False
    for i in range(n):
        lat_a, lon_a = polygon[i]
        lat_b, lon_b = polygon[(i + 1) % n]
        if (lon_a <= lon < lon_b) or (lon_b <= lon < lon_a):
            lat_intersect = lat_a + (lon - lon_a) / (lon_b - lon_a) * (lat_b - lat_a)
            if lat < lat_intersect:
                inside = not inside
    return inside

# ─── Chargement des données ───────────────────────────────────────────────────

def load_data(data_dir, zones_path=None):
    ships = pd.read_csv(os.path.join(data_dir, "ships_large.csv"))
    radio = pd.read_csv(os.path.join(data_dir, "radio_signatures_large.csv"))
    ais   = pd.read_csv(os.path.join(data_dir, "ais_data_large.csv"))

    for df in [ships, radio, ais]:
        df["mmsi"] = df["mmsi"].astype(str)

    ais["timestamp_dt"]   = pd.to_datetime(ais["timestamp"])
    radio["timestamp_dt"] = pd.to_datetime(radio["timestamp"])

    zones = None
    if zones_path and os.path.exists(zones_path):
        zones = pd.read_csv(zones_path)
        zones["polygon"] = zones["coords"].apply(ast.literal_eval)

    return ships, ais, radio, zones

# ─── Feature Engineering ─────────────────────────────────────────────────────

def build_features(ships, ais, radio, config):
    # — AIS —
    ais_stats = ais.groupby("mmsi").agg(
        nb_ais            = ("mmsi",        "count"),
        ais_off_ratio     = ("ais_active",  lambda x: (x == False).mean()),
        speed_max         = ("speed",       "max"),
        speed_mean        = ("speed",       "mean"),
        rot_max           = ("rot",         lambda x: x.abs().max()),
        rot_mean          = ("rot",         lambda x: x.abs().mean()),
        lat_ais           = ("latitude",    "last"),
        lon_ais           = ("longitude",   "last"),
        last_status       = ("status",      "last"),
        last_speed        = ("speed",       "last"),
        last_ais_ts       = ("timestamp_dt","max"),
    ).reset_index()

    # Nombre de changements de statut
    nav_col = "navigational_status" if "navigational_status" in ais.columns else "status"
    ais_sorted = ais.sort_values(["mmsi", "timestamp"])
    status_changes = (
        ais_sorted.groupby("mmsi")[nav_col]
        .apply(lambda x: (x != x.shift()).sum() - 1)
        .reset_index()
    )
    status_changes.columns = ["mmsi", "nb_status_changes"]
    ais_stats = ais_stats.merge(status_changes, on="mmsi", how="left")

    # Ratio conflit vitesse/statut
    ais["speed_status_conflict"] = (
        (ais["status"].isin(["Moored", "At Anchor"]) & (ais["speed"] > 3)) |
        ((ais["status"] == "Under Way") & (ais["speed"] < 0.5))
    )
    conflict_ratio = ais.groupby("mmsi")["speed_status_conflict"].mean().reset_index()
    conflict_ratio.columns = ["mmsi", "speed_conflict_ratio"]
    ais_stats = ais_stats.merge(conflict_ratio, on="mmsi", how="left")

    # — Radio —
    radio_stats = radio.groupby("mmsi").agg(
        nb_radio             = ("mmsi",                  "count"),
        freq_mean            = ("frequency",             "mean"),
        freq_std             = ("frequency",             "std"),
        snr_mean             = ("signal_to_noise_ratio", "mean"),
        signal_strength_mean = ("signal_strength",       "mean"),
        power_mean           = ("power",                 "mean"),
        lat_radio            = ("location_lat",          "last"),
        lon_radio            = ("location_lon",          "last"),
        last_radio_ts        = ("timestamp_dt",          "max"),
        pulse_mode           = ("pulse_pattern",         lambda x: x.mode()[0] if not x.empty else None),
    ).reset_index()

    # — Ships —
    ships = ships.copy()
    ships["nb_old_names"] = ships["historical_names"].fillna("").apply(
        lambda x: len([n for n in x.split(",") if n.strip()])
    )
    ships["ais_obligated"] = (
        (ships["type"] == "Passenger Ship") |
        (ships["gross_tonnage"] >= 300) |
        (ships["year_built"] > 2002)
    )

    df = ships.merge(ais_stats, on="mmsi", how="left")
    df = df.merge(radio_stats, on="mmsi", how="left")

    # — Synchronisation temporelle AIS ↔ Radio —
    sync_window = config.get("sync_window_seconds", 3600)
    ais_ts   = ais[["mmsi", "timestamp_dt", "latitude", "longitude"]].copy()
    radio_ts = radio[["mmsi", "timestamp_dt", "location_lat", "location_lon",
                       "signal_to_noise_ratio"]].copy()
    radio_ts = radio_ts.rename(columns={
        "timestamp_dt": "timestamp_r", "location_lat": "lat_r",
        "location_lon": "lon_r", "signal_to_noise_ratio": "snr_r",
    })

    pairs = ais_ts.merge(radio_ts, on="mmsi", how="inner")
    pairs["dt_seconds"] = (pairs["timestamp_dt"] - pairs["timestamp_r"]).abs().dt.total_seconds()
    sync_pairs = pairs[pairs["dt_seconds"] < sync_window].copy()

    if len(sync_pairs) > 0:
        sync_pairs["dist_km"] = sync_pairs.apply(
            lambda r: haversine_km(r["latitude"], r["longitude"], r["lat_r"], r["lon_r"]),
            axis=1,
        )
        sync_agg = sync_pairs.groupby("mmsi").agg(
            max_sync_dist_km  = ("dist_km", "max"),
            mean_sync_dist_km = ("dist_km", "mean"),
            n_sync_pairs      = ("dist_km", "count"),
            sync_snr_mean     = ("snr_r",   "mean"),
        ).reset_index()
        df = df.merge(sync_agg, on="mmsi", how="left")
    else:
        df["max_sync_dist_km"]  = np.nan
        df["mean_sync_dist_km"] = np.nan
        df["n_sync_pairs"]      = 0
        df["sync_snr_mean"]     = np.nan

    df["n_sync_pairs"] = df["n_sync_pairs"].fillna(0).astype(int)

    # — Signal Quality —
    snr_high = config.get("snr_high", 30)
    snr_mid  = config.get("snr_mid",  15)

    def _quality(snr):
        if pd.isna(snr):
            return 0.5
        if snr >= snr_high:
            return 1.0
        elif snr >= snr_mid:
            return 0.7 + (snr - snr_mid) / max(snr_high - snr_mid, 1) * 0.3
        else:
            return max(0.5 + snr / max(snr_mid, 1) * 0.2, 0.3)

    df["signal_quality"] = df["snr_mean"].apply(_quality)

    # — Seuils par type —
    speed_by_type = config.get("speed_max_by_type", DEFAULT_CONFIG["speed_max_by_type"])
    rot_by_type   = config.get("rot_max_by_type",   DEFAULT_CONFIG["rot_max_by_type"])
    df["type_speed_max"] = df["type"].map(speed_by_type).fillna(config.get("default_speed_max", 20))
    df["type_rot_max"]   = df["type"].map(rot_by_type).fillna(config.get("default_rot_max", 30))

    # — Cap moyen sous-voile + écart destination —
    course_underway = (
        ais[ais["status"] == "Under Way"]
        .groupby("mmsi")["course"]
        .mean()
        .reset_index()
        .rename(columns={"course": "mean_course_underway"})
    )
    df = df.merge(course_underway, on="mmsi", how="left")

    def _dest_bearing(row):
        if pd.isna(row.get("lat_ais")) or pd.isna(row.get("destination")):
            return np.nan
        coords = PORT_COORDS.get(str(row["destination"]).strip())
        if coords is None:
            return np.nan
        return bearing_degrees(row["lat_ais"], row["lon_ais"], coords[0], coords[1])

    df["bearing_to_dest"] = df.apply(_dest_bearing, axis=1)
    df["course_deviation"] = df.apply(
        lambda r: angular_diff(r["mean_course_underway"], r["bearing_to_dest"])
        if not pd.isna(r.get("mean_course_underway")) and not pd.isna(r.get("bearing_to_dest"))
        else np.nan,
        axis=1,
    )

    return df, radio_stats

# ─── Détecteurs ──────────────────────────────────────────────────────────────

def score_ais_disabled(row):
    if pd.isna(row.get("ais_off_ratio")) or pd.isna(row.get("nb_radio")):
        return 0.0, ""
    off = row["ais_off_ratio"]
    if off == 0:
        return 0.0, ""
    obligation_factor = 1.0 if row.get("ais_obligated", False) else 0.6
    radio_factor      = 1.0 if row.get("nb_radio", 0) > 0 else 0.5
    score = min(off * obligation_factor * radio_factor, 0.99)
    desc  = f"AIS désactivé sur {off*100:.0f}% des émissions"
    if row.get("ais_obligated"):
        desc += " (obligation SOLAS)"
    return round(score, 2), desc


def score_speed_anomaly(row, config):
    speed_by_type     = config.get("speed_max_by_type", DEFAULT_CONFIG["speed_max_by_type"])
    default_speed_max = config.get("default_speed_max", 20)
    overspeed_margin  = config.get("overspeed_margin", 1.2)

    ship_type      = row.get("type", "Other")
    type_speed_max = speed_by_type.get(ship_type, default_speed_max)

    conflict = row.get("speed_conflict_ratio", 0)
    score_a, desc_a = 0.0, ""
    if not pd.isna(conflict) and conflict > 0:
        score_a = min(0.5 + conflict * 0.5, 0.99)
        desc_a  = f"Conflit vitesse/statut sur {conflict*100:.0f}% des émissions"

    speed_max = row.get("speed_max", 0)
    score_b, desc_b = 0.0, ""
    if not pd.isna(speed_max) and speed_max > type_speed_max * overspeed_margin:
        ratio  = (speed_max - type_speed_max) / type_speed_max
        score_b = min(0.6 + ratio * 0.3, 0.99)
        desc_b  = f"Vitesse max {speed_max:.1f} nd > max {type_speed_max} nd ({ship_type})"

    return (round(score_a, 2), desc_a) if score_a >= score_b else (round(score_b, 2), desc_b)


def score_course_anomaly(row, config):
    rot_by_type              = config.get("rot_max_by_type", DEFAULT_CONFIG["rot_max_by_type"])
    default_rot_max          = config.get("default_rot_max", 30)
    rot_threshold_multiplier = config.get("rot_threshold_multiplier", 1.5)

    ship_type    = row.get("type", "Other")
    type_rot_max = rot_by_type.get(ship_type, default_rot_max)

    rot = row.get("rot_max", 0)
    if pd.isna(rot):
        return 0.0, ""

    rot_threshold = type_rot_max * rot_threshold_multiplier
    if rot < rot_threshold:
        return 0.0, ""

    scale_range = max(127 - rot_threshold, 1)
    score = min(0.5 + (rot - rot_threshold) / scale_range * 0.45, 0.99)
    desc  = (f"ROT max = {rot:.1f}°/min > seuil {rot_threshold:.0f}°/min "
             f"pour {ship_type} (max normal = {type_rot_max}°/min)")
    return round(score, 2), desc


def score_position_mismatch(row, config):
    dist_min          = config.get("dist_min_km", 50)
    dist_max          = config.get("dist_max_km", 500)
    no_sync_factor    = config.get("no_sync_temp_factor", 0.6)
    quality           = row.get("signal_quality", 1.0)

    if row.get("n_sync_pairs", 0) > 0:
        dist, temp_factor, mode = row["max_sync_dist_km"], 1.0, "sync"
    elif not any(
        pd.isna(row.get(c)) for c in ["lat_ais", "lon_ais", "lat_radio", "lon_radio"]
    ):
        dist = haversine_km(row["lat_ais"], row["lon_ais"], row["lat_radio"], row["lon_radio"])
        temp_factor, mode = no_sync_factor, "fallback"
    else:
        return 0.0, ""

    if pd.isna(dist) or dist < dist_min:
        return 0.0, ""

    score = min(0.5 + (dist - dist_min) / max(dist_max - dist_min, 1) * 0.45, 0.99)
    score = min(score * temp_factor * quality, 0.99)
    if score == 0.0:
        return 0.0, ""

    suffix = ", mesures < 1h" if mode == "sync" else ", timestamps non sync — confiance réduite"
    return round(score, 2), f"Écart AIS/radio = {dist:.0f} km ({mode}{suffix}, quality={quality:.2f})"


def score_fake_flag(row, flag_profiles):
    if pd.isna(row.get("freq_mean")) or pd.isna(row.get("flag")):
        return 0.0, ""
    quality = row.get("signal_quality", 1.0)
    profile = flag_profiles[flag_profiles["flag"] == row["flag"]]
    if profile.empty or pd.isna(profile["flag_freq_std"].values[0]):
        return 0.0, ""
    mu  = profile["flag_freq_mean"].values[0]
    std = profile["flag_freq_std"].values[0]
    if std == 0:
        return 0.0, ""
    z = abs(row["freq_mean"] - mu) / std
    if z < 1.5:
        return 0.0, ""
    score = min((0.4 + (z - 1.5) / 3.0 * 0.55) * quality, 0.99)
    if score == 0.0:
        return 0.0, ""
    return round(score, 2), (
        f"Fréquence {row['freq_mean']:.2f} MHz "
        f"(profil {row['flag']}: {mu:.2f}±{std:.2f} MHz, z={z:.1f}σ, quality={quality:.2f})"
    )


def score_name_change(row):
    nb = row.get("nb_old_names", 0)
    if pd.isna(nb) or nb == 0:
        return 0.0, ""
    suspicious = row.get("is_suspicious", False)
    base  = min(0.3 + nb * 0.15, 0.75)
    score = min(base + (0.2 if suspicious else 0), 0.99)
    desc  = f"{nb} ancien(s) nom(s)"
    if suspicious:
        desc += " + marqué suspect dans le registre"
    return round(score, 2), desc


def build_spoofing_scores(radio_stats):
    spoofing = {}
    r = radio_stats.dropna(subset=["pulse_mode", "freq_mean"])
    for i in range(len(r)):
        ri         = r.iloc[i]
        candidates = r[
            (r["mmsi"] != ri["mmsi"]) &
            (r["pulse_mode"] == ri["pulse_mode"]) &
            (abs(r["freq_mean"] - ri["freq_mean"]) < 0.5)
        ]
        if not candidates.empty:
            n = len(candidates)
            spoofing[ri["mmsi"]] = (
                round(min(0.6 + n * 0.1, 0.99), 2),
                f"Signature similaire à {n} autre(s) navire(s) "
                f"(pulse={ri['pulse_mode']}, freq≈{ri['freq_mean']:.2f} MHz)",
            )
    return spoofing


def score_destination_mismatch(row, config):
    tolerance = config.get("dest_angle_tolerance", 45)
    deviation = row.get("course_deviation")
    dest      = str(row.get("destination", "")).strip()

    if pd.isna(deviation) or dest not in PORT_COORDS:
        return 0.0, ""
    if row.get("last_status") in ["Moored", "At Anchor"]:
        return 0.0, ""
    if deviation < tolerance:
        return 0.0, ""

    score = min(0.4 + (deviation - tolerance) / max(180 - tolerance, 1) * 0.59, 0.99)
    bearing = row.get("bearing_to_dest", 0)
    actual  = row.get("mean_course_underway", 0)
    return round(score, 2), (
        f"Cap observé {actual:.0f}° vs cap vers {dest} ({bearing:.0f}°) — écart {deviation:.0f}°"
    )

# ─── Enrichissement zones à risque ───────────────────────────────────────────

def _get_risk_zone(lat, lon, zones_df):
    if pd.isna(lat) or pd.isna(lon):
        return None
    best, best_niveau = None, 0
    for _, zone in zones_df.iterrows():
        if point_in_polygon(lat, lon, zone["polygon"]) and zone["niveau_num"] > best_niveau:
            best_niveau = zone["niveau_num"]
            best = zone
    return best


def enrich_with_zones(detections, zones_df, pos_by_mmsi, config):
    if zones_df is None or len(detections) == 0:
        detections["risk_zone_name"]   = None
        detections["risk_zone_type"]   = None
        detections["risk_zone_level"]  = None
        detections["confidence_final"] = detections["confidence"]
        return detections

    boost_map = config.get("boost_by_niveau", DEFAULT_CONFIG["boost_by_niveau"])
    boost_map = {int(k): v for k, v in boost_map.items()}

    rz_names, rz_types, rz_levels, conf_finals = [], [], [], []
    for _, alert in detections.iterrows():
        pos  = pos_by_mmsi.get(alert["mmsi"])
        zone = _get_risk_zone(pos[0], pos[1], zones_df) if pos else None
        if zone is not None:
            boost = boost_map.get(int(zone["niveau_num"]), 0)
            rz_names.append(zone["nom"])
            rz_types.append(zone["type"])
            rz_levels.append(zone["niveau"])
            conf_finals.append(min(alert["confidence"] + boost, 0.99))
        else:
            rz_names.append(None); rz_types.append(None)
            rz_levels.append(None); conf_finals.append(alert["confidence"])

    detections = detections.copy()
    detections["risk_zone_name"]   = rz_names
    detections["risk_zone_type"]   = rz_types
    detections["risk_zone_level"]  = rz_levels
    detections["confidence_final"] = conf_finals
    return detections

# ─── Pipeline principal ───────────────────────────────────────────────────────

FRAUD_TYPES = [
    "AIS Disabled", "Speed Anomaly", "Course Anomaly",
    "Position Mismatch", "Fake Flag", "Name Change", "Spoofing",
    "Destination Mismatch",
]


def run_detection(config, ships, ais, radio, zones):
    threshold = config.get("threshold", 0.5)

    df, radio_stats = build_features(ships, ais, radio, config)

    flag_profiles = (
        df.dropna(subset=["freq_mean", "flag"])
        .groupby("flag")
        .agg(flag_freq_mean=("freq_mean", "mean"), flag_freq_std=("freq_mean", "std"))
        .reset_index()
    )
    spoofing_scores = build_spoofing_scores(radio_stats)

    pos_by_mmsi = {}
    for _, row in df[["mmsi", "lat_ais", "lon_ais", "lat_radio", "lon_radio"]].iterrows():
        mmsi = row["mmsi"]
        if not pd.isna(row.get("lat_ais")):
            pos_by_mmsi[mmsi] = (row["lat_ais"], row["lon_ais"])
        elif not pd.isna(row.get("lat_radio")):
            pos_by_mmsi[mmsi] = (row["lat_radio"], row["lon_radio"])

    results = []
    for _, row in df.iterrows():
        mmsi = row["mmsi"]
        lat, lon = pos_by_mmsi.get(mmsi, (None, None))

        def _append(ftype, score, desc):
            if score >= threshold:
                results.append({
                    "mmsi": mmsi, "name": row["name"], "flag": row["flag"],
                    "type": row["type"], "lat": lat, "lon": lon,
                    "fraud_type": ftype, "confidence": score,
                    "signal_quality": row.get("signal_quality", 1.0),
                    "description": desc,
                })

        s, d = score_ais_disabled(row);                _append("AIS Disabled",      s, d)
        s, d = score_speed_anomaly(row, config);       _append("Speed Anomaly",     s, d)
        s, d = score_course_anomaly(row, config);      _append("Course Anomaly",    s, d)
        s, d = score_position_mismatch(row, config);   _append("Position Mismatch", s, d)
        s, d = score_fake_flag(row, flag_profiles);    _append("Fake Flag",         s, d)
        s, d = score_name_change(row);                 _append("Name Change",       s, d)
        s, d = score_destination_mismatch(row, config);_append("Destination Mismatch", s, d)

        if mmsi in spoofing_scores:
            raw_s, raw_d = spoofing_scores[mmsi]
            quality = row.get("signal_quality", 1.0)
            _append("Spoofing", min(round(raw_s * quality, 2), 0.99),
                    raw_d + f" (quality={quality:.2f})")

    detections = (
        pd.DataFrame(results)
        .sort_values("confidence", ascending=False)
        .reset_index(drop=True)
    )

    detections = enrich_with_zones(detections, zones, pos_by_mmsi, config)
    detections = detections.sort_values("confidence_final", ascending=False).reset_index(drop=True)

    stats = {
        "total_ships":    len(df),
        "total_alerts":   len(detections),
        "unique_ships":   detections["mmsi"].nunique() if len(detections) > 0 else 0,
        "in_risk_zone":   detections["risk_zone_name"].notna().sum() if len(detections) > 0 else 0,
        "high_confidence":(detections["confidence_final"] >= 0.8).sum() if len(detections) > 0 else 0,
        "by_type":        detections["fraud_type"].value_counts().to_dict() if len(detections) > 0 else {},
    }

    return {"detections": detections, "ships_df": df, "stats": stats, "pos_by_mmsi": pos_by_mmsi}
