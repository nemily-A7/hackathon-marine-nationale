# Synthèse — Détection de fraude maritime V2

## Contexte

Objectif : identifier les navires au comportement frauduleux en croisant trois sources de données passives et déclaratives, sans dépendre de la coopération du navire.

Les fraudes ciblées correspondent aux techniques documentées de manipulation AIS : désactivation, usurpation d'identité, falsification de position ou de destination, et capture de signaux radio anormaux.

---

## Architecture du pipeline

```
ships_large.csv          ais_data_large.csv          radio_signatures_large.csv
      │                        │                               │
      └──────────────── Feature Engineering ──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    Sync temporelle    Signal quality    Seuils par type
    AIS ↔ Radio         (SNR → [0.3,1])   (speed, ROT)
    (< 1h)                                        │
              └────────────────┼────────────────┘
                               │
                    8 fonctions de score
                    (0.0 → 0.99 par type)
                               │
                    Seuil THRESHOLD = 0.5
                               │
              ┌────────────────┴────────────────┐
              │                                 │
     Enrichissement zones à risque     Vérification destination
     zones_risques_2.csv               PORT_COORDS (bearing)
     (boost score +0.02 à +0.15)       (course_deviation)
              │                                 │
              └────────────────┬────────────────┘
                               │
                  alertes_fraude_v2.csv
         (mmsi, fraud_type, confidence, confidence_final,
          risk_zone_name, risk_zone_level, description)
```

---

## Données utilisées

| Fichier | Lignes | Colonnes clés |
|---|---|---|
| `ships_large.csv` | 1 000 navires | mmsi, type, flag, gross_tonnage, year_built, historical_names, is_suspicious, destination |
| `ais_data_large.csv` | 10 000 émissions | mmsi, timestamp, latitude, longitude, speed, course, status, ais_active, heading, rot |
| `radio_signatures_large.csv` | 5 000 captures | mmsi, timestamp, frequency, signal_to_noise_ratio, pulse_pattern, location_lat/lon |
| `zones_risques_2.csv` | 35 zones | nom, niveau (EXTREME/ELEVE/MODERE/SURVEILLE), type, coords (polygone lat/lon) |

---

## Feature Engineering

Avant de lancer les détecteurs, les données brutes (une ligne par émission ou capture) sont **agrégées par navire** (MMSI). Chaque navire est représenté par une seule ligne avec ses caractéristiques synthétisées.

### Features AIS

| Feature | Calcul | Utilisée par |
|---|---|---|
| `ais_off_ratio` | % d'émissions avec `ais_active = False` | AIS Disabled |
| `speed_max` | Vitesse maximale observée | Speed Anomaly |
| `speed_conflict_ratio` | % d'émissions où vitesse ≠ statut déclaré | Speed Anomaly |
| `rot_max` | Valeur absolue maximale du ROT | Course Anomaly |
| `lat_ais`, `lon_ais` | Dernière position AIS connue | Position Mismatch (fallback) |
| `last_status` | Dernier statut déclaré | Destination Mismatch |
| `mean_course_underway` | Cap moyen quand `status = Under Way` | Destination Mismatch |

### Features radio

| Feature | Calcul | Utilisée par |
|---|---|---|
| `snr_mean` | Moyenne du Signal-to-Noise Ratio | `signal_quality_factor` |
| `freq_mean` | Fréquence radio moyenne | Fake Flag |
| `pulse_mode` | Pattern d'impulsion dominant | Spoofing |
| `lat_radio`, `lon_radio` | Dernière position captée | Position Mismatch (fallback) |

### Features navire (enrichissement)

| Feature | Calcul | Utilisée par |
|---|---|---|
| `nb_old_names` | Nombre de noms historiques dans `historical_names` | Name Change |
| `ais_obligated` | True si Passenger Ship OU gross_tonnage ≥ 300 OU year_built > 2002 | AIS Disabled |
| `type_speed_max` | Vitesse max physique pour ce type (table `SPEED_MAX_BY_TYPE`) | Speed Anomaly |
| `type_rot_max` | ROT max normal pour ce type (table `ROT_MAX_BY_TYPE`) | Course Anomaly |
| `bearing_to_dest` | Relèvement géographique vers le port déclaré | Destination Mismatch |
| `course_deviation` | Écart angulaire `mean_course_underway` vs `bearing_to_dest` | Destination Mismatch |

### Synchronisation temporelle AIS ↔ Radio

Pour le détecteur Position Mismatch, on ne compare les positions AIS et radio que si leurs **timestamps sont à moins d'une heure d'écart**. Sans synchronisation, un navire peut légitimement se trouver à 300 km de sa dernière position radio si plusieurs heures se sont écoulées.

```
paires_sync ← {(a, r) | a ∈ ais_navire, r ∈ radio_navire,
                         |a.timestamp - r.timestamp| < 3 600 s}

max_sync_dist_km ← max(haversine(a, r) pour chaque paire sync)
n_sync_pairs     ← nombre de paires synchronisées
```

Si `n_sync_pairs == 0`, le détecteur bascule en mode **fallback** avec `temporal_factor = 0.6` appliqué au score (les mesures non synchronisées sont moins fiables).

---

## Signal quality factor

Chaque mesure radio est accompagnée d'un SNR (Signal-to-Noise Ratio). Un signal capté avec un SNR faible peut induire des erreurs sur la fréquence, la position ou le pulse_pattern décodé. On calcule un `signal_quality_factor` ∈ [0.3, 1.0] appliqué comme multiplicateur sur tous les scores qui dépendent de mesures radio.

```
SI snr_mean ≥ 30 dB  →  quality = 1.0
SI 15 ≤ snr < 30     →  quality = 0.7 + (snr - 15) / 15 × 0.3
SI snr < 15          →  quality = max(0.5 + snr / 15 × 0.2, 0.3)
```

Détecteurs affectés : Position Mismatch, Fake Flag, Spoofing.
Détecteurs non affectés (AIS only) : AIS Disabled, Speed Anomaly, Course Anomaly, Name Change.

---

## Les 8 détecteurs de fraude

Chaque détecteur prend en entrée le profil d'un navire et retourne un **score ∈ [0.0, 0.99]**. Le score n'atteint jamais 1.0 car aucune règle automatique ne peut avoir une certitude absolue. Une alerte est déclenchée si `score ≥ 0.5`.

La formule de progression utilisée par la plupart des détecteurs est :

```
score = score_min + (valeur - seuil_min) / (seuil_max - seuil_min) × (score_max - score_min)
score = min(score, 0.99)
```

---

### Détecteur 1 — AIS Disabled

**Signal** : `ais_off_ratio` — proportion des émissions AIS où `ais_active = False`.

Un navire soumis à l'obligation SOLAS qui coupe son AIS veut éviter d'être localisé. Le signal est renforcé si des signaux radio continuent d'être captés (le navire est présent mais se cache).

```
SI ais_off_ratio == 0 ALORS score = 0.0

obligation_factor ← 1.0  si navire obligé par SOLAS   sinon 0.6
radio_factor      ← 1.0  si captures radio disponibles  sinon 0.5

score = min(ais_off_ratio × obligation_factor × radio_factor, 0.99)
```

| ais_off_ratio | ais_obligated | nb_radio | Score |
|---|---|---|---|
| 80% | Oui | > 0 | **0.80** |
| 80% | Non | > 0 | 0.80 × 0.6 = **0.48** → sous le seuil |
| 100% | Oui | > 0 | plafonné à **0.99** |

---

### Détecteur 2 — Speed Anomaly

**Deux sous-signaux combinés** :

**A — Conflit statut/vitesse** (V1) : vitesse physiquement incompatible avec le statut déclaré.
- `status ∈ {Moored, At Anchor}` avec `speed > 3 nœuds`
- `status = Under Way` avec `speed < 0.5 nœuds`

```
score_A = 0.5 + speed_conflict_ratio × 0.5
```

**B — Dépassement vitesse max physique** (V2) : vitesse observée impossible pour ce type de navire.

```
type_speed_max ← SPEED_MAX_BY_TYPE[ship_type]
seuil          = type_speed_max × 1.2

SI speed_max > seuil :
    overspeed_ratio = (speed_max - type_speed_max) / type_speed_max
    score_B = 0.6 + overspeed_ratio × 0.3
```

**Score final = max(score_A, score_B)**

| Type | Vitesse max (nd) | Exemple |
|---|---|---|
| Container Ship | 25 | Au-delà : physiquement impossible |
| Tanker | 16 | VLCC ne peut pas dépasser 16 nd |
| Bulk Carrier | 15 | |
| Passenger Ship | 30 | Ferry rapide |
| Fishing Vessel | 14 | |
| Tugboat | 14 | |

---

### Détecteur 3 — Course Anomaly

**Signal** : `rot_max` — valeur absolue maximale du ROT (Rate of Turn, en °/min).

Un virement brutal trahit une manœuvre évasive ou des données AIS falsifiées. Le seuil est calibré par type de navire : un remorqueur vire normalement à 60°/min, un pétrolier de 300 000 t ne peut pas dépasser 10°/min.

```
type_rot_max  ← ROT_MAX_BY_TYPE[ship_type]
rot_threshold = type_rot_max × 1.5   ← 50% de marge

SI rot_max < rot_threshold : score = 0.0

scale_range = 127 - rot_threshold   (127 = limite physique AIS, ITU-R M.1371)
score = 0.5 + (rot_max - rot_threshold) / scale_range × 0.45
```

| Type | ROT max normal | Seuil d'alerte (×1.5) |
|---|---|---|
| Container Ship | 20°/min | 30°/min |
| Tanker | 10°/min | 15°/min |
| Fishing Vessel | 40°/min | 60°/min |
| Tugboat | 60°/min | 90°/min |

---

### Détecteur 4 — Position Mismatch

**Signal** : distance entre la position AIS et la position captée par radio pour le même navire au même moment.

Si l'AIS déclare Marseille mais que le signal radio est capté à 500 km au large, l'AIS est falsifié.

**Mode A — paires synchronisées** (`n_sync_pairs > 0`) : les mesures ont été prises à moins d'1 heure d'écart → comparaison fiable.

**Mode B — fallback** : pas de paires sync disponibles → on compare les dernières mesures connues avec `temporal_factor = 0.6`.

```
dist = haversine(lat_ais, lon_ais, lat_radio, lon_radio)   [km]

SI dist < 50 km : score = 0.0   ← tolérance pour décalages temporels normaux

score = 0.5 + (dist - 50) / (500 - 50) × 0.45
score = score × temporal_factor × signal_quality
```

| dist | Mode A (sync) | Mode B (fallback, quality=1) |
|---|---|---|
| 50 km | 0.50 | 0.50 × 0.6 = **0.30** |
| 300 km | 0.72 | 0.72 × 0.6 = **0.43** → sous le seuil |
| 600 km | 0.99 | 0.99 × 0.6 = **0.59** |

La formule de Haversine utilisée pour le calcul de distance :

```
a    = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
dist = 2 × 6371 × arcsin(√a)
```

---

### Détecteur 5 — Fake Flag

**Signal** : z-score de la fréquence radio du navire par rapport au profil moyen de son pavillon déclaré.

Les navires d'un même pavillon utilisent des équipements radio similaires (réglementations communes). Une fréquence très atypique suggère que le pavillon est faux.

```
mu  = moyenne(freq_mean) des navires du même pavillon
std = écart-type(freq_mean) des navires du même pavillon

z = |freq_mean - mu| / std

SI z < 1.5 : score = 0.0

score = 0.4 + (z - 1.5) / 3.0 × 0.55
score = score × signal_quality   ← fréquence moins fiable si SNR bas
```

| z-score | Interprétation | Score |
|---|---|---|
| < 1.5 σ | Dans la norme | 0.0 |
| 1.5 σ | Légèrement atypique | 0.40 |
| 3.0 σ | Très atypique | 0.68 |
| 4.5 σ | Extrêmement atypique | 0.95 |

---

### Détecteur 6 — Name Change

**Signal** : `nb_old_names` (nombre de noms historiques) + `is_suspicious` (flag registre).

Un navire légitime change rarement de nom. Les navires impliqués dans des activités illicites changent fréquemment de nom pour échapper aux listes de sanctions et aux bases de surveillance.

```
SI nb_old_names == 0 : score = 0.0

base  = min(0.3 + nb_old_names × 0.15, 0.75)
bonus = 0.20  si is_suspicious == True

score = min(base + bonus, 0.99)
```

| nb_old_names | is_suspicious | Score |
|---|---|---|
| 1 | Non | **0.45** |
| 2 | Non | **0.60** |
| 3 | Non | **0.75** (plafonné) |
| 3 | Oui | 0.75 + 0.20 = **0.95** |

---

### Détecteur 7 — Spoofing

**Signal** : nombre de navires distincts partageant le même `pulse_pattern` ET une fréquence à ±0.5 MHz.

Le pulse_pattern est l'empreinte électromagnétique de l'émetteur. Deux navires légitimes ne devraient pas partager la même empreinte à la même fréquence — si c'est le cas, l'un usurpe l'identité de l'autre.

Le calcul est fait en **précalcul O(n²)** une seule fois avant la boucle principale, pour ne pas le répéter 1 000 fois.

```
POUR chaque navire A :
    candidats = navires B tels que :
        B.mmsi       ≠  A.mmsi
        B.pulse_mode == A.pulse_mode
        |B.freq_mean - A.freq_mean| < 0.5 MHz

    n = |candidats|
    SI n > 0 :
        score_brut = min(0.6 + n × 0.1, 0.99)

LORS DE L'APPLICATION :
    score_final = score_brut × signal_quality
```

| n sosies | Score brut | signal_quality = 0.5 |
|---|---|---|
| 1 | 0.70 | 0.35 → sous le seuil |
| 3 | 0.90 | 0.45 → sous le seuil |
| 5 | 0.99 | 0.50 → juste au seuil |

---

### Détecteur 8 — Destination Mismatch

**Signal** : écart entre le cap réel du navire (observé dans l'AIS quand il est "Under Way") et le relèvement théorique vers son port de destination déclaré.

Un navire qui navigue à l'opposé de sa destination déclarée ment sur sa destination — technique courante pour traverser des zones sous surveillance en déclarant un port légitime.

```
ÉTAPE 1 — Relèvement théorique (bearing)

dlon = lon_dest - lon_navire   (en radians)
x    = sin(dlon) × cos(lat_dest)
y    = cos(lat_navire) × sin(lat_dest) - sin(lat_navire) × cos(lat_dest) × cos(dlon)
bearing_to_dest = arctan2(x, y)   normalisé [0, 360°)

ÉTAPE 2 — Écart angulaire

course_deviation = min(|mean_course_underway - bearing_to_dest| mod 360,
                       360 - |mean_course_underway - bearing_to_dest| mod 360)

ÉTAPE 3 — Score

SI last_status ∈ {Moored, At Anchor} : score = 0.0
SI course_deviation < 45° : score = 0.0

score = 0.4 + (course_deviation - 45) / (180 - 45) × 0.59
```

| Écart cap | Interprétation | Score |
|---|---|---|
| < 45° | Route cohérente (tolérance météo/détroits) | **0.0** |
| 45° | Début de déviation suspecte | **0.40** |
| 90° | Cap perpendiculaire à la destination | **0.60** |
| 135° | Navire qui s'éloigne | **0.80** |
| 180° | Navire qui navigue exactement à l'opposé | **0.99** |

Ports de référence utilisés :

| Destination | Coordonnées |
|---|---|
| Rotterdam | 51.93°N, 4.48°E |
| Hambourg | 53.55°N, 10.00°E |
| Marseille | 43.30°N, 5.35°E |
| New York | 40.67°N, 74.00°W |
| Los Angeles | 33.73°N, 118.27°W |
| Shanghai | 31.23°N, 121.47°E |
| Tokyo | 35.65°N, 139.75°E |
| Singapour | 1.28°N, 103.83°E |
| Dubaï | 25.27°N, 55.33°E |
| Suez | 30.00°N, 32.55°E |

---

## Enrichissement contextuel — Zones à risque

Après application des 8 détecteurs, chaque alerte est croisée avec les 35 zones à risque géographiques définies dans `zones_risques_2.csv`. Si la position du navire se trouve à l'intérieur d'une zone, le score est **boosté** et trois colonnes sont ajoutées au tableau des alertes.

### Algorithme : point-dans-polygone (ray casting)

```
POUR chaque arête (A, B) du polygone :
    SI (A.lon ≤ lon_navire < B.lon) OU (B.lon ≤ lon_navire < A.lon) :
        lat_intersect = A.lat + (lon - A.lon) / (B.lon - A.lon) × (B.lat - A.lat)
        SI lat_navire < lat_intersect :
            inside = NOT inside

Résultat : inside impair → point à l'intérieur
```

On retient la zone avec le **niveau le plus élevé** si le navire est dans plusieurs zones simultanément.

### Boost par niveau

| Niveau | Exemples | Boost |
|---|---|---|
| EXTREME | Golfe de Guinée, Mer Rouge/Houthis, Détroit d'Ormuz | +0.15 |
| ELEVE | Corne de l'Afrique, Détroit de Malacca, Mer Noire | +0.10 |
| MODERE | Trafic drogue Caraïbes, Mer de Chine | +0.05 |
| SURVEILLE | Zones de surveillance Atlantique, Pacifique | +0.02 |

```
confidence_final = min(confidence + boost, 0.99)
```

La colonne `confidence_final` est celle utilisée pour le tri final et l'export.

---

## Format de sortie

Le fichier `alertes_fraude_v2.csv` contient une ligne par alerte (un navire peut avoir plusieurs lignes, une par type de fraude détecté) :

| Colonne | Description |
|---|---|
| `mmsi` | Identifiant unique du navire |
| `name` | Nom du navire |
| `flag` | Pavillon déclaré |
| `type` | Type de navire |
| `fraud_type` | Type de fraude détecté (parmi les 8) |
| `confidence` | Score brut du détecteur [0.5, 0.99] |
| `confidence_final` | Score après boost zone à risque |
| `signal_quality` | Coefficient de fiabilité radio [0.3, 1.0] |
| `risk_zone_name` | Nom de la zone à risque (ou vide) |
| `risk_zone_type` | Type de risque de la zone |
| `risk_zone_level` | Niveau de risque (EXTREME / ELEVE / MODERE / SURVEILLE) |
| `description` | Explication textuelle de l'alerte |

---

## Résultats sur le dataset de test (1 000 navires)

| Type de fraude | Alertes | Confiance moyenne |
|---|---|---|
| Speed Anomaly | 999 | 0.83 |
| Course Anomaly | 998 | 0.89 |
| Spoofing | 988 | 0.88 |
| Position Mismatch | 695 | 0.56 |
| Name Change | 627 | 0.75 |
| AIS Disabled | 551 | 0.62 |
| Destination Mismatch | 261 | 0.76 |
| Fake Flag | 23 | 0.59 |
| **TOTAL** | **~5 100** | — |

Navires dans une zone à risque : **31 / 1 000** (ZEE Polynésie, Canal du Mozambique, Golfe de Guinée…)

> **Note sur le dataset synthétique** : les scores élevés sur Speed Anomaly, Course Anomaly et Spoofing reflètent des données générées aléatoirement (vitesses, ROT et pulse_patterns non réalistes). Sur des données AIS réelles, la majorité de ces alertes disparaîtrait, rendant les vrais signaux bien plus visibles.

---

## Limites et pistes V3

| Limite | Amélioration possible |
|---|---|
| Fake Flag sur 1 seule dimension | Profil multi-dimensionnel : freq + puissance + modulation (distance de Mahalanobis) |
| Spoofing : match exact sur pulse_mode | Clustering DBSCAN sur vecteur complet (freq, power, SNR, modulation) |
| Pas de score composite | Score global = max(scores) + bonus logarithmique multi-signaux |
| Seuils manuels non optimisés | Optimisation supervisée sur données annotées |
| Destination : ports fixes uniquement | Base de données dynamique de ports (AIS port database) |
| Pas de dimension temporelle | Détecter l'évolution du comportement semaine par semaine |
| sync_pairs rares sur données synthétiques | En données réelles, AIS émet toutes les 2–10 s → centaines de paires sync par navire |
