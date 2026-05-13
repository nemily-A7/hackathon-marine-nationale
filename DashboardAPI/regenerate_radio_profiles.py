"""
Régénère ship_radio_profiles.csv avec des paramètres radio physiques réels.
Référence : ITU-R M.1371-5 — AIS technical characteristics
Modèle    : récepteur satellite AIS (LEO ~900 km, type exactEarth / Spire)
"""

import pandas as pd
import math
import random
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CSV  = os.path.join(BASE, 'ship_radio_profiles.csv')

# ── Constantes ITU-R M.1371-5 ────────────────────────────────────────────────
AIS_CH87B   = 161.975   # MHz — voie primaire AIS
AIS_CH88B   = 162.025   # MHz — voie secondaire AIS
AIS_BW_KHZ  = 25.0      # kHz — GMSK BT=0.4
AIS_PWR_A   = 12.5      # W   — Class A (navires commerciaux)
AIS_PWR_B   = 2.0       # W   — Class B (plaisance/pêche/remorqueurs)

# ── Modèle satellite LEO (type exactEarth / Spire) ───────────────────────────
SAT_ALT_KM  = 900.0     # km — altitude nominale orbite
SAT_GAIN    = 20.0      # dBi — gain antenne satellite (parabole)
RX_NF_DB    = 4.0       # dB  — facteur de bruit récepteur satellite

CLASS_B_KW  = {'fishing', 'pleasure', 'tug', 'sail', 'pleasure craft', 'fishing vessel'}

def noise_floor_dbm():
    return -174.0 + 10 * math.log10(AIS_BW_KHZ * 1e3) + RX_NF_DB   # ≈ -126 dBm

def fspl_db(dist_km, freq_mhz):
    return 20 * math.log10(max(dist_km, 0.1)) + 20 * math.log10(freq_mhz) + 32.45

def get_cfo_hz(mmsi: int) -> float:
    """CFO déterministe par émetteur — imprécision TCXO (±2 ppm → ±324 Hz sur 162 MHz)."""
    rng = random.Random(int(mmsi) ^ 0xA15ACA1)
    return rng.gauss(0, 108)   # 1 ppm std

def get_bw_jitter(mmsi: int) -> float:
    rng = random.Random(int(mmsi) ^ 0xB007)
    return rng.gauss(0, 0.3)   # kHz

df = pd.read_csv(CSV)
noise = noise_floor_dbm()

print(f"Mise à jour de {len(df)} profils radio (modèle ITU-R M.1371-5)...")

for i, row in df.iterrows():
    mmsi      = int(row['mmsi'])
    ship_type = str(row.get('type', 'Cargo')).lower()

    # Canal AIS : pair → Ch87B, impair → Ch88B
    ch_num  = 87 if mmsi % 2 == 0 else 88
    ch_freq = AIS_CH87B if ch_num == 87 else AIS_CH88B

    # CFO unique par émetteur
    cfo_hz   = get_cfo_hz(mmsi)
    freq_mhz = ch_freq + cfo_hz / 1e6

    # Classe AIS → puissance d'émission
    pwr_w  = AIS_PWR_B if any(k in ship_type for k in CLASS_B_KW) else AIS_PWR_A
    pt_dbm = 10 * math.log10(pwr_w * 1000)

    # Portée oblique satellite — variation déterministe par position
    lat = float(row.get('mean_lat', 0))
    lon = float(row.get('mean_lon', 0))
    pos_rng  = random.Random(int(abs(lat * 100)) ^ int(abs(lon * 100)) ^ mmsi)
    slant_km = SAT_ALT_KM * pos_rng.uniform(0.85, 1.15)

    # RSSI (Friis) + gains antennes
    fspl  = fspl_db(slant_km, ch_freq)
    rssi  = pt_dbm - fspl + 2.15 + SAT_GAIN   # 2.15 dBi navire, 20 dBi satellite

    # SNR
    snr = rssi - noise

    # Gigue de bande passante
    bw = AIS_BW_KHZ + get_bw_jitter(mmsi)

    df.at[i, 'mean_frequency']      = round(freq_mhz, 6)
    df.at[i, 'std_frequency']       = round(abs(cfo_hz) / 1e6, 8)
    df.at[i, 'mean_bandwidth']      = round(bw, 2)
    df.at[i, 'mean_power']          = round(pwr_w, 3)
    df.at[i, 'mean_signal_strength'] = round(rssi, 1)
    df.at[i, 'mean_noise_level']    = round(noise, 1)
    df.at[i, 'mean_snr']            = round(max(0.0, snr), 1)
    df.at[i, 'mean_cfo_hz']         = round(cfo_hz, 1)

df.to_csv(CSV, index=False)

print(f"  ✅ {len(df)} profils mis à jour")
print(f"  Fréquences : {df['mean_frequency'].min():.4f} – {df['mean_frequency'].max():.4f} MHz")
print(f"  CFO        : {df['mean_cfo_hz'].min():.0f} – {df['mean_cfo_hz'].max():.0f} Hz")
print(f"  SNR        : {df['mean_snr'].min():.1f} – {df['mean_snr'].max():.1f} dB")
print(f"  Puissance  : {sorted(df['mean_power'].unique())} W")
print(f"  Bruit      : {noise:.1f} dBm (plancher thermique 25 kHz + NF {RX_NF_DB} dB)")
