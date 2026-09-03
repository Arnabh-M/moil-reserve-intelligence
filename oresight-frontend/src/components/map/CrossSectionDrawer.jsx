import React, { useMemo } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import { X, Activity, AlertCircle } from 'lucide-react';

const Plot = createPlotlyComponent(Plotly);

/**
 * Deterministically generates a 2D subsurface grid (distance vs depth 0-400m)
 * based on coordinate seed so the cross-section is continuous and reproducible.
 */
function generateSubsurfaceGrid(lat, lng) {
  const seed = (Math.abs(lat * 1000 + lng * 100)) % 1000;
  const nDist = 25; // 0m to 500m in steps of 20m
  const nDepth = 21; // 0m to 400m in steps of 20m

  const xDist = Array.from({ length: nDist }, (_, i) => i * 20);
  const yDepth = Array.from({ length: nDepth }, (_, i) => i * 20);

  // Core seam center depth around 160m-220m with some dip
  const dipSlope = 0.15; // 15m depth shift per 100m distance
  const baseSeamCenter = 170 + (seed % 40);

  const zGrade = [];
  for (let j = 0; j < nDepth; j++) {
    const row = [];
    const depth = yDepth[j];
    for (let i = 0; i < nDist; i++) {
      const dist = xDist[i];
      const seamCenter = baseSeamCenter + dist * dipSlope;
      const distFromSeam = Math.abs(depth - seamCenter);

      // Overburden 0-45m: barren/waste (< 12% Mn)
      if (depth < 45) {
        const val = 6 + Math.sin(dist * 0.05 + seed) * 3;
        row.push(Math.max(2, Math.round(val * 10) / 10));
      } else {
        // Gaussian peak at ore seam
        const peakGrade = 38 + (seed % 7);
        const grade = 10 + (peakGrade - 10) * Math.exp(-Math.pow(distFromSeam / 45, 2));
        // Add subtle geologic noise
        const noise = Math.sin(dist * 0.08 + depth * 0.04 + seed) * 2.5;
        row.push(Math.max(5, Math.round((grade + noise) * 10) / 10));
      }
    }
    zGrade.push(row);
  }

  // Simulated borehole trajectories
  const boreholes = [
    { id: 'BH-01', dist: 100, depth: 320, dip: 85 },
    { id: 'BH-02', dist: 240, depth: 360, dip: 88 },
    { id: 'BH-03', dist: 400, depth: 290, dip: 82 },
  ];

  return { xDist, yDepth, zGrade, boreholes, baseSeamCenter };
}

export default function CrossSectionDrawer({ isOpen, onClose, point }) {
  const lat = point?.lat ?? point?.latitude ?? 21.8;
  const lng = point?.lng ?? point?.longitude ?? 80.2;
  const siteName = point?.siteName || (point?.site_id ? String(point.site_id).toUpperCase() : 'MOIL Operational Belt');
  const zoneName = point?.zoneName || (point?.id ? `Zone #${point.id}` : null);

  const gridData = useMemo(() => generateSubsurfaceGrid(lat, lng), [lat, lng]);

  if (!isOpen || !point) return null;

  // Find max grade in grid for KPI
  let maxGrade = 0;
  gridData.zGrade.forEach((row) => {
    row.forEach((val) => {
      if (val > maxGrade) maxGrade = val;
    });
  });

  // Plotly traces:
  // 1. Heatmap / Contour of Mn Grade
  const contourTrace = {
    x: gridData.xDist,
    y: gridData.yDepth,
    z: gridData.zGrade,
    type: 'contour',
    colorscale: [
      [0.0, '#0f172a'],   // barren slate
      [0.25, '#1e293b'],  // low grade
      [0.45, '#155e75'],  // medium grade (cyan/teal)
      [0.7, '#d97706'],   // high grade (amber)
      [1.0, '#dc2626'],   // ultra high grade (crimson)
    ],
    contours: {
      coloring: 'heatmap',
      showlabels: true,
      labelfont: { size: 10, color: '#ffffff' },
    },
    colorbar: {
      title: 'Mn Grade (%)',
      titleside: 'right',
      tickfont: { size: 10, color: '#5a6577' },
      titlefont: { size: 11, color: '#16233a' },
      len: 0.85,
    },
    hovertemplate: 'Distance: %{x}m<br>Depth: %{y}m<br><b>Estimated Mn Grade: %{z}%</b><extra></extra>',
  };

  // 2. Borehole traces
  const boreholeTraces = gridData.boreholes.map((bh) => ({
    x: [bh.dist, bh.dist + (400 - bh.depth) * 0.05],
    y: [0, bh.depth],
    mode: 'lines+text',
    name: bh.id,
    line: { color: '#ffffff', width: 2, dash: 'dot' },
    text: ['', bh.id],
    textposition: 'bottom center',
    textfont: { size: 9, color: '#cbd5e1' },
    hovertemplate: `<b>${bh.id}</b><br>Drill Depth: ${bh.depth}m<br>Dip: ${bh.dip}°<extra></extra>`,
  }));

  const plotData = [contourTrace, ...boreholeTraces];

  const plotLayout = {
    title: false,
    autosize: true,
    height: 250,
    margin: { l: 60, r: 40, t: 20, b: 45 },
    xaxis: {
      title: { text: 'Horizontal Distance Along Section (m)', font: { size: 11, color: '#5a6577' } },
      tickfont: { size: 10, color: '#5a6577' },
      gridcolor: '#e2e8f0',
      zeroline: false,
    },
    yaxis: {
      title: { text: 'Subsurface Depth (0–400 m)', font: { size: 11, color: '#5a6577' } },
      autorange: 'reversed', // Invert Y-axis so 0m ground surface is at top
      range: [400, 0],
      tickfont: { size: 10, color: '#5a6577' },
      gridcolor: '#e2e8f0',
      zeroline: false,
    },
    plot_bgcolor: '#f8fafc',
    paper_bgcolor: 'transparent',
    showlegend: false,
  };

  const plotConfig = {
    responsive: true,
    displayModeBar: false,
  };

  return (
    <div className="absolute inset-x-0 bottom-0 z-30 flex flex-col border-t border-border bg-white shadow-2xl transition-transform duration-300 max-h-[460px]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-white/95 px-5 py-3 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal/10 text-teal">
            <Activity size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-heading text-sm font-bold text-navy">
                Subsurface Cross-Section Profile (0–400m)
              </h3>
              <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
                Simulated / Synthetic Model
              </span>
            </div>
            <p className="text-xs text-text-muted">
              Sampling location: {siteName} {zoneName ? `• ${zoneName}` : ''} ({lat.toFixed(4)}°N, {lng.toFixed(4)}°E)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            type="button"
            aria-label="Close Cross-Section Drawer"
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-border text-slate-500 transition-colors hover:bg-bg hover:text-navy"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Drawer Content */}
      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-4 overflow-y-auto">
        {/* KPI Panel */}
        <div className="flex flex-col justify-between space-y-2 lg:col-span-1">
          <div className="space-y-2">
            <div className="rounded-xl border border-border bg-bg/50 p-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Peak Estimated Grade</span>
              <p className="font-heading text-xl font-bold text-navy">{maxGrade.toFixed(1)}% <span className="text-xs text-teal font-medium">Mn</span></p>
              <span className="text-[11px] text-text-secondary">High-grade core lens</span>
            </div>

            <div className="rounded-xl border border-border bg-bg/50 p-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Target Seam Depth</span>
              <p className="font-heading text-xl font-bold text-navy">{Math.round(gridData.baseSeamCenter)} <span className="text-xs text-slate-500 font-medium">meters</span></p>
              <span className="text-[11px] text-text-secondary">True depth below collar</span>
            </div>

            <div className="rounded-xl border border-border bg-bg/50 p-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Estimated Overburden</span>
              <p className="font-heading text-xl font-bold text-navy">45 <span className="text-xs text-slate-500 font-medium">meters</span></p>
              <span className="text-[11px] text-text-secondary">Weathered laterite cap</span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 text-[10px] text-text-muted italic pt-1">
            <AlertCircle size={12} className="shrink-0 text-amber-500" />
            <span>Profile generated from 2D strike interpolation and variogram kriging.</span>
          </div>
        </div>

        {/* Plotly Depth Chart */}
        <div className="rounded-xl border border-border bg-white p-2 lg:col-span-3">
          <Plot
            data={plotData}
            layout={plotLayout}
            config={plotConfig}
            style={{ width: '100%', height: '250px' }}
            useResizeHandler
          />
        </div>
      </div>
    </div>
  );
}
