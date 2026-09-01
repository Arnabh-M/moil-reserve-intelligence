import React from 'react';
import { X, ShieldAlert, Award, Layers, MapPin } from 'lucide-react';
import Badge from '../Badge';

export default function ZoneDetailPanel({ zone, siteName, onClose }) {
  if (!zone) return null;

  const confidenceScore = zone.confidence_score ?? zone.confidence ?? 0;
  const confidencePct = Math.round(confidenceScore * 100);
  const zoneName = zone.zone_name || zone.name || (zone.id ? `Zone #${zone.id}` : 'Reserve Zone');
  const gradePct = zone.estimated_grade_pct ?? zone.grade_percent ?? zone.grade_estimate;

  const confidenceVariant =
    confidenceScore >= 0.7 ? 'operational' : confidenceScore >= 0.4 ? 'warning' : 'critical';

  return (
    <div className="absolute top-4 right-4 bottom-4 z-20 w-80 rounded-2xl border border-border bg-white p-5 shadow-xl transition-all flex flex-col justify-between overflow-y-auto">
      <div>
        {/* Header */}
        <div className="flex items-start justify-between border-b border-border pb-3 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-teal" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
                GeoJSON Feature Detail
              </span>
            </div>
            <h3 className="font-heading text-base font-bold text-navy mt-0.5">{zoneName}</h3>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="rounded-lg p-1 text-text-muted hover:bg-bg hover:text-text-primary transition-colors duration-150"
            aria-label="Close detail panel"
          >
            <X size={18} />
          </button>
        </div>

        {/* Site badge */}
        {siteName && (
          <div className="flex items-center gap-2 mb-4 bg-bg px-3 py-2 rounded-xl border border-border">
            <MapPin size={15} className="text-orange shrink-0" />
            <div>
              <p className="text-[10px] text-text-muted font-medium">Mine Site</p>
              <p className="text-xs font-semibold text-navy">{siteName}</p>
            </div>
          </div>
        )}

        {/* Confidence Score section */}
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-bg/50 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-secondary">Confidence Score</span>
              <Badge variant={confidenceVariant}>{confidencePct}%</Badge>
            </div>
            <div className="h-2 w-full rounded-full bg-border overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  confidenceScore >= 0.7
                    ? 'bg-success'
                    : confidenceScore >= 0.4
                    ? 'bg-warning'
                    : 'bg-danger'
                }`}
                style={{ width: `${Math.min(Math.max(confidencePct, 5), 100)}%` }}
              />
            </div>
            <p className="mt-2 text-[11px] text-text-secondary">
              Score: <span className="font-semibold text-navy">{Number(confidenceScore).toFixed(4)}</span>
            </p>
          </div>

          {/* Key Properties Grid */}
          <div className="grid grid-cols-2 gap-3">
            {gradePct != null && (
              <div className="rounded-xl border border-border p-3">
                <div className="flex items-center gap-1.5 text-teal mb-1">
                  <Award size={14} />
                  <span className="text-[10px] font-medium uppercase tracking-wider text-text-secondary">
                    Est. Grade
                  </span>
                </div>
                <p className="text-sm font-bold text-navy">{gradePct}% Mn</p>
              </div>
            )}

            <div className="rounded-xl border border-border p-3">
              <div className="flex items-center gap-1.5 text-orange mb-1">
                <ShieldAlert size={14} />
                <span className="text-[10px] font-medium uppercase tracking-wider text-text-secondary">
                  Status
                </span>
              </div>
              <p className="text-sm font-bold text-navy">
                {confidenceScore >= 0.6 ? 'High Prospect' : 'Exploration'}
              </p>
            </div>
          </div>

          {/* Causal Reasoning Placeholder */}
          <div className="mt-4 rounded-xl border border-dashed border-border bg-bg p-3">
            <span className="text-xs font-semibold text-text-muted">Causal reasoning coming soon</span>
          </div>

          {/* Raw GeoJSON Properties */}
          <div className="mt-4">
            <h4 className="text-xs font-semibold text-navy mb-2">All Feature Attributes</h4>
            <div className="rounded-xl border border-border bg-bg p-3 space-y-1.5 text-xs">
              {Object.entries(zone).map(([key, val]) => (
                <div key={key} className="flex justify-between items-center py-0.5 border-b border-border/60 last:border-0">
                  <span className="text-text-secondary font-mono text-[11px]">{key}:</span>
                  <span className="font-medium text-navy text-[11px]">
                    {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-border mt-4">
        <button
          onClick={onClose}
          type="button"
          className="w-full py-2 px-4 rounded-xl border border-border bg-bg hover:bg-border/60 text-xs font-semibold text-navy transition-colors duration-150"
        >
          Deselect Zone
        </button>
      </div>
    </div>
  );
}
