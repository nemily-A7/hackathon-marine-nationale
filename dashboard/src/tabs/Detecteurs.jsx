import { useState, useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer, ReferenceLine } from 'recharts'
import { FRAUD_TYPES_ORDER } from '../mockData'
import { scoreColor, scoreBadgeClass, NIVEAU_BADGE, NIVEAU_EMOJI, fmt, exportCSV } from '../utils'

const FRAUD_ICONS = {
  "AIS Disabled":"🔕","Speed Anomaly":"⚡","Course Anomaly":"🧭",
  "Position Mismatch":"📍","Fake Flag":"🏁","Name Change":"📝",
  "Spoofing":"📡","Destination Mismatch":"🗺️",
}

const EXTRA_COLS = {
  "AIS Disabled":         ['last_status','speed_max','gross_tonnage','length'],
  "Speed Anomaly":        ['speed_max','length','gross_tonnage'],
  "Course Anomaly":       ['rot_max','length','gross_tonnage'],
  "Position Mismatch":    ['snr_mean'],
  "Fake Flag":            ['snr_mean','flag'],
  "Name Change":          ['year_built','gross_tonnage'],
  "Spoofing":             ['snr_mean'],
  "Destination Mismatch": ['destination','course_deviation'],
}

function DetTable({ rows, extraCols, shipMap }) {
  return (
    <div className="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>Score</th>
            <th>Navire</th>
            <th>Type</th>
            <th>Pavillon</th>
            {extraCols.includes('speed_max')      && <th>Vitesse max (nd)</th>}
            {extraCols.includes('rot_max')         && <th>ROT max (°/min)</th>}
            {extraCols.includes('snr_mean')        && <th>SNR moyen (dB)</th>}
            {extraCols.includes('course_deviation')&& <th>Écart cap (°)</th>}
            {extraCols.includes('length')          && <th>Longueur (m)</th>}
            {extraCols.includes('destination')     && <th>Destination</th>}
            {extraCols.includes('year_built')      && <th>Année</th>}
            <th>Zone</th>
            <th style={{ maxWidth: 320 }}>Détail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d, i) => {
            const s = shipMap[d.mmsi]
            return (
              <tr key={i}>
                <td><span className={scoreBadgeClass(d.confidence_final)}>{d.confidence_final.toFixed(2)}</span></td>
                <td style={{ fontWeight: 600 }}>{d.name}</td>
                <td className="muted">{d.type}</td>
                <td className="muted">{d.flag}</td>
                {extraCols.includes('speed_max')       && <td className="mono">{fmt(s?.speed_max)}</td>}
                {extraCols.includes('rot_max')          && <td className="mono">{fmt(s?.rot_max)}</td>}
                {extraCols.includes('snr_mean')         && <td className="mono">{fmt(s?.snr_mean)}</td>}
                {extraCols.includes('course_deviation') && <td className="mono">{fmt(s?.course_deviation)}</td>}
                {extraCols.includes('length')           && <td className="mono">{s?.length ?? '—'}</td>}
                {extraCols.includes('destination')      && <td className="muted">{s?.destination ?? '—'}</td>}
                {extraCols.includes('year_built')       && <td className="mono">{s?.year_built ?? '—'}</td>}
                <td>
                  {d.risk_zone_name
                    ? <span className={`badge ${NIVEAU_BADGE[d.risk_zone_level] ?? 'badge-blue'}`}>
                        {NIVEAU_EMOJI[d.risk_zone_level]} {d.risk_zone_name}
                      </span>
                    : <span className="muted">—</span>
                  }
                </td>
                <td className="muted" style={{ maxWidth: 300, whiteSpace: 'normal', fontSize: 11 }}>
                  {d.description}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

const TIP = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="custom-tooltip">
      <div className="label">{payload[0]?.payload?.bin}</div>
      <div className="val">{payload[0]?.value} alertes</div>
    </div>
  )
}

export default function Detecteurs({ detections, ships, shipMap }) {
  const [activeType, setActiveType] = useState(FRAUD_TYPES_ORDER[0])

  const countByType = useMemo(() => {
    const m = {}
    detections.forEach(d => { m[d.fraud_type] = (m[d.fraud_type] ?? 0) + 1 })
    return m
  }, [detections])

  const subset = useMemo(
    () => detections.filter(d => d.fraud_type === activeType)
         .sort((a, b) => b.confidence_final - a.confidence_final),
    [detections, activeType]
  )

  const stats = useMemo(() => ({
    count:   subset.length,
    mean:    subset.length ? (subset.reduce((s, d) => s + d.confidence_final, 0) / subset.length) : 0,
    max:     subset.length ? Math.max(...subset.map(d => d.confidence_final)) : 0,
    inZone:  subset.filter(d => d.risk_zone_name).length,
  }), [subset])

  const histogram = useMemo(() => {
    const bins = {}
    for (let b = 0.45; b < 1.0; b = Math.round((b + 0.05) * 100) / 100) {
      bins[b.toFixed(2)] = 0
    }
    subset.forEach(d => {
      const k = (Math.floor(d.confidence_final / 0.05) * 0.05).toFixed(2)
      if (bins[k] !== undefined) bins[k]++
    })
    return Object.entries(bins).map(([bin, cnt]) => ({
      bin: `${(Number(bin) * 100).toFixed(0)}%`,
      cnt,
      color: Number(bin) >= 0.8 ? '#e8254a' : Number(bin) >= 0.65 ? '#f97316' : '#eab308',
    }))
  }, [subset])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Detector pill tabs */}
      <div className="det-tabs">
        {FRAUD_TYPES_ORDER.map(ft => (
          <button
            key={ft}
            className={`det-tab ${activeType === ft ? 'active' : ''}`}
            onClick={() => setActiveType(ft)}
          >
            {FRAUD_ICONS[ft]} {ft}
            <span className="cnt">{countByType[ft] ?? 0}</span>
          </button>
        ))}
      </div>

      {/* Metrics */}
      <div className="metric-row">
        <div className="metric">
          <div className="metric-val">{stats.count}</div>
          <div className="metric-lbl">Alertes</div>
        </div>
        <div className="metric">
          <div className="metric-val" style={{ color: stats.count ? scoreColor(stats.mean) : 'var(--text-dim)' }}>
            {stats.count ? stats.mean.toFixed(2) : '—'}
          </div>
          <div className="metric-lbl">Score moyen</div>
        </div>
        <div className="metric">
          <div className="metric-val" style={{ color: stats.count ? scoreColor(stats.max) : 'var(--text-dim)' }}>
            {stats.count ? stats.max.toFixed(2) : '—'}
          </div>
          <div className="metric-lbl">Score max</div>
        </div>
        <div className="metric">
          <div className="metric-val">{stats.inZone}</div>
          <div className="metric-lbl">En zone à risque</div>
        </div>
      </div>

      {subset.length === 0 ? (
        <div className="empty">Aucune alerte pour « {activeType} » avec les seuils actuels.</div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
            <button className="export-btn" onClick={() => exportCSV(
              subset.map(d => {
                const s = shipMap[d.mmsi]
                return {
                  mmsi: d.mmsi,
                  navire: d.name,
                  type: d.type,
                  pavillon: d.flag,
                  type_fraude: d.fraud_type,
                  score_brut: d.confidence?.toFixed(2) ?? '',
                  score_final: d.confidence_final.toFixed(2),
                  vitesse_max_nd: fmt(s?.speed_max),
                  rot_max_deg_min: fmt(s?.rot_max),
                  snr_moyen_db: fmt(s?.snr_mean),
                  ecart_cap_deg: fmt(s?.course_deviation),
                  longueur_m: s?.length ?? '',
                  destination: s?.destination ?? '',
                  zone_risque: d.risk_zone_name ?? '',
                  niveau_zone: d.risk_zone_level ?? '',
                  description: d.description ?? '',
                }
              }),
              `detecteur_${activeType.toLowerCase().replace(/ /g, '_')}.csv`
            )}>
              ⬇ Exporter CSV
            </button>
          </div>
          <div className="card" style={{ padding: 0, overflow: 'visible' }}>
            <DetTable rows={subset} extraCols={EXTRA_COLS[activeType] ?? []} shipMap={shipMap} />
          </div>

          <div className="card">
            <div className="card-title">Distribution des scores — {activeType}</div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={histogram} margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
                <XAxis dataKey="bin" tick={{ fill:'#7a97be', fontSize:10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<TIP />} cursor={{ fill:'rgba(255,255,255,.04)' }} />
                <ReferenceLine x="80%" stroke="#e8254a" strokeDasharray="3 3" />
                <Bar dataKey="cnt" radius={[4,4,0,0]}>
                  {histogram.map(e => <Cell key={e.bin} fill={e.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}
