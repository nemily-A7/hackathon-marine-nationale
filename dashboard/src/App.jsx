import { useState, useMemo, useEffect } from 'react'
import { Menu, Anchor } from 'lucide-react'
import { DEFAULT_CONFIG, FRAUD_TYPES_ORDER } from './mockData'
import { recomputeScore } from './utils'
import Sidebar     from './Sidebar'
import VueGlobale  from './tabs/VueGlobale'
import Carte       from './tabs/Carte'
import Detecteurs  from './tabs/Detecteurs'
import TopSuspects from './tabs/TopSuspects'
import Zones       from './tabs/Zones'
import Reporting   from './tabs/Reporting'

const TABS = [
  { id:'overview',   label:'Vue globale',    icon:'📊' },
  { id:'map',        label:'Carte',          icon:'🗺️' },
  { id:'detectors',  label:'Détecteurs',     icon:'🔍' },
  { id:'suspects',   label:'Top suspects',   icon:'🏆' },
  { id:'zones',      label:'Zones à risque', icon:'⚠️' },
  { id:'reporting',  label:'Reporting',      icon:'📋' },
]

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeTab,   setActiveTab]   = useState('overview')
  const [config,      setConfig]      = useState(DEFAULT_CONFIG)

  // ── Chargement des vraies données JSON (exportées par export_data.py) ──
  const [rawShips,      setRawShips]      = useState([])
  const [rawDetections, setRawDetections] = useState([])
  const [zones,         setZones]         = useState([])
  const [loading,       setLoading]       = useState(true)
  const [error,         setError]         = useState(null)

  useEffect(() => {
    Promise.all([
      fetch('/data/ships.json').then(r => r.json()),
      fetch('/data/detections.json').then(r => r.json()),
      fetch('/data/zones.json').then(r => r.json()),
    ])
      .then(([s, d, z]) => {
        setRawShips(s)
        setRawDetections(d)
        setZones(z)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  const shipMap = useMemo(
    () => Object.fromEntries(rawShips.map(s => [String(s.mmsi), s])),
    [rawShips]
  )

  // ── Recalcul des scores à chaque changement de config ──
  const detections = useMemo(() => {
    return rawDetections
      .map(d => {
        const ship = shipMap[String(d.mmsi)]
        const cf   = recomputeScore(d, ship, config)
        return { ...d, confidence_final: cf }
      })
      .filter(d => d.confidence_final >= config.threshold)
  }, [rawDetections, shipMap, config])

  const stats = useMemo(() => ({
    total_ships:  rawShips.length,
    total_alerts: detections.length,
    unique_ships: new Set(detections.map(d => d.mmsi)).size,
    high_conf:    detections.filter(d => d.confidence_final >= 0.8).length,
    in_risk_zone: detections.filter(d => d.risk_zone_name).length,
  }), [rawShips, detections])

  function updateConfig(patch) {
    setConfig(prev => ({ ...prev, ...patch }))
  }

  // ── Écrans de chargement / erreur ──
  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', flexDirection:'column', gap:16 }}>
      <Anchor size={36} color="var(--teal)" style={{ animation:'spin 1.5s linear infinite' }} />
      <div style={{ color:'var(--text-muted)', fontSize:14 }}>Chargement des données…</div>
      <style>{`@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`}</style>
    </div>
  )

  if (error) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', flexDirection:'column', gap:12 }}>
      <div style={{ color:'var(--red)', fontSize:16, fontWeight:700 }}>Erreur de chargement</div>
      <div style={{ color:'var(--text-muted)', fontSize:13 }}>{error}</div>
      <div style={{ color:'var(--text-dim)', fontSize:12 }}>
        Lancez d'abord : <code style={{ background:'var(--bg-card)', padding:'2px 8px', borderRadius:4 }}>python3 export_data.py</code>
      </div>
    </div>
  )

  const tabProps = { detections, ships: rawShips, shipMap, config, zones }

  return (
    <div className="layout">
      <Sidebar open={sidebarOpen} config={config} onChange={updateConfig} />

      <div className="main">
        {/* Top bar */}
        <div className="topbar">
          <button className="topbar-toggle" onClick={() => setSidebarOpen(v => !v)}>
            <Menu size={18} />
          </button>
          <div className="topbar-title">
            <Anchor size={18} color="var(--teal)" />
            <h1>Détection de fraude maritime</h1>
            <span>V2 — {rawShips.length.toLocaleString('fr')} navires</span>
          </div>
        </div>

        {/* KPI bar */}
        <div className="kpi-bar">
          <div className="kpi-card ok">
            <div className="kpi-label">Navires analysés</div>
            <div className="kpi-value">{stats.total_ships.toLocaleString('fr')}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Alertes totales</div>
            <div className="kpi-value">{stats.total_alerts.toLocaleString('fr')}</div>
          </div>
          <div className="kpi-card warn">
            <div className="kpi-label">Navires alertés</div>
            <div className="kpi-value">{stats.unique_ships.toLocaleString('fr')}</div>
          </div>
          <div className="kpi-card accent">
            <div className="kpi-label">Score ≥ 0.8</div>
            <div className="kpi-value">{stats.high_conf.toLocaleString('fr')}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Alertes en zone</div>
            <div className="kpi-value">{stats.in_risk_zone.toLocaleString('fr')}</div>
          </div>
        </div>

        {/* Tab nav */}
        <div className="tab-nav">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="tab-content">
          {activeTab === 'overview'   && <VueGlobale  {...tabProps} />}
          {activeTab === 'map'        && <Carte        {...tabProps} />}
          {activeTab === 'detectors'  && <Detecteurs   {...tabProps} />}
          {activeTab === 'suspects'   && <TopSuspects  {...tabProps} />}
          {activeTab === 'zones'      && <Zones        {...tabProps} />}
          {activeTab === 'reporting'  && <Reporting    {...tabProps} />}
        </div>
      </div>
    </div>
  )
}
