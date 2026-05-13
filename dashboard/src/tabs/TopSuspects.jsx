import { useMemo, useState } from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, Cell
} from 'recharts'
import { scoreColor, scoreBadgeClass, NIVEAU_EMOJI, NIVEAU_ORDER, fmt, exportCSV } from '../utils'

const MEDALS = ['🥇', '🥈', '🥉']
const MEDAL_CLASS = ['gold', 'silver', 'bronze']

const TIP = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="custom-tooltip">
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{d?.name}</div>
      <div className="label">{d?.type} — {d?.flag}</div>
      <div className="val" style={{ color: scoreColor(d?.score_max) }}>
        Score max : {d?.score_max?.toFixed(2)}
      </div>
      <div className="val">{d?.nb_types} types de fraude</div>
    </div>
  )
}

export default function TopSuspects({ detections, ships, shipMap }) {
  const [minTypes, setMinTypes] = useState(1)
  const [minScore, setMinScore] = useState(0.5)

  const aggregated = useMemo(() => {
    const acc = {}
    detections.forEach(d => {
      if (!acc[d.mmsi]) {
        const s = shipMap[d.mmsi]
        acc[d.mmsi] = {
          mmsi: d.mmsi, name: d.name, type: d.type, flag: d.flag,
          fraud_types: new Set(), score_max: 0, score_sum: 0, count: 0,
          in_zone: false, zone_max_level: 0, zone_max_name: null,
          length: s?.length, destination: s?.destination,
          speed_max: s?.speed_max, rot_max: s?.rot_max,
        }
      }
      const a = acc[d.mmsi]
      a.fraud_types.add(d.fraud_type)
      a.score_max = Math.max(a.score_max, d.confidence_final)
      a.score_sum += d.confidence_final
      a.count++
      if (d.risk_zone_name) {
        a.in_zone = true
        const lvl = NIVEAU_ORDER[d.risk_zone_level] ?? 0
        if (lvl > a.zone_max_level) {
          a.zone_max_level = lvl
          a.zone_max_name  = d.risk_zone_name
          a.zone_max_lvl_str = d.risk_zone_level
        }
      }
    })
    return Object.values(acc).map(a => ({
      ...a,
      nb_types: a.fraud_types.size,
      score_mean: a.score_sum / a.count,
      types_list: [...a.fraud_types].sort().join(' · '),
    })).sort((a, b) => {
      if (b.nb_types !== a.nb_types) return b.nb_types - a.nb_types
      return b.score_max - a.score_max
    })
  }, [detections, shipMap])

  const filtered = useMemo(
    () => aggregated.filter(a => a.nb_types >= minTypes && a.score_max >= minScore),
    [aggregated, minTypes, minScore]
  )

  const top3 = filtered.slice(0, 3)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Podium */}
      {top3.length > 0 && (
        <div className="podium">
          {top3.map((r, i) => (
            <div key={r.mmsi} className={`podium-card ${MEDAL_CLASS[i]}`}>
              <div className="podium-rank">{MEDALS[i]}</div>
              <div className="podium-name">{r.name}</div>
              <div className="podium-meta">
                {r.type} — {r.flag}<br />
                {r.nb_types} types de fraude<br />
                {r.length ? `${r.length} m` : ''} {r.destination ? `→ ${r.destination}` : ''}<br />
                <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{r.types_list}</span>
                {r.in_zone && (
                  <div style={{ marginTop: 4 }}>
                    {NIVEAU_EMOJI[r.zone_max_lvl_str]} {r.zone_max_name}
                  </div>
                )}
              </div>
              <div className="podium-score" style={{ color: scoreColor(r.score_max) }}>
                {r.score_max.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="filter-bar">
        <label>
          Minimum de types de fraude :
          <select style={{ marginLeft: 8 }} value={minTypes} onChange={e => setMinTypes(Number(e.target.value))}>
            {[1,2,3,4,5,6,7,8].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          Score max ≥ :
          <select style={{ marginLeft: 8 }} value={minScore} onChange={e => setMinScore(Number(e.target.value))}>
            {[0.5, 0.6, 0.65, 0.7, 0.8, 0.9].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
          {filtered.length} navire{filtered.length !== 1 ? 's' : ''} affiché{filtered.length !== 1 ? 's' : ''}
        </span>
        <button className="export-btn" onClick={() => exportCSV(
          filtered.map(r => ({
            rang: r.rang ?? '',
            mmsi: r.mmsi,
            navire: r.name,
            type: r.type,
            pavillon: r.flag,
            longueur_m: r.length ?? '',
            types_cumules: r.nb_types,
            score_max: r.score_max.toFixed(2),
            score_moyen: r.score_mean.toFixed(2),
            vitesse_max_nd: fmt(r.speed_max),
            rot_max_deg_min: fmt(r.rot_max),
            destination: r.destination ?? '',
            zone_risque: r.zone_max_name ?? '',
            niveau_zone: r.zone_max_lvl_str ?? '',
            detecteurs: r.types_list,
          })),
          'top_suspects.csv'
        )}>
          ⬇ Exporter CSV
        </button>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="empty">Aucun navire avec ces critères.</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Score max</th>
                  <th>Navire</th>
                  <th>Type</th>
                  <th>Pavillon</th>
                  <th>Longueur</th>
                  <th>Types cumulés</th>
                  <th>Vitesse max</th>
                  <th>ROT max</th>
                  <th>Zone à risque</th>
                  <th>Détecteurs déclenchés</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r, i) => (
                  <tr key={r.mmsi}>
                    <td className="muted">{i + 1}</td>
                    <td><span className={scoreBadgeClass(r.score_max)}>{r.score_max.toFixed(2)}</span></td>
                    <td style={{ fontWeight: 600 }}>{r.name}</td>
                    <td className="muted">{r.type}</td>
                    <td className="muted">{r.flag}</td>
                    <td className="mono">{r.length ?? '—'}</td>
                    <td>
                      <span className="badge badge-teal" style={{ fontFamily: 'inherit', fontWeight: 700 }}>
                        {r.nb_types}
                      </span>
                    </td>
                    <td className="mono">{fmt(r.speed_max)} nd</td>
                    <td className="mono">{fmt(r.rot_max)}°/min</td>
                    <td>
                      {r.in_zone
                        ? <span style={{ fontSize: 12 }}>{NIVEAU_EMOJI[r.zone_max_lvl_str]} {r.zone_max_name}</span>
                        : <span className="muted">—</span>
                      }
                    </td>
                    <td className="muted" style={{ fontSize: 11, maxWidth: 260, whiteSpace: 'normal' }}>
                      {r.types_list}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Scatter */}
      {aggregated.length > 0 && (
        <div className="card">
          <div className="card-title">Types de fraude cumulés vs score maximum</div>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ left: 8, right: 24, top: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                type="number" dataKey="nb_types" name="Types de fraude"
                label={{ value: 'Types de fraude', position: 'insideBottom', offset: -4, fill: '#7a97be', fontSize: 12 }}
                tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false}
                domain={[0.5, 8.5]} ticks={[1,2,3,4,5,6,7,8]}
              />
              <YAxis
                type="number" dataKey="score_max" name="Score max"
                domain={[0.4, 1.0]}
                tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false}
              />
              <Tooltip content={<TIP />} cursor={{ strokeDasharray:'3 3' }} />
              <Scatter data={aggregated} name="Navires">
                {aggregated.map(r => (
                  <Cell
                    key={r.mmsi}
                    fill={scoreColor(r.score_max)}
                    fillOpacity={0.8}
                    r={Math.max(5, r.nb_types * 3)}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
