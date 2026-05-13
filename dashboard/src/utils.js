export function exportCSV(rows, filename = 'export.csv') {
  if (!rows.length) return
  const cols = Object.keys(rows[0])
  const escape = v => {
    if (v == null) return ''
    const s = String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => escape(r[c])).join(','))].join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}

export function scoreColor(s) {
  if (s >= 0.8)  return '#e8254a'
  if (s >= 0.65) return '#f97316'
  return '#eab308'
}

export function scoreBadgeClass(s) {
  if (s >= 0.8)  return 'badge badge-red'
  if (s >= 0.65) return 'badge badge-orange'
  return 'badge badge-yellow'
}

export function scoreLabel(s) {
  if (s >= 0.8)  return '● Critique'
  if (s >= 0.65) return '● Élevé'
  return '● Modéré'
}

export const NIVEAU_COLOR = {
  EXTREME:   '#e8254a',
  ELEVE:     '#f97316',
  MODERE:    '#eab308',
  SURVEILLE: '#3b82f6',
}

export const NIVEAU_BADGE = {
  EXTREME:   'badge-red',
  ELEVE:     'badge-orange',
  MODERE:    'badge-yellow',
  SURVEILLE: 'badge-blue',
}

export const NIVEAU_EMOJI = {
  EXTREME: '🔴', ELEVE: '🟠', MODERE: '🟡', SURVEILLE: '🔵',
}

export const NIVEAU_ORDER = { EXTREME: 4, ELEVE: 3, MODERE: 2, SURVEILLE: 1 }

export function fmt(v, dec = 1) {
  if (v == null || isNaN(v)) return '—'
  return Number(v).toFixed(dec)
}

// ── Réimplémentation JS fidèle aux scorers Python de detection_engine.py ─────

function scoreSpeedAnomaly(ship, config) {
  const typeMax = config.speed_max_by_type[ship.type] ?? config.default_speed_max ?? 20
  const margin  = config.overspeed_margin ?? 1.2

  // Sub-signal A : conflit vitesse/statut (indépendant des seuils de type)
  const conflict = ship.speed_conflict_ratio ?? 0
  const score_a  = conflict > 0 ? Math.min(0.5 + conflict * 0.5, 0.99) : 0

  // Sub-signal B : vitesse max > seuil du type × marge
  const threshold = typeMax * margin
  let score_b = 0
  if ((ship.speed_max ?? 0) > threshold) {
    const ratio = (ship.speed_max - typeMax) / typeMax
    score_b = Math.min(0.6 + ratio * 0.3, 0.99)
  }

  return Math.max(score_a, score_b)
}

function scoreCourseAnomaly(ship, config) {
  const typeRotMax  = config.rot_max_by_type[ship.type] ?? config.default_rot_max ?? 30
  const multiplier  = config.rot_threshold_multiplier ?? 1.5
  const rot         = ship.rot_max ?? 0
  const rotThreshold = typeRotMax * multiplier

  if (rot < rotThreshold) return 0
  const scaleRange = Math.max(127 - rotThreshold, 1)
  return Math.min(0.5 + (rot - rotThreshold) / scaleRange * 0.45, 0.99)
}

function scoreDestinationMismatch(ship, config) {
  const tolerance = config.dest_angle_tolerance ?? 45
  const deviation = ship.course_deviation
  if (deviation == null) return 0
  if (['Moored', 'At Anchor'].includes(ship.last_status)) return 0
  if (deviation < tolerance) return 0
  return Math.min(0.4 + (deviation - tolerance) / Math.max(180 - tolerance, 1) * 0.59, 0.99)
}

// Recalcule le score final en fonction de la config courante.
// Speed Anomaly, Course Anomaly et Destination Mismatch sont recalculés depuis
// les données brutes du navire. Les autres types conservent le score Python.
export function recomputeScore(det, ship, config) {
  let base = det.confidence ?? 0

  if (ship) {
    if (det.fraud_type === 'Speed Anomaly')
      base = scoreSpeedAnomaly(ship, config)
    else if (det.fraud_type === 'Course Anomaly')
      base = scoreCourseAnomaly(ship, config)
    else if (det.fraud_type === 'Destination Mismatch')
      base = scoreDestinationMismatch(ship, config)
  }

  const boost = det.risk_zone_level
    ? (config.boost_by_niveau[det.risk_zone_level] ?? 0)
    : 0

  return Math.min(base + boost, 0.99)
}
