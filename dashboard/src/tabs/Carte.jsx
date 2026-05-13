import { useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Marker, Popup, Polygon, LayersControl } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { FRAUD_TYPES_ORDER } from '../mockData'
import { scoreColor, NIVEAU_COLOR, NIVEAU_EMOJI, fmt } from '../utils'

// Fix default Leaflet marker icon
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

function alertIcon(score) {
  const col = score >= 0.8 ? '#e8254a' : score >= 0.65 ? '#f97316' : '#eab308'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28">
    <circle cx="12" cy="12" r="11" fill="${col}" fill-opacity=".85" stroke="#111" stroke-width="1.5"/>
    <text x="12" y="16" font-size="12" text-anchor="middle" fill="white">⚠</text>
  </svg>`
  return L.divIcon({
    className: '',
    html: svg,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  })
}

function ShipPopup({ ship, allDets }) {
  const sorted = [...(allDets ?? [])].sort((a, b) => b.confidence_final - a.confidence_final)
  return (
    <div style={{ minWidth: 240, maxWidth: 320, fontFamily: 'sans-serif', fontSize: 13, lineHeight: 1.5 }}>
      {/* En-tête navire */}
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>
        {sorted.length > 0 ? '⚠️ ' : '✓ '}{ship.name}
      </div>
      <div style={{ color: '#7a97be', fontSize: 11, marginBottom: 6 }}>MMSI : {ship.mmsi}</div>
      <div>🚢 {ship.type} &nbsp;|&nbsp; 🏳️ {ship.flag}</div>
      <div style={{ marginBottom: 4 }}>
        ⚡ {fmt(ship.speed_max)} nd &nbsp;|&nbsp; 🧭 ROT {fmt(ship.rot_max)}°/min
      </div>
      {ship.destination && <div style={{ marginBottom: 4 }}>📍 {ship.destination}</div>}

      {/* Liste de toutes les anomalies */}
      {sorted.length > 0 && (
        <div style={{ marginTop: 8, borderTop: '1px solid #253960', paddingTop: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '.05em', color: '#7a97be', marginBottom: 2 }}>
            {sorted.length} anomalie{sorted.length > 1 ? 's' : ''} détectée{sorted.length > 1 ? 's' : ''}
          </div>
          {sorted.map((d, i) => (
            <div key={i} style={{ background: 'rgba(255,255,255,.04)', borderRadius: 4, padding: '5px 8px', borderLeft: `3px solid ${scoreColor(d.confidence_final)}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: scoreColor(d.confidence_final), fontWeight: 700, fontSize: 12 }}>
                  {d.fraud_type}
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: 12, color: scoreColor(d.confidence_final) }}>
                  {d.confidence_final.toFixed(2)}
                </span>
              </div>
              {d.risk_zone_name && (
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  {NIVEAU_EMOJI[d.risk_zone_level]} {d.risk_zone_name}
                </div>
              )}
              <div style={{ fontSize: 10, color: '#64748b', marginTop: 2, lineHeight: 1.4 }}>
                {d.description?.length > 80 ? d.description.slice(0, 80) + '…' : d.description}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Carte({ detections, ships, zones = [] }) {
  const [fraudFilter, setFraudFilter] = useState('')
  const [minScore,    setMinScore]    = useState(0)

  // Toutes les détections filtrées, groupées par mmsi
  const { worstByMmsi, allByMmsi } = useMemo(() => {
    const worst = {}
    const all   = {}
    const filtered = detections
      .filter(d => !fraudFilter || d.fraud_type === fraudFilter)
      .filter(d => d.confidence_final >= minScore)
    filtered.forEach(d => {
      // worst : pour la couleur du marqueur
      if (!worst[d.mmsi] || d.confidence_final > worst[d.mmsi].confidence_final) {
        worst[d.mmsi] = d
      }
      // all : pour le popup complet
      if (!all[d.mmsi]) all[d.mmsi] = []
      all[d.mmsi].push(d)
    })
    return { worstByMmsi: worst, allByMmsi: all }
  }, [detections, fraudFilter, minScore])

  const alertedMmsis = new Set(Object.keys(worstByMmsi))
  const shipsWithPos = ships.filter(s => s.lat_ais != null && s.lon_ais != null)
  const alerted = shipsWithPos.filter(s => alertedMmsis.has(s.mmsi))
  const clean   = shipsWithPos.filter(s => !alertedMmsis.has(s.mmsi))

  return (
    <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="map-controls">
        <label>
          Type de fraude :
          <select style={{ marginLeft: 8 }} value={fraudFilter} onChange={e => setFraudFilter(e.target.value)}>
            <option value="">Tous</option>
            {FRAUD_TYPES_ORDER.map(ft => <option key={ft} value={ft}>{ft}</option>)}
          </select>
        </label>
        <label>
          Score minimum :
          <select style={{ marginLeft: 8 }} value={minScore} onChange={e => setMinScore(Number(e.target.value))}>
            {[0, 0.5, 0.65, 0.8].map(v => <option key={v} value={v}>{v === 0 ? 'Tous' : `≥ ${v}`}</option>)}
          </select>
        </label>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
          {alerted.length} alertes · {clean.length} normaux · {shipsWithPos.length} total
        </span>
      </div>

      <div className="map-container" style={{ position: 'relative' }}>
        <MapContainer
          center={[25, 15]}
          zoom={2}
          style={{ height: '100%', width: '100%' }}
          preferCanvas
        >
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="Sombre (CartoDB)">
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution='© OpenStreetMap contributors © CARTO'
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Standard">
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='© OpenStreetMap contributors'
              />
            </LayersControl.BaseLayer>

            <LayersControl.Overlay checked name="Zones à risque">
              <>
                {zones.map(z => (
                  <Polygon
                    key={z.id}
                    positions={z.polygon}
                    pathOptions={{
                      color: NIVEAU_COLOR[z.level],
                      weight: 1.5,
                      fillColor: NIVEAU_COLOR[z.level],
                      fillOpacity: 0.12,
                    }}
                  >
                    <Popup>
                      <strong>{z.name}</strong><br />
                      {NIVEAU_EMOJI[z.level]} {z.level} · {z.type}
                    </Popup>
                  </Polygon>
                ))}
              </>
            </LayersControl.Overlay>

            <LayersControl.Overlay checked name="Navires sans alerte">
              <>
                {clean.map(s => (
                  <CircleMarker
                    key={s.mmsi}
                    center={[s.lat_ais, s.lon_ais]}
                    radius={4}
                    pathOptions={{ color: '#6495ed', fillColor: '#6495ed', fillOpacity: 0.6, weight: 0 }}
                  >
                    <Popup><ShipPopup ship={s} allDets={[]} /></Popup>
                  </CircleMarker>
                ))}
              </>
            </LayersControl.Overlay>

            <LayersControl.Overlay checked name="Navires alertés">
              <>
                {alerted.map(s => {
                  const worst = worstByMmsi[s.mmsi]
                  return (
                    <Marker
                      key={s.mmsi}
                      position={[s.lat_ais, s.lon_ais]}
                      icon={alertIcon(worst.confidence_final)}
                    >
                      <Popup maxWidth={340}>
                        <ShipPopup ship={s} allDets={allByMmsi[s.mmsi] ?? []} />
                      </Popup>
                    </Marker>
                  )
                })}
              </>
            </LayersControl.Overlay>
          </LayersControl>
        </MapContainer>

        {/* Legend */}
        <div className="map-legend">
          <div style={{ fontWeight: 700, marginBottom: 4, fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Score de fraude</div>
          <div><span style={{ color:'#e8254a' }}>●</span> ≥ 0.8 — Critique</div>
          <div><span style={{ color:'#f97316' }}>●</span> 0.65–0.8 — Élevé</div>
          <div><span style={{ color:'#eab308' }}>●</span> 0.5–0.65 — Modéré</div>
          <div><span style={{ color:'#6495ed' }}>●</span> Aucune alerte</div>
          <div style={{ marginTop: 8, fontWeight: 700, fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Zones</div>
          {Object.entries(NIVEAU_COLOR).map(([n, c]) => (
            <div key={n}><span style={{ color: c }}>■</span> {NIVEAU_EMOJI[n]} {n}</div>
          ))}
        </div>
      </div>
    </div>
  )
}
