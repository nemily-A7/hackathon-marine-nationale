import { useMemo, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts'
import { scoreBadgeClass, NIVEAU_COLOR, NIVEAU_BADGE, NIVEAU_EMOJI, NIVEAU_ORDER, fmt } from '../utils'
import { FRAUD_TYPES_ORDER } from '../mockData'

const TIP = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="custom-tooltip">
      <div className="label">{label}</div>
      {payload.map((p, i) => <div key={i} className="val">{p.value} alertes</div>)}
    </div>
  )
}

export default function Zones({ detections, shipMap, zones = [] }) {
  const [levelFilter, setLevelFilter] = useState('Tous')
  const [typeFilter,  setTypeFilter]  = useState('')

  const inZone = useMemo(
    () => detections.filter(d => d.risk_zone_name),
    [detections]
  )

  const stats = useMemo(() => ({
    total:   inZone.length,
    ships:   new Set(inZone.map(d => d.mmsi)).size,
    zones:   new Set(inZone.map(d => d.risk_zone_name)).size,
    extreme: inZone.filter(d => d.risk_zone_level === 'EXTREME').length,
  }), [inZone])

  const levels = useMemo(() =>
    [...new Set(inZone.map(d => d.risk_zone_level))].sort((a, b) => (NIVEAU_ORDER[b] ?? 0) - (NIVEAU_ORDER[a] ?? 0)),
    [inZone]
  )
  const fraudTypes = useMemo(() =>
    [...new Set(inZone.map(d => d.fraud_type))].sort(),
    [inZone]
  )

  const filtered = useMemo(() => {
    let rows = inZone
    if (levelFilter !== 'Tous') rows = rows.filter(d => d.risk_zone_level === levelFilter)
    if (typeFilter)              rows = rows.filter(d => d.fraud_type     === typeFilter)
    return rows.sort((a, b) => b.confidence_final - a.confidence_final)
  }, [inZone, levelFilter, typeFilter])

  const byZone = useMemo(() => {
    const acc = {}
    filtered.forEach(d => {
      const k = d.risk_zone_name
      if (!acc[k]) acc[k] = { zone: k, level: d.risk_zone_level, count: 0, score_max: 0 }
      acc[k].count++
      acc[k].score_max = Math.max(acc[k].score_max, d.confidence_final)
    })
    return Object.values(acc).sort((a, b) => b.score_max - a.score_max)
  }, [filtered])

  // Zones with no alerts
  const silentZones = useMemo(() => {
    const active = new Set(inZone.map(d => d.risk_zone_name))
    return zones.filter(z => !active.has(z.name))
  }, [inZone, zones])

  if (inZone.length === 0) {
    return <div className="empty">Aucune alerte dans une zone à risque avec les seuils actuels.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* KPIs */}
      <div className="metric-row">
        <div className="metric">
          <div className="metric-val">{stats.total}</div>
          <div className="metric-lbl">Alertes en zone</div>
        </div>
        <div className="metric">
          <div className="metric-val">{stats.ships}</div>
          <div className="metric-lbl">Navires uniques</div>
        </div>
        <div className="metric">
          <div className="metric-val">{stats.zones}</div>
          <div className="metric-lbl">Zones concernées</div>
        </div>
        <div className="metric">
          <div className="metric-val" style={{ color: 'var(--red)' }}>{stats.extreme}</div>
          <div className="metric-lbl">🔴 Extrême</div>
        </div>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <label>
          Niveau de risque :
          <select style={{ marginLeft: 8 }} value={levelFilter} onChange={e => setLevelFilter(e.target.value)}>
            <option value="Tous">Tous</option>
            {levels.map(l => <option key={l} value={l}>{NIVEAU_EMOJI[l]} {l}</option>)}
          </select>
        </label>
        <label>
          Type de fraude :
          <select style={{ marginLeft: 8 }} value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="">Tous</option>
            {fraudTypes.map(ft => <option key={ft} value={ft}>{ft}</option>)}
          </select>
        </label>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
          {filtered.length} alerte{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Score</th>
                <th>Navire</th>
                <th>Type</th>
                <th>Pavillon</th>
                <th>Vitesse max</th>
                <th>ROT max</th>
                <th>Type de fraude</th>
                <th>Zone</th>
                <th>Niveau</th>
                <th style={{ maxWidth: 280 }}>Détail</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d, i) => {
                const s = shipMap[d.mmsi]
                return (
                  <tr key={i}>
                    <td><span className={scoreBadgeClass(d.confidence_final)}>{d.confidence_final.toFixed(2)}</span></td>
                    <td style={{ fontWeight: 600 }}>{d.name}</td>
                    <td className="muted">{d.type}</td>
                    <td className="muted">{d.flag}</td>
                    <td className="mono">{fmt(s?.speed_max)} nd</td>
                    <td className="mono">{fmt(s?.rot_max)}°/min</td>
                    <td className="muted" style={{ fontSize: 12 }}>{d.fraud_type}</td>
                    <td style={{ fontWeight: 600 }}>{d.risk_zone_name}</td>
                    <td>
                      <span className={`badge ${NIVEAU_BADGE[d.risk_zone_level] ?? 'badge-blue'}`}>
                        {NIVEAU_EMOJI[d.risk_zone_level]} {d.risk_zone_level}
                      </span>
                    </td>
                    <td className="muted" style={{ maxWidth: 280, whiteSpace: 'normal', fontSize: 11 }}>
                      {d.description}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bar chart */}
      <div className="card">
        <div className="card-title">Alertes par zone à risque</div>
        <ResponsiveContainer width="100%" height={Math.max(180, byZone.length * 40)}>
          <BarChart data={byZone} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
            <XAxis type="number" tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="zone" width={200} tick={{ fill:'#dce8f8', fontSize:11 }} axisLine={false} tickLine={false} />
            <Tooltip content={<TIP />} cursor={{ fill:'rgba(255,255,255,.04)' }} />
            <Bar dataKey="count" name="Alertes" radius={[0,4,4,0]}>
              {byZone.map(z => <Cell key={z.zone} fill={NIVEAU_COLOR[z.level] ?? '#7a97be'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Silent zones */}
      {silentZones.length > 0 && (
        <div className="card">
          <div className="card-title">Zones sans alerte active</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {silentZones.map(z => (
              <span key={z.id} className={`badge ${NIVEAU_BADGE[z.level] ?? 'badge-blue'}`}>
                {NIVEAU_EMOJI[z.level]} {z.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
