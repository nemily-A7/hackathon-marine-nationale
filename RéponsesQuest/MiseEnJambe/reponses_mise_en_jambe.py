"""
Hackathon Albert 2026 — Sujet 3
Réponses : Mise en Jambe (Questions 1 à 12)
============================================
Données utilisées :
  - ships_small.csv
  - radio_signatures_small.csv
  - ais_data_small.csv
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ── Chargement des données ────────────────────────────────────────────────────
DATA = "../../SujetsHackathon2026/Sujet3/MiseEnJambe/"

ships  = pd.read_csv(DATA + "ships_small.csv")
radio  = pd.read_csv(DATA + "radio_signatures_small.csv")
ais    = pd.read_csv(DATA + "ais_data_small.csv")

print("=== DONNÉES CHARGÉES ===")
print(f"ships  : {ships.shape[0]} lignes × {ships.shape[1]} colonnes")
print(f"radio  : {radio.shape[0]} lignes × {radio.shape[1]} colonnes")
print(f"ais    : {ais.shape[0]} lignes × {ais.shape[1]} colonnes")


# ═══════════════════════════════════════════════════════════════════════════════
# PARTIE 1 : EXPLORATION DES DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

# ── Q1 : Structure des fichiers ───────────────────────────────────────────────
print("\n=== Q1 : Structure des fichiers ===")

champs_ships = set(ships.columns)
champs_radio = set(radio.columns)
communs = champs_ships & champs_radio

print(f"Colonnes ships ({len(ships.columns)}) : {list(ships.columns)}")
print(f"Colonnes radio ({len(radio.columns)}) : {list(radio.columns)}")
print(f"Colonnes AIS   ({len(ais.columns)})   : {list(ais.columns)}")
print(f"\nChamps communs ships ∩ radio : {sorted(communs)}")

# ── Q2 : Analyse des navires ──────────────────────────────────────────────────
print("\n=== Q2 : Analyse des navires ===")

navire_long = ships.loc[ships['length'].idxmax()]
print(f"Navire le plus long : {navire_long['name']} (MMSI {navire_long['mmsi']}, {navire_long['length']} m)")

nb_panama = (ships['flag'] == 'Panama').sum()
print(f"Navires sous pavillon Panama : {nb_panama}")

# ── Q3 : Analyse des signatures radio ────────────────────────────────────────
print("\n=== Q3 : Analyse des signatures radio ===")

freq_max = radio['frequency'].max()
navire_freq_max = radio.loc[radio['frequency'].idxmax(), 'mmsi']
print(f"Fréquence radio la plus élevée : {freq_max} MHz (MMSI {navire_freq_max})")

nb_fm = (radio['modulation'].str.upper() == 'FM').sum() if 'modulation' in radio.columns else 'N/A'
print(f"Signatures radio en modulation FM : {nb_fm}")

# ── Q4 : Analyse des données AIS ──────────────────────────────────────────────
print("\n=== Q4 : Analyse des données AIS ===")

nb_ais_off = (~ais['ais_active'].astype(bool)).sum() if 'ais_active' in ais.columns else 'N/A'
print(f"Navires AIS désactivé : {nb_ais_off}")

navire_rapide = ais.loc[ais['speed'].idxmax()]
print(f"Navire le plus rapide : MMSI {navire_rapide['mmsi']} à {navire_rapide['speed']} kt")


# ═══════════════════════════════════════════════════════════════════════════════
# PARTIE 2 : LIENS ENTRE LES FICHIERS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Q5 : Association navires → signatures radio ───────────────────────────────
print("\n=== Q5 : Association navires → signatures radio ===")

mmsi_avec_radio = set(radio['mmsi'].unique())
ships_avec_radio = ships[ships['mmsi'].isin(mmsi_avec_radio)]
print(f"Navires avec au moins une signature radio : {len(ships_avec_radio)}")

# ── Q6 : Association navires → données AIS ───────────────────────────────────
print("\n=== Q6 : Association navires → données AIS ===")

mmsi_avec_ais = set(ais['mmsi'].unique())
ships_avec_ais = ships[ships['mmsi'].isin(mmsi_avec_ais)]
print(f"Navires avec au moins une donnée AIS : {len(ships_avec_ais)}")

ships_ais_sans_radio = ships[
    ships['mmsi'].isin(mmsi_avec_ais) & ~ships['mmsi'].isin(mmsi_avec_radio)
]
print(f"Navires avec AIS mais sans signature radio : {len(ships_ais_sans_radio)}")
if len(ships_ais_sans_radio) > 0:
    print(ships_ais_sans_radio[['mmsi', 'name', 'flag']].head(10).to_string(index=False))

# ── Q7 : Anomalies de position ────────────────────────────────────────────────
print("\n=== Q7 : Anomalies de position AIS vs radio ===")

# Prendre la dernière position AIS et la première signature radio par MMSI
ais_pos   = ais[['mmsi', 'latitude', 'longitude']].drop_duplicates('mmsi')
radio_pos = radio[['mmsi', 'location_lat', 'location_lon']].drop_duplicates('mmsi') \
            if 'location_lat' in radio.columns else None

if radio_pos is not None:
    merge = ais_pos.merge(radio_pos, on='mmsi')
    merge['delta_lat'] = (merge['latitude'] - merge['location_lat']).abs()
    merge['delta_lon'] = (merge['longitude'] - merge['location_lon']).abs()
    anomalies_pos = merge[(merge['delta_lat'] > 0.001) | (merge['delta_lon'] > 0.001)]
    print(f"Navires avec écart de position > 0.001° : {len(anomalies_pos)}")
    print(anomalies_pos[['mmsi', 'delta_lat', 'delta_lon']].head(10).to_string(index=False))
else:
    print("Colonnes location_lat/location_lon absentes dans radio_signatures_small.csv")

# ── Q8 : Données manquantes ───────────────────────────────────────────────────
print("\n=== Q8 : Données manquantes et MMSI dupliqués ===")

ships_sans_tout = ships[
    ~ships['mmsi'].isin(mmsi_avec_radio) & ~ships['mmsi'].isin(mmsi_avec_ais)
]
print(f"Navires sans radio ET sans AIS : {len(ships_sans_tout)}")
if len(ships_sans_tout) > 0:
    print(ships_sans_tout[['mmsi', 'name', 'flag']].head(10).to_string(index=False))

mmsi_dup_ships = ships[ships['mmsi'].duplicated(keep=False)]
mmsi_dup_radio = radio[radio['mmsi'].duplicated(keep=False)]
mmsi_dup_ais   = ais[ais['mmsi'].duplicated(keep=False)]
print(f"\nMMSI dupliqués dans ships  : {mmsi_dup_ships['mmsi'].nunique()}")
print(f"MMSI dupliqués dans radio  : {mmsi_dup_radio['mmsi'].nunique()}")
print(f"MMSI dupliqués dans AIS    : {mmsi_dup_ais['mmsi'].nunique()}")


# ═══════════════════════════════════════════════════════════════════════════════
# PARTIE 3 : ANALYSE ET VISUALISATION
# ═══════════════════════════════════════════════════════════════════════════════

# ── Q9 : Statistiques descriptives ───────────────────────────────────────────
print("\n=== Q9 : Statistiques descriptives ===")

stats_length = ships['length'].agg(['mean', 'median', 'std'])
print(f"Longueur navires — moyenne : {stats_length['mean']:.1f} m | "
      f"médiane : {stats_length['median']:.1f} m | "
      f"écart-type : {stats_length['std']:.1f} m")

stats_freq = radio['frequency'].agg(['mean', 'std'])
print(f"Fréquence radio — moyenne : {stats_freq['mean']:.3f} MHz | "
      f"écart-type : {stats_freq['std']:.3f} MHz")

# ── Q10 : Visualisations ──────────────────────────────────────────────────────
print("\n=== Q10 : Visualisations ===")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('Hackathon Albert 2026 — Sujet 3 — Mise en Jambe', fontsize=12, fontweight='bold')

# Histogramme des vitesses AIS
axes[0].hist(ais['speed'].dropna(), bins=30, color='#1e7fcb', edgecolor='white', linewidth=0.5)
axes[0].set_title('Distribution des vitesses AIS')
axes[0].set_xlabel('Vitesse (nœuds)')
axes[0].set_ylabel('Nombre de mesures')
axes[0].grid(True, alpha=0.3)

# Navires par pavillon
flag_counts = ships['flag'].value_counts().head(15)
axes[1].barh(flag_counts.index, flag_counts.values, color='#c9a227')
axes[1].set_title('Navires par pavillon (Top 15)')
axes[1].set_xlabel('Nombre de navires')
axes[1].grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig('q10_mise_en_jambe_visualisations.png', dpi=120, bbox_inches='tight')
print("→ Graphique sauvegardé : q10_mise_en_jambe_visualisations.png")
plt.show()


# ═══════════════════════════════════════════════════════════════════════════════
# PARTIE 4 : QUESTIONS OUVERTES
# ═══════════════════════════════════════════════════════════════════════════════

print("""
=== Q11 : Hypothèses ===

Pourquoi certains navires ont-ils leur AIS désactivé ?
------------------------------------------------------
1. Activités illicites : dark shipping pour éviter la détection lors de
   transferts STS non déclarés (pétrole sanctionné, contrebande, trafic humain).
2. Contournement de sanctions : navires de la flotte fantôme russe/iranienne
   coupent leur AIS pour dissimuler leurs trajets et escales.
3. Zone de conflit : dans certaines zones (Mer Rouge, Golfe de Guinée),
   des navires coupent l'AIS pour éviter d'être ciblés par des acteurs hostiles.
4. Défaillance technique : pannes d'équipement, batterie déchargée, erreur de
   configuration (moins probable pour des coupures > 24h).
5. Zone non couverte : dépassement de la portée des récepteurs côtiers (en haute
   mer, hors couverture satellite LEO).

Comment expliquer les écarts de position AIS vs radio ?
-------------------------------------------------------
1. Décalage temporel : les positions AIS et radio ne sont pas capturées au même
   instant — le navire s'est déplacé entre les deux mesures.
2. Spoofing AIS : le navire diffuse une position GPS falsifiée tout en émettant
   depuis une position réelle détectable par triangulation radio.
3. Erreur de capteur : GPS défaillant à bord, erreur de quantification, ou
   coordonnées dans un référentiel différent (WGS84 vs local).
4. Clonage de MMSI : deux navires distincts partagent le même MMSI — l'un est
   détecté par AIS, l'autre par signature radio.


=== Q12 : Améliorations possibles ===

Champs manquants pour une identification plus fiable :
------------------------------------------------------
- IMO (numéro international unique, résistant aux changements de MMSI/nom)
- Timestamp précis pour chaque mesure (horodatage UTC synchronisé)
- RSSI (puissance du signal) pour permettre la triangulation
- Empreinte CFO (décalage fréquentiel de l'oscillateur — unique par transpondeur)
- Escales et ports fréquentés (itinéraire historique)
- Propriétaire réel (beneficial owner) vs armateur déclaré

Comment automatiser la détection des écarts AIS vs radio ?
----------------------------------------------------------
1. Interpolation temporelle : pour chaque couple (AIS, radio), interpoler la
   position AIS à l'instant exact de la mesure radio avant de comparer.
2. Seuil adaptatif : calibrer le seuil d'écart en fonction de la vitesse du
   navire et du delta temporel (tolérance = SOG × dt × facteur_sécurité).
3. Pipeline temps réel : comparer en continu les positions AIS du flux live
   avec les signatures radio récentes — déclencher une alerte si écart > 1 km.
4. Machine learning : entraîner un classificateur sur des paires (position_AIS,
   position_radio, delta_t, speed) pour distinguer les vrais écarts suspects
   des faux positifs liés à la latence.
""")

print("=== FIN DES RÉPONSES MISE EN JAMBE ===")
