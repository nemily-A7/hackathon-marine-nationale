import { useState, useEffect, useRef } from 'react'
import { scoreColor, NIVEAU_EMOJI, fmt } from '../utils'

// ── Données de démonstration ──────────────────────────────────────────────────
const MOCK_HISTORY = [
  { id: 1, ts: '2026-05-13 08:00', alerts: 5150, high: 312,  zones: 847, new: 23,  status: 'ok' },
  { id: 2, ts: '2026-05-13 07:50', alerts: 5141, high: 308,  zones: 841, new: 17,  status: 'ok' },
  { id: 3, ts: '2026-05-13 07:40', alerts: 5138, high: 308,  zones: 839, new: 31,  status: 'warn' },
  { id: 4, ts: '2026-05-13 07:30', alerts: 5122, high: 301,  zones: 832, new: 9,   status: 'ok' },
  { id: 5, ts: '2026-05-13 07:20', alerts: 5119, high: 299,  zones: 828, new: 44,  status: 'crit' },
  { id: 6, ts: '2026-05-13 07:10', alerts: 5097, high: 291,  zones: 814, new: 12,  status: 'ok' },
]

const MOCK_EVENTS = [
  { ts: '08:03', type: 'crit',  msg: 'NAVIRE-2770 — Speed Anomaly score 0.99 en zone EXTREME' },
  { ts: '07:58', type: 'warn',  msg: '3 nouveaux navires détectés dans le Golfe de Guinée' },
  { ts: '07:51', type: 'info',  msg: 'Rapport #2 généré — 5141 alertes, 308 critiques' },
  { ts: '07:43', type: 'crit',  msg: 'NAVIRE-9098 — 8 types de fraude simultanés' },
  { ts: '07:41', type: '\'warn', msg: 'Pic d\'alertes Course Anomaly (+31 en 10 min)' },
  { ts: '07:34', type: 'info',  msg: 'Rapport #4 généré — 5122 alertes, 301 critiques' },
  { ts: '07:22', type: 'crit',  msg: 'NAVIRE-5049 — Position Mismatch 450 km, zone ELEVE' },
  { ts: '07:20', type: 'warn',  msg: 'Pic inhabituel : +44 nouvelles alertes en 10 min' },
]

const CHANNELS = [
  { id: 'email',  icon: '📧', label: 'Email', desc: 'Rapport PDF joint' },
  { id: 'teams',  icon: '💬', label: 'Teams', desc: 'Message + résumé' },
  { id: 'syslog', icon: '🖥️', label: 'Syslog', desc: 'SIEM / SOC' },
  { id: 's3',     icon: '☁️', label: 'S3 / Cloud', desc: 'Stockage rapport JSON' },
]

const FREQ_OPTIONS = ['5 min', '10 min', '30 min', '1 heure', '6 heures', '24 heures']

function Countdown({ freq }) {
  const totalSec = {
    '5 min': 300, '10 min': 600, '30 min': 1800,
    '1 heure': 3600, '6 heures': 21600, '24 heures': 86400,
  }[freq] ?? 600

  const [remaining, setRemaining] = useState(Math.floor(totalSec * 0.6))
  const ref = useRef()

  useEffect(() => {
    ref.current = setInterval(() => {
      setRemaining(v => v <= 1 ? totalSec : v - 1)
    }, 1000)
    return () => clearInterval(ref.current)
  }, [totalSec])

  const pct = ((totalSec - remaining) / totalSec) * 100
  const mm  = String(Math.floor(remaining / 60)).padStart(2, '0')
  const ss  = String(remaining % 60).padStart(2, '0')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <svg width={80} height={80} viewBox="0 0 80 80">
        <circle cx={40} cy={40} r={34} fill="none" stroke="var(--border)" strokeWidth={6} />
        <circle cx={40} cy={40} r={34} fill="none" stroke="var(--teal)" strokeWidth={6}
          strokeDasharray={`${2 * Math.PI * 34}`}
          strokeDashoffset={`${2 * Math.PI * 34 * (1 - pct / 100)}`}
          strokeLinecap="round"
          style={{ transform: 'rotate(-90deg)', transformOrigin: '40px 40px', transition: 'stroke-dashoffset 1s linear' }}
        />
        <text x={40} y={45} textAnchor="middle" fill="var(--teal)"
          fontSize={14} fontWeight={700} fontFamily="monospace">
          {mm}:{ss}
        </text>
      </svg>
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>prochain rapport</div>
    </div>
  )
}

function StatusDot({ status }) {
  const col = { ok: '#00c2a8', warn: '#eab308', crit: '#e8254a', info: '#3b82f6' }[status] ?? '#7a97be'
  return <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: col, marginRight: 6, flexShrink: 0 }} />
}

export default function Reporting({ detections, ships }) {
  const [freq,     setFreq]     = useState('10 min')
  const [channels, setChannels] = useState({ email: true, teams: false, syslog: false, s3: false })
  const [minScore, setMinScore] = useState(0.8)
  const [running,  setRunning]  = useState(false)

  const high   = detections.filter(d => d.confidence_final >= 0.8).length
  const inZone = detections.filter(d => d.risk_zone_name).length
  const unique = new Set(detections.map(d => d.mmsi)).size

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Bannière concept ─────────────────────────────────────────── */}
      <div style={{
        background: 'rgba(0,194,168,.07)', border: '1px solid var(--teal-dim)',
        borderRadius: 'var(--radius-lg)', padding: '14px 18px',
        display: 'flex', gap: 14, alignItems: 'flex-start',
      }}>
        <div style={{ fontSize: 22, flexShrink: 0 }}>🔭</div>
        <div>
          <div style={{ fontWeight: 700, color: 'var(--teal)', marginBottom: 4 }}>
            Fonctionnalité en cours de développement — démonstration du concept
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
            Cette page illustre le système de reporting automatique prévu pour la production.
            Dans sa version complète, le moteur de détection Python tourne en continu sur un flux AIS live
            (aisstream.io), génère un rapport structuré à intervalle configurable et le pousse vers
            les canaux sélectionnés. La maquette ci-dessous utilise les données statiques actuelles.
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

        {/* ── Configuration ────────────────────────────────────────────── */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card-title">⚙️ Configuration du reporting</div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>Fréquence de génération</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {FREQ_OPTIONS.map(f => (
                <button key={f}
                  onClick={() => setFreq(f)}
                  style={{
                    padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                    cursor: 'pointer', border: '1px solid',
                    borderColor: freq === f ? 'var(--teal)' : 'var(--border)',
                    background:  freq === f ? 'rgba(0,194,168,.15)' : 'var(--bg-card)',
                    color:       freq === f ? 'var(--teal)' : 'var(--text-muted)',
                    transition: 'all .15s',
                  }}>
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
              Score minimum pour inclusion dans le rapport
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {[0.5, 0.65, 0.8, 0.9].map(v => (
                <button key={v} onClick={() => setMinScore(v)}
                  style={{
                    padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                    cursor: 'pointer', border: '1px solid',
                    borderColor: minScore === v ? scoreColor(v) : 'var(--border)',
                    background:  minScore === v ? `${scoreColor(v)}22` : 'var(--bg-card)',
                    color:       minScore === v ? scoreColor(v) : 'var(--text-muted)',
                  }}>
                  ≥ {v}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>Canaux de diffusion</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {CHANNELS.map(ch => (
                <label key={ch.id} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                  <input type="checkbox"
                    checked={channels[ch.id]}
                    onChange={e => setChannels(p => ({ ...p, [ch.id]: e.target.checked }))}
                    style={{ accentColor: 'var(--teal)', width: 14, height: 14 }}
                  />
                  <span style={{ fontSize: 16 }}>{ch.icon}</span>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{ch.label}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{ch.desc}</span>
                </label>
              ))}
            </div>
          </div>

          <button
            onClick={() => setRunning(v => !v)}
            style={{
              padding: '10px 0', borderRadius: 'var(--radius)', border: 'none',
              fontWeight: 700, fontSize: 13, cursor: 'pointer',
              background: running ? 'rgba(232,37,74,.15)' : 'rgba(0,194,168,.2)',
              color:      running ? 'var(--red)' : 'var(--teal)',
              transition: 'all .2s',
            }}>
            {running ? '⏹ Arrêter le reporting' : '▶ Activer le reporting automatique'}
          </button>

          {running && (
            <div style={{ textAlign: 'center', padding: '8px 0', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{ fontSize: 11, color: 'var(--teal)', fontWeight: 600, marginBottom: 8 }}>ACTIF — fréquence {freq}</div>
              <Countdown freq={freq} />
            </div>
          )}
        </div>

        {/* ── Snapshot du rapport courant ───────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card">
            <div className="card-title">📋 Aperçu du prochain rapport</div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 12 }}>
              Basé sur les données actuelles · seuil ≥ {minScore}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                { label: 'Alertes incluses', val: detections.filter(d => d.confidence_final >= minScore).length, color: 'var(--text)' },
                { label: 'Score critique (≥ 0.8)', val: high, color: 'var(--red)' },
                { label: 'Navires concernés', val: unique, color: 'var(--orange)' },
                { label: 'Alertes en zone', val: inZone, color: 'var(--yellow)' },
              ].map(m => (
                <div key={m.label} style={{ background: 'var(--bg-panel)', borderRadius: 'var(--radius)', padding: '10px 14px' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'monospace', color: m.color }}>{m.val.toLocaleString('fr')}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{m.label}</div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>Canaux actifs</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {CHANNELS.filter(c => channels[c.id]).map(c => (
                  <span key={c.id} className="badge badge-teal">{c.icon} {c.label}</span>
                ))}
                {!Object.values(channels).some(Boolean) && (
                  <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>Aucun canal sélectionné</span>
                )}
              </div>
            </div>
          </div>

          {/* Architecture de scaling */}
          <div className="card">
            <div className="card-title">🏗️ Architecture cible (production)</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
              {[
                { icon: '📡', step: 'Flux AIS live', desc: 'aisstream.io WebSocket mondial' },
                { icon: '⚙️', step: 'Moteur Python', desc: 'detection_engine.py + scheduler (cron / Celery)' },
                { icon: '🗄️', step: 'Base de données', desc: 'PostgreSQL / TimescaleDB pour l\'historique' },
                { icon: '📊', step: 'Dashboard React', desc: 'Ce dashboard — données rafraîchies via API REST' },
                { icon: '📬', step: 'Diffusion', desc: 'Email · Teams · Syslog · S3' },
              ].map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>{s.icon}</span>
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text)' }}>{s.step}</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>— {s.desc}</span>
                  </div>
                </div>
              ))}
              <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: 'var(--bg-panel)', borderRadius: 'var(--radius)', fontSize: 11, color: 'var(--text-muted)' }}>
                🔁 Chaque cycle : lecture flux → détection → diff alertes → rapport → push canaux
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Historique simulé ─────────────────────────────────────────── */}
      <div className="grid-2">
        <div className="card">
          <div className="card-title">🕐 Historique des rapports (simulation)</div>
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Horodatage</th>
                  <th>Alertes</th>
                  <th>Critiques</th>
                  <th>En zone</th>
                  <th>Nouvelles</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_HISTORY.map(r => (
                  <tr key={r.id}>
                    <td className="mono" style={{ fontSize: 11 }}>{r.ts}</td>
                    <td className="mono">{r.alerts.toLocaleString('fr')}</td>
                    <td style={{ color: 'var(--red)', fontFamily: 'monospace' }}>{r.high}</td>
                    <td className="mono">{r.zones}</td>
                    <td style={{ color: r.new > 30 ? 'var(--orange)' : 'var(--text-muted)', fontFamily: 'monospace' }}>+{r.new}</td>
                    <td>
                      <span className={`badge ${r.status === 'crit' ? 'badge-red' : r.status === 'warn' ? 'badge-yellow' : 'badge-teal'}`}>
                        {r.status === 'crit' ? '🔴 Critique' : r.status === 'warn' ? '🟡 Attention' : '✓ Normal'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-title">🔔 Flux d'événements temps réel (simulation)</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {MOCK_EVENTS.map((e, i) => {
              const col = e.type === 'crit' ? 'var(--red)' : e.type === 'warn' ? 'var(--yellow)' : 'var(--text-muted)'
              return (
                <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '7px 10px', borderRadius: 'var(--radius)', background: 'var(--bg-panel)' }}>
                  <StatusDot status={e.type} />
                  <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'monospace', flexShrink: 0, marginTop: 1 }}>{e.ts}</span>
                  <span style={{ fontSize: 12, color: col, lineHeight: 1.4 }}>{e.msg}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
