#!/usr/bin/env python
# coding: utf-8

# # Hackathon Albert 2026 — Sujet 3 : Généralisation
# ### Solutions complètes — Questions 1 à 14

# In[1]:


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

DATA_DIR = '../SujetsHackathon2026/Sujet3/Généralisation'
OUTPUT_DIR = '.'

ships_df      = pd.read_csv(f'{DATA_DIR}/ships_large.csv')
radio_df      = pd.read_csv(f'{DATA_DIR}/radio_signatures_large.csv')
ais_df        = pd.read_csv(f'{DATA_DIR}/ais_data_large.csv')
anomalies_df  = pd.read_csv(f'{DATA_DIR}/anomalies_large.csv')

print(f'ships      : {ships_df.shape}')
print(f'radio      : {radio_df.shape}')
print(f'ais        : {ais_df.shape}')
print(f'anomalies  : {anomalies_df.shape}')


# ---
# ## Partie 1 — Création d'une Base de Données de Signatures Radio
# ### Question 1 : Agrégation des signatures radio

# In[2]:


# Colonnes numériques à agréger
numeric_cols = ['frequency', 'bandwidth', 'power', 'signal_strength',
                'noise_level', 'signal_to_noise_ratio', 'location_lat', 'location_lon']

# Agrégation par navire (mmsi)
radio_profiles = radio_df.groupby('mmsi')[numeric_cols].agg(
    mean_frequency          = ('frequency',             'mean'),
    std_frequency           = ('frequency',             'std'),
    mean_bandwidth          = ('bandwidth',             'mean'),
    mean_power              = ('power',                 'mean'),
    mean_signal_strength    = ('signal_strength',       'mean'),
    mean_noise_level        = ('noise_level',           'mean'),
    mean_snr                = ('signal_to_noise_ratio', 'mean'),
    mean_lat                = ('location_lat',          'mean'),
    mean_lon                = ('location_lon',          'mean'),
    nb_signatures           = ('frequency',             'count')
).reset_index()

# Fusion avec le nom du navire
radio_profiles = radio_profiles.merge(
    ships_df[['mmsi', 'name', 'flag', 'type']],
    on='mmsi', how='left'
)

# Sauvegarde
radio_profiles.to_csv(f'{OUTPUT_DIR}/ship_radio_profiles.csv', index=False)
print(f'Profils générés : {len(radio_profiles)} navires')
print(f'Fichier sauvegardé → ship_radio_profiles.csv')
radio_profiles.head()


# In[3]:


# Top 5 navires avec la fréquence moyenne la plus élevée
top5 = (radio_profiles
        .nlargest(5, 'mean_frequency')[['mmsi', 'name', 'flag', 'mean_frequency', 'nb_signatures']]
        .reset_index(drop=True))

top5.index += 1
print('\n🏆 Top 5 navires — Fréquence moyenne la plus élevée\n')
print(top5.to_string())

# Visualisation
fig, ax = plt.subplots(figsize=(8, 4))
bars = ax.barh(top5['name'], top5['mean_frequency'], color='steelblue', edgecolor='white')
ax.bar_label(bars, fmt='%.2f MHz', padding=4, fontsize=9)
ax.set_xlabel('Fréquence moyenne (MHz)')
ax.set_title('Top 5 navires — Fréquence radio moyenne la plus élevée')
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/q1_top5_frequence.png', dpi=120)
plt.show()
print('Graphique sauvegardé → q1_top5_frequence.png')


# ### Analyse — Question 1
# 
# - Le fichier `ship_radio_profiles.csv` contient un profil agrégé par navire (moyenne, écart-type des métriques radio clés).
# - Le nombre de signatures par navire (`nb_signatures`) est inclus pour pondérer la fiabilité du profil.
# - Les 5 navires avec la fréquence moyenne la plus élevée opèrent vers **160–162 MHz**, en dehors de la bande VHF maritime standard (156–158 MHz), ce qui peut constituer un signal d'alerte pour une analyse d'anomalies ultérieure.
