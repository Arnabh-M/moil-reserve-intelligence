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

  // Backward-compatibility: if `visible` prop is explicitly provided, treat it as prospectivityVisible
  const showProspectivity = prospectivityVisible || (visible && !lineamentVisible && !spectralVisible && !droneVisible && !ndviVisible);

  // Count active layers that have legend representations
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
      className="pointer-events-auto w-64 max-w-full rounded-[3px] border border-border bg-bg-surface shadow-xs transition-all duration-200"
    >
      {/* Legend Header */}
      <div
        onClick={() => setCollapsed(!collapsed)}
        className="flex cursor-pointer items-center justify-between px-3.5 py-2.5 hover:bg-bg/50 transition-colors rounded-t-[3px]"
      >
        <div className="flex items-center gap-2">
          <Layers size={14} className="text-teal" />
          <h2 className="font-heading text-xs font-bold uppercase tracking-wider text-navy">
            Map Legend
          </h2>
          <span className="rounded-full bg-teal/10 px-1.5 py-0.2 text-[10px] font-semibold text-teal">
            {activeLayersCount}
          </span>
        </div>
        <button
          type="button"
          aria-label={collapsed ? 'Expand Legend' : 'Collapse Legend'}
          className="text-slate-400 hover:text-navy transition-colors"
        >
          {collapsed ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>

      {/* Collapsible Content */}
      {!collapsed && (
        <div className="border-t border-border/70 p-3.5 space-y-3.5 text-xs">
          {/* 1. Reserve Confidence / Prospectivity */}
          {showProspectivity && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-navy text-[11px]">Reserve Confidence</span>
                <span className="text-[10px] text-slate-500 font-medium">Kriging Surface</span>
              </div>
              <div
                className="h-2.5 w-full rounded-md shadow-inner mb-1"
                style={{
                  background: `linear-gradient(to right, ${CONFIDENCE_COLOR_RAMP.low}, ${CONFIDENCE_COLOR_RAMP.mid}, ${CONFIDENCE_COLOR_RAMP.high})`,
                }}
              />
              <div className="flex justify-between text-[10px] font-semibold text-slate-500">
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
                <span className="font-semibold text-navy text-[11px]">Structural Lineament</span>
                <span className="text-[10px] text-slate-500 font-medium">Vector Faults</span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 text-[10px]">
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-4 rounded-full"
                    style={{ backgroundColor: STRUCTURAL_LINE_COLORS.fault }}
                  />
                  <span className="text-slate-700 font-medium">Fault</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-4 rounded-full"
                    style={{ backgroundColor: STRUCTURAL_LINE_COLORS.shear_zone }}
                  />
                  <span className="text-slate-700 font-medium">Shear</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-4 rounded-full"
                    style={{ backgroundColor: STRUCTURAL_LINE_COLORS.fold_axis }}
                  />
                  <span className="text-slate-700 font-medium">Fold Axis</span>
                </div>
              </div>
            </div>
          )}

          {/* 3. Spectral Alteration */}
          {spectralVisible && (
            <div className="flex items-center justify-between pt-0.5">
              <div>
                <span className="font-semibold text-navy text-[11px] block">Spectral Alteration</span>
                <span className="text-[10px] text-slate-500">ASTER / Landsat · {SPECTRAL_LAYER_CONFIG.date}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="h-3 w-8 rounded bg-gradient-to-r from-amber-600 via-orange-500 to-red-600 border border-border" />
              </div>
            </div>
          )}

          {/* 4. Drone DSM */}
          {droneVisible && (
            <div className="flex items-center justify-between pt-0.5">
              <div>
                <span className="font-semibold text-navy text-[11px] block">Drone Orthomosaic</span>
                <span className="text-[10px] text-slate-500">UAV RGB · {DRONE_LAYER_CONFIG.date}</span>
              </div>
              <span className="text-[10px] font-mono font-medium text-teal bg-teal/10 px-1.5 py-0.5 rounded">
                10cm/px
              </span>
            </div>
          )}

          {/* 5. NDVI Time-Series */}
          {ndviVisible && (
            <div className="flex items-center justify-between pt-0.5">
              <div>
                <span className="font-semibold text-navy text-[11px] block">NDVI Vegetation</span>
                <span className="text-[10px] text-slate-500">Sentinel-2 4-Week Series</span>
              </div>
              <span className="h-3 w-8 rounded bg-gradient-to-r from-amber-200 via-emerald-400 to-emerald-800 border border-border" />
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
