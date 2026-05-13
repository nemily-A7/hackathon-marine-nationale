"""
Pipeline d'identification passive — flux AIS temps réel (aisstream.io)
======================================================================
⚠️  Les données radio (fréquence, bandwidth, power) ne sont PAS transmises
    par AIS. Elles sont ici SIMULÉES à partir du type et de la vitesse du
    navire pour démontrer le pipeline. Le cross-référencement MMSI, lui,
    est 100% réel.
"""

import asyncio
import websockets
import json
import random
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import euclidean_distances
from datetime import datetime, timezone
import os

# ── Chemins ────────────────────────────────────────────────────────────────
BASE   = os.path.dirname(os.path.abspath(__file__))
DATA   = os.path.join(BASE, '..', 'SujetsHackathon2026', 'Sujet3', 'Généralisation')

API_KEY = "caae13ac0e37a4c0b6721666f74396b938c5b670"
WS_URL  = "wss://stream.aisstream.io/v0/stream"

# ── Chargement des références ───────────────────────────────────────────────
print("Chargement des profils de référence...")
profiles   = pd.read_csv(os.path.join(BASE, 'ship_radio_profiles.csv'))
ships_df   = pd.read_csv(os.path.join(DATA, 'ships_large.csv'))
anomalies  = pd.read_csv(os.path.join(DATA, 'anomalies_large.csv'))

profiles   = profiles.merge(ships_df[['mmsi', 'is_suspicious']], on='mmsi', how='left')
suspect_mmsi = set(ships_df[ships_df['is_suspicious'] == True]['mmsi'].tolist())
anomaly_mmsi = set(anomalies['mmsi'].tolist())

FEATURES       = ['mean_frequency', 'mean_bandwidth', 'mean_power', 'mean_snr']
profile_matrix = profiles[FEATURES].fillna(profiles[FEATURES].mean())
scaler         = StandardScaler()
profile_scaled = scaler.fit_transform(profile_matrix)

print(f"✅ {len(profiles)} profils chargés | {len(suspect_mmsi)} MMSI suspects connus\n")

# ── Simulation de signature radio ───────────────────────────────────────────
FREQ_BY_TYPE = {
    'Cargo': 157.0, 'Tanker': 156.8, 'Passenger': 156.5,
    'Fishing': 157.5, 'Tug': 157.2, 'Pleasure': 157.0,
}

def simulate_radio_sig(ship_type: str, speed_knots: float) -> dict:
    """
    Génère une signature radio vraisemblable basée sur le type et la vitesse.
    [SIMULATION — pas une vraie mesure radio]
    """
    base_freq = FREQ_BY_TYPE.get(ship_type, 158.0)
    return {
        'frequency'            : round(base_freq + random.gauss(0, 1.5), 2),
        'bandwidth'            : round(max(10, 25 + speed_knots * 0.3 + random.gauss(0, 5)), 2),
        'power'                : round(max(10, 150 + speed_knots * 8 + random.gauss(0, 30)), 2),
        'signal_to_noise_ratio': round(max(1, 20 + random.gauss(0, 8)), 2),
    }

# ── Pipeline d'identification ───────────────────────────────────────────────
def identify(sig: dict, top_k: int = 3):
    vec   = scaler.transform([[sig['frequency'], sig['bandwidth'],
                                sig['power'], sig['signal_to_noise_ratio']]])
    dists = euclidean_distances(vec, profile_scaled)[0]
    idx   = dists.argsort()[:top_k]
    cands = profiles.iloc[idx][['mmsi', 'name', 'flag', 'is_suspicious']].copy()
    cands['distance']  = dists[idx].round(3)
    cands['confiance'] = (1 / (1 + cands['distance'])).round(3)
    return cands.reset_index(drop=True)

# ── Affichage ───────────────────────────────────────────────────────────────
def print_alert(real_mmsi, ship_name, ship_type, lat, lon, speed,
                sig, candidates, alerts):
    ts  = datetime.now(timezone.utc).strftime('%H:%M:%S')
    sep = '─' * 62
    best = candidates.iloc[0]
    print(f"\n{sep}")
    print(f"  🛳  {ship_name or 'Inconnu':<25} MMSI {real_mmsi}  [{ts}]")
    print(f"  Type : {ship_type:<18} Pos : {lat:.2f}°, {lon:.2f}°  Vitesse : {speed:.1f} kt")
    print(sep)
    # Cross-référence MMSI (100% réel)
    if real_mmsi in suspect_mmsi:
        print(f"  ⚠️  [RÉEL] MMSI dans notre base de suspects !")
    if real_mmsi in anomaly_mmsi:
        print(f"  ⚠️  [RÉEL] MMSI dans notre base d'anomalies !")
    print(f"  📻 [SIMULÉ] Signature radio générée :")
    print(f"     {sig['frequency']} MHz | BW {sig['bandwidth']} kHz | "
          f"{sig['power']:.0f} W | SNR {sig['signal_to_noise_ratio']} dB")
    print(sep)
    print(f"  Match pipeline → {best['name']} ({best['flag']}) "
          f"conf={best['confiance']:.0%}")
    for _, row in candidates.iloc[1:].iterrows():
        print(f"     → {row['name']} ({row['flag']}) conf={row['confiance']:.0%}")
    print(sep)
    if alerts:
        print("  🚨 ALERTES :")
        for a in alerts:
            print(f"     ⚠  {a}")
    else:
        print("  ✅ Aucune alerte")
    print(sep)

# ── Boucle principale WebSocket ─────────────────────────────────────────────
async def run():
    subscription = {
        "APIKey": API_KEY,
        "BoundingBoxes": [[[-90, -180], [90, 180]]],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
    }

    ship_cache = {}   # mmsi → nom + type (enrichi par ShipStaticData)
    processed  = 0
    MAX_SHIPS  = 20   # on affiche 20 navires puis on s'arrête

    print(f"Connexion à {WS_URL}...")
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(subscription))
        print("✅ Connecté — en attente de navires en temps réel...\n")

        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get('MessageType', '')

            # Enrichir le cache avec les noms/types
            if msg_type == 'ShipStaticData':
                meta = msg.get('Message', {}).get('ShipStaticData', {})
                mmsi = meta.get('UserID') or meta.get('MMSI')
                if mmsi:
                    ship_cache[mmsi] = {
                        'name': meta.get('Name', '').strip(),
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

            info      = ship_cache.get(mmsi, {})
            ship_name = info.get('name', '')
            ship_type = info.get('type', 'Unknown')

            # Simulation signature radio
            sig        = simulate_radio_sig(ship_type, speed)
            candidates = identify(sig)

            # Construction des alertes
            alerts = []
            if mmsi in suspect_mmsi:
                alerts.append("MMSI dans la base de suspects [source : dataset hackathon]")
            if mmsi in anomaly_mmsi:
                alerts.append("MMSI dans la base d'anomalies [source : dataset hackathon]")
            if not (156.0 <= sig['frequency'] <= 158.0):
                alerts.append(f"Fréquence simulée hors bande VHF ({sig['frequency']} MHz)")
            if bool(candidates.iloc[0]['is_suspicious']):
                alerts.append("Meilleur match est un navire suspect (profil synthétique)")

            print_alert(mmsi, ship_name, ship_type, lat, lon, speed,
                        sig, candidates, alerts)

            processed += 1
            if processed >= MAX_SHIPS:
                print(f"\n{'═'*62}")
                print(f"  {MAX_SHIPS} navires traités — pipeline terminé.")
                print(f"{'═'*62}")
                break

# ── Entrée ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    asyncio.run(run())
