import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Layers } from 'lucide-react';
import { CONFIDENCE_COLOR_RAMP, STRUCTURAL_LINE_COLORS, SPECTRAL_LAYER_CONFIG, DRONE_LAYER_CONFIG } from '../../lib/map';

export default function ConfidenceLegend({
  visible,
  prospectivityVisible = false,
  lineamentVisible = false,
  spectralVisible = false,
  droneVisible = false,
  ndviVisible = false,
}) {
  const [collapsed, setCollapsed] = useState(true);

  const showProspectivity = prospectivityVisible || (visible && !lineamentVisible && !spectralVisible && !droneVisible && !ndviVisible);

  const activeLayersCount = [
    showProspectivity,
    lineamentVisible,
    spectralVisible,
    droneVisible,
    ndviVisible,
  ].filter(Boolean).length;

  if (activeLayersCount === 0) return null;

  return (
    <aside
      aria-label="Map Legend"
      className="pointer-events-auto w-64 max-w-full rounded-xl border border-[var(--divider)] bg-[var(--bg-elevated)]/90 backdrop-blur-md shadow-md transition-all duration-200"
    >
      {/* Legend Header */}
      <div
        onClick={() => setCollapsed(!collapsed)}
        className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-[var(--bg-primary)]/50 transition-colors rounded-t-xl"
      >
        <div className="flex items-center gap-2">
          <Layers size={14} className="text-[var(--accent-primary)]" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-primary)]">
            Map Legend
          </h2>
          <span className="rounded-full bg-[var(--accent-soft)] px-1.5 py-0.2 text-[10px] font-semibold text-[var(--accent-primary)]">
            {activeLayersCount}
          </span>
        </div>
        <button
          type="button"
          aria-label={collapsed ? 'Expand Legend' : 'Collapse Legend'}
          className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
        >
          {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Collapsible Content */}
      {!collapsed && (
        <div className="border-t border-[var(--divider)] p-4 space-y-4 text-xs">
          {/* 1. Reserve Confidence / Prospectivity */}
          {showProspectivity && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-[var(--text-primary)] text-[11px]">Reserve Confidence</span>
                <span className="text-[10px] text-[var(--text-muted)]">Kriging Surface</span>
              </div>
              <div
                className="h-2 w-full rounded-full shadow-inner mb-1"
                style={{
                  background: `linear-gradient(to right, ${CONFIDENCE_COLOR_RAMP.low}, ${CONFIDENCE_COLOR_RAMP.mid}, ${CONFIDENCE_COLOR_RAMP.high})`,
                }}
              />
              <div className="flex justify-between text-[10px] font-medium text-[var(--text-muted)]">
                <span>0.0 (Low)</span>
                <span>0.5 (Mid)</span>
                <span>1.0 (High)</span>
              </div>
            </div>
          )}

          {/* 2. Structural Lineaments */}
          {lineamentVisible && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-[var(--text-primary)] text-[11px]">Structural Lineaments</span>
                <span className="text-[10px] text-[var(--text-muted)]">Vector Faults</span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 text-[10px]">
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-3.5 rounded-full"
                    style={{ backgroundColor: STRUCTURAL_LINE_COLORS.fault }}
                  />
                  <span className="text-[var(--text-muted)]">Fault</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-3.5 rounded-full"
                    style={{ backgroundColor: STRUCTURAL_LINE_COLORS.shear_zone }}
                  />
                  <span className="text-[var(--text-muted)]">Shear</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-3.5 rounded-full"
                    style={{ backgroundColor: STRUCTURAL_LINE_COLORS.fold_axis }}
                  />
                  <span className="text-[var(--text-muted)]">Fold Axis</span>
                </div>
              </div>
            </div>
          )}

          {/* 3. Spectral Alteration */}
          {spectralVisible && (
            <div className="flex items-center justify-between pt-0.5">
              <div>
                <span className="font-semibold text-[var(--text-primary)] text-[11px] block">Spectral Alteration</span>
                <span className="text-[10px] text-[var(--text-muted)]">ASTER / Landsat · {SPECTRAL_LAYER_CONFIG.date}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="h-2.5 w-8 rounded-full bg-gradient-to-r from-amber-600 via-orange-500 to-red-600 border border-[var(--divider)]" />
              </div>
            </div>
          )}

          {/* 4. Drone DSM */}
          {droneVisible && (
            <div className="flex items-center justify-between pt-0.5">
              <div>
                <span className="font-semibold text-[var(--text-primary)] text-[11px] block">Drone Orthomosaic</span>
                <span className="text-[10px] text-[var(--text-muted)]">UAV RGB · {DRONE_LAYER_CONFIG.date}</span>
              </div>
              <span className="text-[10px] font-mono font-medium text-[var(--accent-primary)] bg-[var(--accent-soft)] px-1.5 py-0.5 rounded">
                10cm/px
              </span>
            </div>
          )}

          {/* 5. NDVI Time-Series */}
          {ndviVisible && (
            <div className="flex items-center justify-between pt-0.5">
              <div>
                <span className="font-semibold text-[var(--text-primary)] text-[11px] block">NDVI Vegetation</span>
                <span className="text-[10px] text-[var(--text-muted)]">Sentinel-2 4-Week Series</span>
              </div>
              <span className="h-2.5 w-8 rounded-full bg-gradient-to-r from-amber-200 via-emerald-400 to-emerald-800 border border-[var(--divider)]" />
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
