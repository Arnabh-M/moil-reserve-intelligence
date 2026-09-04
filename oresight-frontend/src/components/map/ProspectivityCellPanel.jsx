import React from 'react'
import { X, AlertTriangle, ShieldCheck, Layers, TrendingDown } from 'lucide-react'
import Badge from '../Badge'
import { CONFIDENCE_BAND_COLORS } from '../../lib/map'

/**
 * PART 7.10 — Detail panel for a clicked prospectivity grid cell.
 *
 * Shows the ensemble score and band prominently, then the individual
 * contributing factors from Part 6.3, the data-quality badge, and the
 * auto-generated recommendation.
 */

// Display metadata for the Part 6.3 factor fields.
const FACTOR_META = [
  { key: 'ndvi_anomaly', label: 'NDVI Anomaly', unit: '', digits: 3 },
  { key: 'ndri', label: 'NDRI (Rock Index)', unit: '', digits: 3 },
  { key: 'ndwi', label: 'NDWI (Water)', unit: '', digits: 3 },
  { key: 'iron_oxide_index', label: 'Iron-Oxide Ratio', unit: '', digits: 3 },
  { key: 'clay_index', label: 'Clay Mineral Index', unit: '', digits: 3 },
  { key: 'manganese_spectral_ratio', label: 'Mn Spectral Ratio', unit: '', digits: 3 },
  { key: 'slope', label: 'Slope', unit: '°', digits: 1 },
  { key: 'aspect', label: 'Aspect', unit: '°', digits: 0 },
  { key: 'terrain_ruggedness', label: 'Terrain Ruggedness', unit: '', digits: 3 },
  { key: 'structural_density', label: 'Structural Density', unit: ' lines/2km', digits: 0 },
]

function formatValue(value, digits, unit) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${Number(value).toFixed(digits)}${unit}`
}

export default function ProspectivityCellPanel({ cell, siteName, onClose, isPlaceholder = false }) {
  if (!cell) return null

  const band = cell.confidence_band
  const score = Number(cell.ensemble_confidence_score ?? 0)
  const quality = (cell.data_quality || 'low').toLowerCase()
  const ndviAlert = cell.ndvi_anomaly_alert === true || cell.ndvi_anomaly_alert === 'true'
  const isPriority = band === 'High' || band === 'Very High'

  return (
    <aside
      aria-label="Prospectivity cell detail"
      className="absolute top-4 right-4 bottom-4 z-30 w-96 max-w-[calc(100%-2rem)] overflow-y-auto rounded-[3px] border border-border bg-bg-surface shadow-xs"
    >
      {/* Header */}
      <div className="flex items-start justify-between border-b border-border px-5 py-4">
        <div>
          <h2 className="font-heading text-sm font-bold text-navy">Reserve Cell Detail</h2>
          <p className="mt-1 text-xs text-text-muted">
            {siteName || cell.site_id} · {cell.cell_id}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close cell detail"
          className="rounded-[3px] p-1 text-text-muted transition-colors hover:text-navy cursor-pointer"
        >
          <X size={16} />
        </button>
      </div>

      {isPlaceholder && (
        <div className="mx-5 mt-4 rounded-[3px] border border-warning/40 bg-warning/10 px-3 py-2">
          <p className="text-[11px] font-semibold text-warning">Placeholder scores</p>
          <p className="mt-0.5 text-[10px] text-text-muted">
            Geometry is real; model values are not. Pending Earth Engine credentials
            and real deposit ground truth.
          </p>
        </div>
      )}

      {/* Part 7.10 — score + band, prominent */}
      <div className="px-5 py-4">
        <div className="rounded-[3px] border border-border bg-bg/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
              Ensemble Confidence
            </span>
            <span
              className="rounded-[3px] px-2 py-0.5 text-[10px] font-bold text-white"
              style={{ backgroundColor: CONFIDENCE_BAND_COLORS[band] || '#999' }}
            >
              {band}
            </span>
          </div>
          <div className="mt-2 font-heading text-3xl font-bold tracking-tight text-navy">
            {(score * 100).toFixed(1)}%
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(100, Math.max(0, score * 100))}%`,
                backgroundColor: CONFIDENCE_BAND_COLORS[band] || '#999',
              }}
            />
          </div>
          <p className="mt-2 font-mono text-[10px] text-text-muted">
            {cell.model_agreement_count ?? 0} of 3 models concur · {cell.cell_size_m ?? '—'} m cell
          </p>
        </div>

        {/* Part 7.10 — data quality badge */}
        <div className="mt-4 flex items-center gap-2">
          <Badge variant={quality === 'high' ? 'operational' : 'warning'} dot>
            Data quality: {quality === 'high' ? 'High' : 'Low'}
          </Badge>
          {ndviAlert && (
            <Badge variant="critical">
              <TrendingDown size={11} className="mr-1 inline" />
              NDVI anomaly
            </Badge>
          )}
        </div>

        {/* Part 7.10 — auto-generated recommendation */}
        <div
          className={`mt-4 flex items-start gap-2 rounded-[3px] border px-3 py-2.5 ${
            isPriority && quality === 'high'
              ? 'border-success/40 bg-success/10'
              : 'border-border bg-bg/60'
          }`}
        >
          {isPriority && quality === 'high' ? (
            <ShieldCheck size={14} className="mt-0.5 shrink-0 text-success" />
          ) : (
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-text-muted" />
          )}
          <p className="text-xs font-medium text-navy">{cell.recommendation || 'No recommendation'}</p>
        </div>

        {/* Part 7.10 — contributing factor breakdown */}
        <div className="mt-5">
          <div className="mb-2 flex items-center gap-2">
            <Layers size={13} className="text-teal" />
            <h3 className="font-heading text-xs font-bold uppercase tracking-wider text-navy">
              Contributing Factors
            </h3>
          </div>
          <div className="divide-y divide-border rounded-[3px] border border-border">
            {FACTOR_META.map(({ key, label, unit, digits }) => {
              const value = cell[key]
              const flagged = key === 'ndvi_anomaly' && ndviAlert
              return (
                <div
                  key={key}
                  className={`flex items-center justify-between px-3 py-2 ${
                    flagged ? 'bg-warning/10' : ''
                  }`}
                >
                  <span className={`text-[11px] ${flagged ? 'font-semibold text-warning' : 'text-text-muted'}`}>
                    {label}
                    {flagged && <span className="ml-1 font-normal">(beyond −10%)</span>}
                  </span>
                  <span
                    className={`font-mono text-[11px] font-semibold ${
                      flagged ? 'text-warning' : 'text-navy'
                    }`}
                  >
                    {formatValue(value, digits, unit)}
                  </span>
                </div>
              )
            })}
          </div>
          <p className="mt-2 text-[10px] text-text-muted">
            Values are the mean across the 100 m analysis cells aggregated into this render cell.
          </p>
        </div>
      </div>
    </aside>
  )
}
