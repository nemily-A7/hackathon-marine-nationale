import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { SHIP_TYPES_LIST } from './mockData'

function Section({ title, icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="param-section">
      <div className="param-section-header" onClick={() => setOpen(v => !v)}>
        <span>{icon} {title}</span>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </div>
      {open && <div className="param-section-body">{children}</div>}
    </div>
  )
}

function Slider({ label, min, max, step, value, onChange, hint }) {
  return (
    <div className="param-row">
      <div className="param-label">
        <span>{label}</span>
        <strong>{typeof value === 'number' ? value.toFixed(step < 0.1 ? 2 : step < 1 ? 1 : 0) : value}</strong>
      </div>
      <input type="range" min={min} max={max} step={step}
        value={value} onChange={e => onChange(Number(e.target.value))} />
      {hint && <p className="param-hint">{hint}</p>}
    </div>
  )
}

export default function Sidebar({ open, config, onChange }) {
  function patchSpeed(type, val) {
    onChange({ speed_max_by_type: { ...config.speed_max_by_type, [type]: Number(val) } })
  }
  function patchRot(type, val) {
    onChange({ rot_max_by_type: { ...config.rot_max_by_type, [type]: Number(val) } })
  }
  function patchBoost(level, val) {
    onChange({ boost_by_niveau: { ...config.boost_by_niveau, [level]: Number(val) } })
  }

  return (
    <div className={`sidebar ${open ? '' : 'collapsed'}`}>
      <div className="sidebar-header">
        <span>⚙️</span>
        <h2>Paramètres de détection</h2>
      </div>
      <div className="sidebar-body">

        <Section title="Seuil global" icon="🎯" defaultOpen>
          <Slider label="Score minimum pour alerter" min={0.3} max={0.9} step={0.05}
            value={config.threshold}
            onChange={v => onChange({ threshold: v })}
            hint="Abaisser = plus d'alertes. Relever = plus strict." />
        </Section>

        <Section title="Speed Anomaly — Vitesse" icon="⚡">
          <p className="param-hint" style={{marginBottom:8}}>
            Vitesse max par type de navire (nœuds). Un dépassement × marge déclenche une alerte.
          </p>
          <div className="type-grid">
            {SHIP_TYPES_LIST.map(t => (
              <div key={t} className="type-input-row">
                <span>{t}</span>
                <input type="number" min={3} max={60}
                  value={config.speed_max_by_type[t] ?? 20}
                  onChange={e => patchSpeed(t, e.target.value)} />
              </div>
            ))}
          </div>
          <Slider label="Marge de tolérance (×)" min={1.0} max={1.8} step={0.05}
            value={config.overspeed_margin}
            onChange={v => onChange({ overspeed_margin: v })}
            hint="1.2 = alerte si vitesse > 120% du max." />
        </Section>

        <Section title="Course Anomaly — ROT" icon="🧭">
          <p className="param-hint" style={{marginBottom:8}}>
            ROT = taux de virement (°/min). Seuil d'alerte = max × multiplicateur.
          </p>
          <div className="type-grid">
            {SHIP_TYPES_LIST.map(t => (
              <div key={t} className="type-input-row">
                <span>{t}</span>
                <input type="number" min={5} max={120}
                  value={config.rot_max_by_type[t] ?? 30}
                  onChange={e => patchRot(t, e.target.value)} />
              </div>
            ))}
          </div>
          <Slider label="Multiplicateur du seuil (×)" min={1.0} max={3.0} step={0.1}
            value={config.rot_threshold_multiplier}
            onChange={v => onChange({ rot_threshold_multiplier: v })}
            hint="1.5 = alerte si ROT > 150% du max normal." />
        </Section>

        <Section title="Position Mismatch" icon="📍">
          <p className="param-hint" style={{marginBottom:8}}>
            Compare la position AIS déclarée avec la position radio mesurée.
          </p>
          <Slider label="Distance min pour alerter (km)" min={5} max={200} step={5}
            value={config.dist_min_km}
            onChange={v => onChange({ dist_min_km: v })}
            hint="En dessous, l'écart est considéré normal." />
          <Slider label="Distance = score max (km)" min={100} max={2000} step={50}
            value={config.dist_max_km}
            onChange={v => onChange({ dist_max_km: v })}
            hint="Au-delà, le score plafonne à 0.99." />
          <Slider label="Pénalité si pas de sync (×)" min={0.2} max={1.0} step={0.05}
            value={config.no_sync_temp_factor}
            onChange={v => onChange({ no_sync_temp_factor: v })} />
        </Section>

        <Section title="Signal Radio — SNR" icon="📡">
          <p className="param-hint" style={{marginBottom:8}}>
            SNR (dB) = qualité du signal radio. Affecte Position Mismatch, Fake Flag, Spoofing.
          </p>
          <Slider label="SNR → qualité max (dB)" min={15} max={50} step={1}
            value={config.snr_high}
            onChange={v => onChange({ snr_high: v })} />
          <Slider label="SNR → qualité intermédiaire (dB)" min={5} max={25} step={1}
            value={config.snr_mid}
            onChange={v => onChange({ snr_mid: v })} />
        </Section>

        <Section title="Destination Mismatch" icon="🏁">
          <p className="param-hint" style={{marginBottom:8}}>
            Vérifie la cohérence entre le cap réel et la destination déclarée.
          </p>
          <Slider label="Tolérance angulaire (°)" min={10} max={90} step={5}
            value={config.dest_angle_tolerance}
            onChange={v => onChange({ dest_angle_tolerance: v })}
            hint="En dessous, le cap est considéré normal." />
        </Section>

        <Section title="Zone Risk Boost" icon="⚠️">
          <p className="param-hint" style={{marginBottom:8}}>
            Bonus ajouté au score si le navire est dans une zone à risque.
          </p>
          {[['SURVEILLE','🔵',0,0.20],['MODERE','🟡',0,0.20],['ELEVE','🟠',0,0.30],['EXTREME','🔴',0,0.30]].map(([lvl,em,mn,mx]) => (
            <Slider key={lvl} label={`${em} ${lvl} — bonus`} min={mn} max={mx} step={0.01}
              value={config.boost_by_niveau[lvl] ?? 0}
              onChange={v => patchBoost(lvl, v)} />
          ))}
        </Section>

      </div>
    </div>
  )
}
