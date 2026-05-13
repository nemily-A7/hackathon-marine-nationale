"""
Télécharge et consolide 4 bases de données maritimes gratuites :
  1. OFAC SDN     (US Treasury)          — navires sous sanctions américaines
  2. OpenSanctions Maritime              — Paris/Tokyo/Abuja MOU + EU + Ukraine + shadow fleet
  3. UN SC 1718   (OpenSanctions)        — navires nord-coréens sous embargo ONU
  4. UK OFSI      (UK Treasury)          — navires sous sanctions britanniques

Sauvegarde dans work/sanctions_real.csv avec colonne risk_category.
"""

import requests
import pandas as pd
import re
import io
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sanctions_real.csv')

def _clean_id(series):
    return (series.fillna('').astype(str).str.strip()
            .str.replace(r'\.0$', '', regex=True)
            .replace({'nan': '', 'None': ''}))

def _fetch(label, url, **kwargs):
    print(f"  Téléchargement {label}...", end=' ', flush=True)
    r = requests.get(url, timeout=30, **kwargs)
    r.raise_for_status()
    print(f"OK ({len(r.content)//1024} KB)")
    return r

rows = []

# ── 1. OFAC SDN ─────────────────────────────────────────────────────────────
print("━" * 62)
print("  1/4 — OFAC SDN (US Treasury)")
print("━" * 62)
try:
    r = _fetch("OFAC SDN", 'https://www.treasury.gov/ofac/downloads/sdn.csv')
    sdn = pd.read_csv(
        io.StringIO(r.text), header=None,
        names=['ent_num','name','type','program','title','call_sign',
               'vess_type','tonnage','grt','vess_flag','vess_owner','remarks'],
        on_bad_lines='skip'
    )
    vessels = sdn[sdn['type'].str.strip().str.lower() == 'vessel'].copy()
    vessels['remarks'] = vessels['remarks'].fillna('')
    vessels['imo']  = vessels['remarks'].str.extract(r'IMO\s+([0-9]{7})', flags=re.IGNORECASE)[0]
    vessels['mmsi'] = vessels['remarks'].str.extract(r'MMSI\s+([0-9]{9})', flags=re.IGNORECASE)[0]

    for _, v in vessels.iterrows():
        rows.append({
            'name':          str(v['name']).strip(),
            'flag':          str(v['vess_flag']).strip() if pd.notna(v['vess_flag']) else '',
            'program':       str(v['program']).strip(),
            'imo':           str(v['imo']).strip() if pd.notna(v['imo']) else '',
            'mmsi':          str(v['mmsi']).strip() if pd.notna(v['mmsi']) else '',
            'source':        'OFAC SDN',
            'risk_category': 'sanction',
        })
    print(f"  ✅ {len(vessels)} navires  ({vessels['imo'].notna().sum()} IMO, {vessels['mmsi'].notna().sum()} MMSI)")
    top = vessels['program'].value_counts().head(5)
    for prog, cnt in top.items():
        print(f"     {prog:<30} {cnt}")
except Exception as e:
    print(f"  ⚠️  OFAC SDN indisponible : {e}")

# ── 2. OpenSanctions Maritime ────────────────────────────────────────────────
print()
print("━" * 62)
print("  2/4 — OpenSanctions Maritime (Paris/Tokyo/Abuja MOU + EU + Ukraine + shadow fleet)")
print("━" * 62)

RISK_MAP = {
    'sanction':     'sanction',
    'mare.shadow':  'shadow_fleet',
    'mare.detained':'psc_detained',
    'reg.warn':     'reg_warning',
    'poi':          'poi',
}

SOURCE_LABELS = {
    'paris_mou_banned':       'Paris MOU (navires bannis Europe)',
    'tokyo_mou_detention':    'Tokyo MOU (rétentions Asie-Pacifique)',
    'abuja_mou_detention':    'Abuja MOU (rétentions Afrique ouest)',
    'black_sea_mou_detention':'Black Sea MOU (rétentions Mer Noire)',
    'ua_war_sanctions':       'Sanctions guerre Ukraine',
    'eu_sanctions_map':       'EU Sanctions Map',
    'eu_journal_sanctions':   'Journal officiel UE',
    'us_ofac_sdn':            'OFAC SDN',
    'kp_rusi_reports':        'Rapport RUSI Corée du Nord',
    'gb_fcdo_sanctions':      'UK FCDO Sanctions',
    'ca_dfatd_sema_sanctions':'Sanctions Canada',
    'ch_seco_sanctions':      'Sanctions Suisse',
    'fr_tresor_gels_avoir':   'Gels avoirs France',
}

try:
    r = _fetch("OpenSanctions Maritime",
               'https://data.opensanctions.org/datasets/20260511/maritime/maritime.csv')
    df_os = pd.read_csv(io.StringIO(r.text), on_bad_lines='skip')
    df_os['imo_clean']  = df_os['imo'].str.replace('IMO', '', regex=False).str.strip()
    df_os['mmsi_clean'] = df_os['mmsi'].fillna('').astype(str).str.strip().replace('nan','')

    for _, v in df_os.iterrows():
        risk_raw = str(v.get('risk', '') or '').split(';')
        risk_cat = 'flagged'
        for r_key, r_val in RISK_MAP.items():
            if r_key in risk_raw:
                risk_cat = r_val
                break

        ds = str(v.get('datasets', '') or '')
        src_label = SOURCE_LABELS.get(ds.split(';')[0].strip(), f'OpenSanctions ({ds[:40]})')

        rows.append({
            'name':          str(v.get('caption', '') or '').strip().upper(),
            'flag':          str(v.get('flag', '') or '').strip(),
            'program':       src_label,
            'imo':           str(v['imo_clean']) if pd.notna(v.get('imo')) else '',
            'mmsi':          str(v['mmsi_clean']),
            'source':        'OpenSanctions',
            'risk_category': risk_cat,
        })

    n_imo  = df_os['imo_clean'].notna().sum()
    n_mmsi = (df_os['mmsi_clean'] != '').sum()
    print(f"  ✅ {len(df_os)} navires  ({n_imo} IMO, {n_mmsi} MMSI)")
    top_ds = df_os['datasets'].value_counts().head(6)
    for ds, cnt in top_ds.items():
        label = SOURCE_LABELS.get(ds, ds)
        print(f"     {label:<45} {cnt}")
except Exception as e:
    print(f"  ⚠️  OpenSanctions indisponible : {e}")

# ── 3. UN Security Council 1718 (Corée du Nord) ──────────────────────────────
print()
print("━" * 62)
print("  3/4 — UN Security Council 1718 (navires nord-coréens)")
print("━" * 62)
try:
    r = _fetch("UN 1718",
               'https://data.opensanctions.org/datasets/20260505/un_1718_vessels/targets.simple.csv')
    df_un = pd.read_csv(io.StringIO(r.text), on_bad_lines='skip')

    for _, v in df_un.iterrows():
        ident = str(v.get('identifiers', '') or '')
        imo_match = re.search(r'IMO(\d{7})', ident)
        imo = imo_match.group(1) if imo_match else ''
        rows.append({
            'name':          str(v.get('name', '') or '').strip().upper(),
            'flag':          'KP',
            'program':       'UN SC Résolution 1718 (DPRK)',
            'imo':           imo,
            'mmsi':          '',
            'source':        'UN SC 1718',
            'risk_category': 'sanction',
        })
    print(f"  ✅ {len(df_un)} navires nord-coréens")
except Exception as e:
    print(f"  ⚠️  UN 1718 indisponible : {e}")

# ── 4. UK OFSI ───────────────────────────────────────────────────────────────
print()
print("━" * 62)
print("  4/4 — UK OFSI (Office of Financial Sanctions Implementation)")
print("━" * 62)
try:
    r = _fetch("UK OFSI",
               'https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.csv')
    lines = r.text.splitlines()
    content = '\n'.join(lines[1:])  # sauter la ligne 'Last Updated'
    df_uk = pd.read_csv(io.StringIO(content), on_bad_lines='skip', low_memory=False)
    ships_uk = df_uk[df_uk['Group Type'].str.lower().str.contains('ship', na=False)].copy()

    for _, v in ships_uk.iterrows():
        name = str(v.get('Name 6', '') or v.get('Name 1', '') or '').strip()
        rows.append({
            'name':          name.upper(),
            'flag':          '',
            'program':       'UK OFSI Financial Sanctions',
            'imo':           '',
            'mmsi':          '',
            'source':        'UK OFSI',
            'risk_category': 'sanction',
        })
    print(f"  ✅ {len(ships_uk)} navires sous sanctions UK")
except Exception as e:
    print(f"  ⚠️  UK OFSI indisponible : {e}")

# ── Consolidation ────────────────────────────────────────────────────────────
print()
print("━" * 62)
print("  Consolidation finale...")
print("━" * 62)

all_df = pd.DataFrame(rows)
all_df['imo']  = _clean_id(all_df['imo'])
all_df['mmsi'] = _clean_id(all_df['mmsi'])
all_df['name'] = all_df['name'].str.strip()

# Supprimer les doublons (même IMO → garder la source la plus sévère)
SEVERITY = {'sanction': 0, 'shadow_fleet': 1, 'psc_detained': 2,
            'poi': 3, 'reg_warning': 4, 'flagged': 5}
all_df['_sev'] = all_df['risk_category'].map(SEVERITY).fillna(9)
all_df = (all_df.sort_values('_sev')
                .drop_duplicates(subset=['imo'], keep='first')
                .drop(columns=['_sev'])
                .reset_index(drop=True))

n_imo  = (all_df['imo']  != '').sum()
n_mmsi = (all_df['mmsi'] != '').sum()
print(f"  Total navires uniques : {len(all_df)}")
print(f"  Avec IMO  : {n_imo}")
print(f"  Avec MMSI : {n_mmsi}")
print()
print("  Par catégorie de risque :")
for cat, cnt in all_df['risk_category'].value_counts().items():
    print(f"     {cat:<15} {cnt}")
print()
print("  Par source :")
for src, cnt in all_df['source'].value_counts().items():
    print(f"     {src:<20} {cnt}")

all_df.to_csv(OUT, index=False)
print(f"\n  💾 Sauvegardé → {OUT}")
print("━" * 62)
