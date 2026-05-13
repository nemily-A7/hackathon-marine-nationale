import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer,
  ScatterChart, Scatter, CartesianGrid, ReferenceLine,
} from 'recharts'
import { scoreColor, NIVEAU_COLOR } from '../utils'
import { FRAUD_TYPES_ORDER, RISK_ZONES } from '../mockData'

const TIP = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="custom-tooltip">
      <div className="label">{label ?? payload[0]?.name}</div>
      {payload.map((p, i) => (
        <div key={i} className="val" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed ? p.value.toFixed(2) : p.value : p.value}
        </div>
      ))}
    </div>
  )
}

export default function VueGlobale({ detections, ships }) {
  const byType = useMemo(() => {
    const counts = {}
    FRAUD_TYPES_ORDER.forEach(t => { counts[t] = 0 })
    detections.forEach(d => { counts[d.fraud_type] = (counts[d.fraud_type] ?? 0) + 1 })
    return FRAUD_TYPES_ORDER
      .map(t => ({ type: t, count: counts[t] }))
      .filter(x => x.count > 0)
      .sort((a, b) => a.count - b.count)
  }, [detections])

  const byTypeScore = useMemo(() => {
    const acc = {}
    detections.forEach(d => {
      if (!acc[d.fraud_type]) acc[d.fraud_type] = []
      acc[d.fraud_type].push(d.confidence_final)
    })
    return Object.entries(acc)
      .map(([type, scores]) => ({
        type,
        score: scores.reduce((a, b) => a + b, 0) / scores.length,
      }))
      .sort((a, b) => a.score - b.score)
  }, [detections])

  const byFlag = useMemo(() => {
    const counts = {}
    detections.forEach(d => { counts[d.flag] = (counts[d.flag] ?? 0) + 1 })
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([flag, count]) => ({ flag, count }))
      .reverse()
  }, [detections])

  // Histogram: bucket [0.5, 1.0] in 0.05 bins
  const histogram = useMemo(() => {
    const bins = {}
    for (let b = 0.50; b < 1.0; b = Math.round((b + 0.05) * 100) / 100) {
      bins[b.toFixed(2)] = 0
    }
    detections.forEach(d => {
      const k = (Math.floor(d.confidence_final / 0.05) * 0.05).toFixed(2)
      if (bins[k] !== undefined) bins[k]++
    })
    return Object.entries(bins).map(([bin, cnt]) => ({
      bin: `${(Number(bin) * 100).toFixed(0)}%`,
      cnt,
      color: Number(bin) >= 0.8 ? '#e8254a' : Number(bin) >= 0.65 ? '#f97316' : '#eab308',
    }))
  }, [detections])

  // Stacked bars: ship type × fraud type
  const byShipType = useMemo(() => {
    const acc = {}
    detections.forEach(d => {
      if (!acc[d.type]) acc[d.type] = {}
      acc[d.type][d.fraud_type] = (acc[d.type][d.fraud_type] ?? 0) + 1
    })
    return Object.entries(acc).map(([type, frauds]) => ({ type, ...frauds }))
  }, [detections])

  const FRAUD_COLORS = {
    "AIS Disabled":"#3b82f6","Speed Anomaly":"#e8254a","Course Anomaly":"#f97316",
    "Position Mismatch":"#a855f7","Fake Flag":"#06b6d4","Name Change":"#84cc16",
    "Spoofing":"#ec4899","Destination Mismatch":"#eab308",
  }

  if (detections.length === 0) {
    return <div className="empty">Aucune alerte avec le seuil actuel — abaissez le curseur.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="grid-2">
        <div className="card">
          <div className="card-title">Alertes par type de fraude</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byType} layout="vertical" margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
              <XAxis type="number" tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="type" width={145} tick={{ fill:'#dce8f8', fontSize:11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<TIP />} cursor={{ fill:'rgba(255,255,255,.04)' }} />
              <Bar dataKey="count" name="Alertes" radius={[0,4,4,0]}>
                {byType.map(e => <Cell key={e.type} fill={FRAUD_COLORS[e.type] ?? '#7a97be'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-title">Score moyen par type</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byTypeScore} layout="vertical" margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
              <XAxis type="number" domain={[0,1]} tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="type" width={145} tick={{ fill:'#dce8f8', fontSize:11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<TIP />} cursor={{ fill:'rgba(255,255,255,.04)' }} />
              <ReferenceLine x={0.5} stroke="#555" strokeDasharray="3 3" />
              <ReferenceLine x={0.8} stroke="#e8254a" strokeDasharray="3 3" />
              <Bar dataKey="score" name="Score moyen" radius={[0,4,4,0]}>
                {byTypeScore.map(e => <Cell key={e.type} fill={scoreColor(e.score)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-title">Alertes par pavillon (top 10)</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byFlag} layout="vertical" margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
              <XAxis type="number" tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="flag" width={120} tick={{ fill:'#dce8f8', fontSize:11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<TIP />} cursor={{ fill:'rgba(255,255,255,.04)' }} />
              <Bar dataKey="count" name="Alertes" fill="var(--ocean)" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-title">Distribution des scores finaux</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={histogram} margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
              <XAxis dataKey="bin" tick={{ fill:'#7a97be', fontSize:10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<TIP />} cursor={{ fill:'rgba(255,255,255,.04)' }} />
              <ReferenceLine x="80%" stroke="#e8254a" strokeDasharray="3 3" />
              <Bar dataKey="cnt" name="Alertes" radius={[4,4,0,0]}>
                {histogram.map(e => <Cell key={e.bin} fill={e.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Alertes par type de navire et type de fraude</div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={byShipType} margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
            <XAxis dataKey="type" tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill:'#7a97be', fontSize:11 }} axisLine={false} tickLine={false} />
            <Tooltip content={<TIP />} cursor={{ fill:'rgba(255,255,255,.04)' }} />
            {FRAUD_TYPES_ORDER.map(ft => (
              <Bar key={ft} dataKey={ft} stackId="a" fill={FRAUD_COLORS[ft]} name={ft} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
