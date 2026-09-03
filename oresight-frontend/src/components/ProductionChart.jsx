import React, { useState, useEffect } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import { AlertCircle, RefreshCw, BarChart2 } from 'lucide-react';
import { getProduction, SITE_MAP } from '../api/client';
import Button from './Button';

const Plot = createPlotlyComponent(Plotly);

export default function ProductionChart({ site_id, days = 30, className = '' }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const records = await getProduction({ site_id, days });
      setData(records || []);
    } catch (err) {
      console.error('[ProductionChart] Failed to fetch production data:', err);
      setError(err.message || 'Unable to retrieve production records from server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [site_id, days]);

  // Loading skeleton state
  if (loading) {
    return (
      <div className={`p-4 animate-pulse ${className}`}>
        <div className="flex items-center justify-between mb-4">
          <div className="h-4 bg-border rounded w-44" />
          <div className="h-4 bg-border rounded w-24" />
        </div>
        <div className="h-72 bg-border/40 rounded-xl flex items-end p-4 gap-2">
          {Array.from({ length: 14 }).map((_, i) => (
            <div
              key={i}
              className="bg-border rounded-t flex-1"
              style={{ height: `${25 + ((i * 17) % 65)}%` }}
            />
          ))}
        </div>
        <div className="flex justify-center mt-3 gap-6">
          <div className="h-3 bg-border rounded w-20" />
          <div className="h-3 bg-border rounded w-20" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`flex flex-col items-center justify-center py-16 px-4 text-center ${className}`}>
        <div className="w-12 h-12 rounded-xl bg-danger/10 text-danger flex items-center justify-center mb-3">
          <AlertCircle size={22} />
        </div>
        <h4 className="text-sm font-bold text-text-primary mb-1">Failed to Load Production Chart</h4>
        <p className="text-xs text-text-muted max-w-sm mb-4">{error}</p>
        <Button variant="ghost" size="sm" onClick={fetchData}>
          <RefreshCw size={14} /> Retry
        </Button>
      </div>
    );
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center py-16 px-4 text-center ${className}`}>
        <div className="w-12 h-12 rounded-xl bg-bg border border-border text-text-muted flex items-center justify-center mb-3">
          <BarChart2 size={22} />
        </div>
        <h4 className="text-sm font-semibold text-text-primary mb-1">No production data yet for this site</h4>
        <p className="text-xs text-text-muted max-w-sm">
          No daily records have been logged for the selected time period.
        </p>
      </div>
    );
  }

  // Prepare Plotly traces
  const dates = data.map(d => d.date);
  const actuals = data.map(d => d.actual_output);
  const targets = data.map(d => d.target_output);

  const traces = [
    {
      x: dates,
      y: actuals,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Actual',
      line: {
        color: '#6B2737', // oxblood accent
        width: 2.5,
        shape: 'spline',
        smoothing: 0.8,
      },
      marker: {
        color: '#6B2737',
        size: 5,
      },
      hovertemplate: '<b>%{x}</b><br>Actual: <b>%{y:,.1f} t</b><extra></extra>',
    },
    {
      x: dates,
      y: targets,
      type: 'scatter',
      mode: 'lines',
      name: 'Target',
      line: {
        color: '#2C3E50', // slate navy accent
        width: 2,
        dash: 'dash',
      },
      hovertemplate: '<b>%{x}</b><br>Target: <b>%{y:,.1f} t</b><extra></extra>',
    },
  ];

  const layout = {
    autosize: true,
    height: 330,
    margin: { l: 45, r: 20, t: 20, b: 45 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0.5,
      xanchor: 'center',
      y: 1.15,
      font: {
        family: 'PT Serif, Georgia, serif',
        size: 11,
        color: '#6E695E',
      },
    },
    xaxis: {
      type: 'category',
      showgrid: false,
      tickfont: {
        family: 'IBM Plex Mono, monospace',
        size: 10,
        color: '#6E695E',
      },
      tickangle: -30,
      showline: true,
      linecolor: 'rgba(221,214,200,0.6)',
    },
    yaxis: {
      showgrid: true,
      gridcolor: 'rgba(221,214,200,0.6)',
      gridwidth: 1,
      tickfont: {
        family: 'IBM Plex Mono, monospace',
        size: 10,
        color: '#6E695E',
      },
      showline: false,
      zeroline: false,
      tickformat: ',.0f',
      nticks: 6,
    },
    hoverlabel: {
      bgcolor: '#1A1815',
      bordercolor: '#38352F',
      font: {
        family: 'PT Serif, Georgia, serif',
        size: 12,
        color: '#EDE8DD',
      },
    },
  };

  const config = {
    displayModeBar: false,
    responsive: true,
    showTips: false,
  };

  return (
    <div className={`w-full overflow-hidden ${className}`}>
      <Plot
        data={traces}
        layout={layout}
        config={config}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
      />
    </div>
  );
}
