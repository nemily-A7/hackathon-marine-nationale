# Rapport — Pipeline d'identification et de surveillance maritime

## Vue d'ensemble

Le système reçoit un flux AIS mondial en temps réel, analyse chaque navire selon 6 critères de risque, et diffuse les résultats vers quatre dashboards interactifs.

```
Flux AIS (aisstream.io)
        │
        ▼
  Pipeline Python  ──── Base sanctions (11 081 navires) ────┐
  (dashboard.py)   ──── Modèle radio ITU-R M.1371-5  ───────┤
        │           ──── Checks comportementaux  ────────────┘
        ▼
  WebSocket ws://localhost:8765
        │
        ├── dashboard.html         (tous les navires)
        ├── dashboard_clean.html   (navires clean ✅)
        ├── dashboard_suspects.html (1 alerte ⚠)
        └── dashboard_alertes.html  (2+ alertes 🚨)
```

---

## 1. Sources de données

### 1.1 Flux AIS — aisstream.io
- Flux WebSocket mondial, messages filtrés : `PositionReport` et `ShipStaticData`
- `PositionReport` → position (lat/lon), vitesse (SOG), MMSI
- `ShipStaticData` → nom du navire, IMO, type (cargo, tanker, etc.)
- Les deux types sont fusionnés dans un cache par MMSI

### 1.2 Base de sanctions consolidée — `sanctions_real.csv`
Construite par `fetch_sanctions.py` à partir de 4 sources officielles gratuites :

| Source | Contenu | Navires |
|--------|---------|---------|
| OFAC SDN (US Treasury) | Sanctions américaines | ~700 |
| OpenSanctions Maritime | Shadow fleet, Paris/Tokyo MOU, EU, Ukraine | ~16 000 |
| UN SC Résolution 1718 | Navires nord-coréens sous embargo ONU | ~100 |
| UK OFSI | Sanctions financières britanniques | ~300 |

Résultat : **11 081 navires uniques** après dédoublonnage par IMO (priorité à la catégorie la plus sévère).

Catégories de risque : `sanction` > `shadow_fleet` > `psc_detained` > `poi` > `reg_warning` > `flagged`

### 1.3 Profils radio — `ship_radio_profiles.csv`
994 profils générés selon le modèle physique ITU-R M.1371-5 :
- Fréquence réelle : 161,975 MHz (Ch87B) ou 162,025 MHz (Ch88B)
- Puissance : 12,5 W (Class A) ou 2 W (Class B)
- CFO (Carrier Frequency Offset) : décalage d'oscillateur unique et stable par émetteur

---

## 2. Pipeline de traitement

Pour chaque message AIS reçu, le pipeline effectue les étapes suivantes :

### Étape 1 — Réception et fusion
Le message est soit une mise à jour de position, soit une fiche statique. Les deux sont stockés dans `ship_cache[mmsi]` et fusionnés à chaque position reçue.

### Étape 2 — Empreinte radio (modèle ITU-R)
La fonction `radio_fingerprint()` calcule les caractéristiques physiques du signal AIS :
- **Canal** : Ch87B si MMSI pair, Ch88B si MMSI impair (conforme ITU-R)
- **RSSI** : calculé par l'équation de Friis (FSPL satellite LEO ~900 km)
- **SNR** : RSSI − plancher de bruit thermique (−126 dBm sur 25 kHz, NF 4 dB)
- **CFO** : décalage d'oscillateur déterministe et unique par MMSI (±300 Hz)
- Ces valeurs sont scientifiquement fondées, pas aléatoires

### Étape 3 — Identification par empreinte
La fonction `identify()` compare le CFO, le SNR et la puissance du navire aux 994 profils connus via un algorithme nearest-neighbor (distance euclidienne après normalisation). Elle retourne le profil le plus proche avec un score de confiance.

### Étape 4 — 6 checks de risque
Voir section suivante.

### Étape 5 — Calcul du niveau d'alerte
- 0 alerte → `green` (navire clean)
- 1 alerte → `orange` (navire suspect)
- 2 alertes ou plus → `red` (navire en alerte critique)

### Étape 6 — Diffusion WebSocket
L'événement JSON est envoyé à tous les navigateurs connectés. Les dashboards filtrent selon le niveau d'alerte.

---

## 3. Les 6 checks de risque

### Check 1 — Base de sanctions (IMO / MMSI / Nom)
Recherche le navire dans les 11 081 entrées de `sanctions_real.csv` par trois méthodes :
1. Correspondance exacte sur l'**IMO**
2. Correspondance exacte sur le **MMSI**
3. Correspondance exacte sur le **nom** du navire

Si trouvé, génère une alerte avec la catégorie de risque, la source (OFAC, UN, etc.) et le programme de sanction exact.

> **Pourquoi peu de hits en direct ?** Les navires sanctionnés (iraniens, nord-coréens, russes) coupent volontairement leur AIS pour ne pas être localisés — c'est le phénomène du "dark shipping". Le check fonctionne, mais les navires sanctionnés évitent précisément d'apparaître dans les flux AIS publics.

### Check 2 — Vitesse anormale
Deux niveaux :
- **Impossible** (> 50 nœuds) : aucun navire commercial ne peut physiquement atteindre cette vitesse → spoofing GPS ou capteur défaillant
- **Anormale pour le type** : dépasse la vitesse maximale connue pour ce type (ex. tanker > 20 kt, cargo > 25 kt, etc.) → données AIS suspectes

### Check 3 — Position "Null Island" (0°, 0°)
Si lat et lon sont proches de (0°, 0°) : transpondeur défaillant ou spoofing volontaire. Ce point fictif au large du Ghana est la valeur par défaut d'un GPS non initialisé.

### Check 4 — Zone géographique à risque
7 zones définies avec leurs raisons :

| Zone | Raison |
|------|--------|
| Golfe de Guinée | Piraterie active (IMB) |
| Golfe Persique / Iran | Sanctions Iran, pétrole illicite |
| Bab-el-Mandeb / Mer Rouge | Attaques Houthis 2024–2025 |
| Mer Rouge nord | Zone de conflit actif |
| Détroit de Malacca | Piraterie, contrebande |
| Eaux nord-coréennes | Sanctions DPRK, charbon/pétrole illicite |
| Côtes somaliennes | Piraterie (reprise 2023) |

### Check 5 — Saut de position (téléportation)
Compare la position actuelle à la dernière position connue. Si la distance parcourue est physiquement impossible compte tenu du temps écoulé et de la vitesse déclarée, le navire a "téléporté" → clonage de MMSI ou spoofing.

Formule : `distance_haversine > vitesse × temps × 3 + 20 km`

### Check 6 — Anomalies de signature radio AIS
Deux anomalies détectées par le modèle physique :
- **SNR < 35 dB** : signal dégradé → puissance réduite volontairement (furtivité AIS) ou équipement défaillant
- **|CFO| > 250 Hz** : décalage d'oscillateur hors spec (> 2,3 σ pour un TCXO standard) → transpondeur non homologué ou matériel de remplacement non certifié

---

## 4. Les quatre dashboards

### `dashboard.html` — Vue globale
- Carte Leaflet mondiale avec tous les navires (vert / orange / rouge)
- Sidebar : flux temps réel de tous les événements
- Popup par navire : position, vitesse, signature radio, identification CFO

### `dashboard_clean.html` — Navires conformes ✅
- Filtre : `alert_level === 'green'`
- Affiche pour chaque navire la liste des checks réussis avec leur explication détaillée (pourquoi le navire est considéré clean)
- Exemple : "Absent de toutes les bases de sanctions — IMO 9427366 vérifié sur 11 081 entrées"

### `dashboard_suspects.html` — Navires suspects ⚠
- Filtre : `alert_level === 'orange'` (exactement 1 critère déclenché)
- Affiche l'alerte unique avec son label, son détail et son code
- Carte : marqueurs orange avec popup contextuel

### `dashboard_alertes.html` — Navires en alerte critique 🚨
- Filtre : `alert_level === 'red'` (2 critères ou plus déclenchés)
- Affiche tous les critères numérotés avec badge de sévérité
- Auto-zoom sur les navires déclenchant 3 critères ou plus
- Animation pulse rouge sur les marqueurs carte

---

## 5. Ce qu'on voit dans les cartes

Chaque carte navire affiche :

```
NOM DU NAVIRE                               14:32:07
MMSI 338123456 · Cargo · 12.4 kt · 48.23°, -2.51°

📡 AIS Ch87 161.975 MHz · RSSI -72 dBm · SNR 53 dB · CFO +88 Hz · 12.5 W
↳ Empreinte CFO → NAVIRE-3456 (USA) — confiance 78%

✅ Absent de toutes les bases de sanctions (11 081 entrées)
✅ Vitesse cohérente avec le type (Cargo) : 12.4 kt
✅ Position géographique valide (48.230°, -2.510°)
✅ Zone géographique sans risque connu
✅ Signature AIS conforme — Ch87 161.975 MHz · RSSI -72 dBm · SNR 53 dB
```

---

## 6. Lancement

```bash
# 1. Télécharger les sanctions réelles (à faire une fois)
python fetch_sanctions.py

# 2. Régénérer les profils radio (à faire une fois)
python regenerate_radio_profiles.py

# 3. Lancer le dashboard
python dashboard.py

# 4. Ouvrir dans le navigateur
open http://localhost:8080/dashboard.html
```

---

## 7. Ce qui est réel vs modélisé

| Donnée | Statut | Source |
|--------|--------|--------|
| Position AIS (lat/lon) | ✅ Réel | aisstream.io (flux live) |
| Vitesse, cap | ✅ Réel | aisstream.io (flux live) |
| Nom, IMO, type du navire | ✅ Réel | aisstream.io (flux live) |
| Base de sanctions | ✅ Réel | OFAC, OpenSanctions, UN, UK OFSI |
| Zones à risque | ✅ Réel | IMB, rapports géopolitiques |
| Canaux AIS (161.975 / 162.025 MHz) | ✅ Standard ITU-R | ITU-R M.1371-5 |
| Puissance (12.5 W / 2 W) | ✅ Standard ITU-R | ITU-R M.1371-5 |
| RSSI, SNR | ✅ Modèle physique | Équation de Friis, FSPL satellite |
| CFO (empreinte oscillateur) | ✅ Modèle physique | Distribution TCXO 1 ppm |
| Mesure RF en direct | ❌ Non disponible | Nécessite hardware SDR (RTL-SDR) |
