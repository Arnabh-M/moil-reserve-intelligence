import React, { useState, useEffect } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import { AlertCircle, RefreshCw, BarChart2 } from 'lucide-react';
import { getProduction } from '../api/client';
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
      <div className={`p-2 animate-pulse ${className}`}>
        <div className="flex items-center justify-between mb-4">
          <div className="h-3 bg-[var(--divider)] rounded w-36" />
          <div className="h-3 bg-[var(--divider)] rounded w-20" />
        </div>
        <div className="h-64 flex items-end p-2 gap-2">
          {Array.from({ length: 14 }).map((_, i) => (
            <div
              key={i}
              className="bg-[var(--divider)]/60 rounded-t flex-1"
              style={{ height: `${30 + ((i * 19) % 60)}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}>
        <div className="w-10 h-10 rounded-full bg-[var(--critical)]/10 text-[var(--critical)] flex items-center justify-center mb-3">
          <AlertCircle size={18} />
        </div>
        <h4 className="text-xs font-semibold text-[var(--text-primary)] mb-1">Failed to Load Production Chart</h4>
        <p className="text-xs text-[var(--text-muted)] max-w-sm mb-3">{error}</p>
        <Button variant="secondary" size="sm" onClick={fetchData}>
          <RefreshCw size={13} /> Retry
        </Button>
      </div>
    );
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}>
        <div className="w-10 h-10 rounded-full bg-[var(--bg-elevated)] text-[var(--text-muted)] flex items-center justify-center mb-3">
          <BarChart2 size={18} />
        </div>
        <h4 className="text-xs font-medium text-[var(--text-primary)] mb-1">No production data yet for this site</h4>
        <p className="text-xs text-[var(--text-muted)] max-w-sm">
          No daily records have been logged for the selected time period.
        </p>
      </div>
    );
  }

  // Prepare Plotly traces with clean smooth styling
  const dates = data.map(d => d.date);
  const actuals = data.map(d => d.actual_output);
  const targets = data.map(d => d.target_output);

  const traces = [
    {
      x: dates,
      y: actuals,
      type: 'scatter',
      mode: 'lines',
      name: 'Actual Output',
      fill: 'tozeroy',
      fillcolor: 'rgba(193, 87, 30, 0.06)',
      line: {
        color: '#C1571E',
        width: 2.25,
        shape: 'spline',
        smoothing: 0.85,
      },
      marker: {
        color: '#C1571E',
        size: 4,
      },
      hovertemplate: '<b>%{x}</b><br>Actual: <b>%{y:,.1f} t</b><extra></extra>',
    },
    {
      x: dates,
      y: targets,
      type: 'scatter',
      mode: 'lines',
      name: 'Target Output',
      line: {
        color: '#8A8578',
        width: 1.5,
        dash: 'dash',
      },
      hovertemplate: '<b>%{x}</b><br>Target: <b>%{y:,.1f} t</b><extra></extra>',
    },
  ];

  const layout = {
    autosize: true,
    height: 300,
    margin: { l: 40, r: 15, t: 15, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: 1.15,
      font: {
        family: 'Inter, sans-serif',
        size: 11,
        color: '#8A8578',
      },
    },
    xaxis: {
      type: 'category',
      showgrid: false,
      tickfont: {
        family: 'Inter, sans-serif',
        size: 10,
        color: '#8A8578',
      },
      tickangle: -25,
      showline: false,
      zeroline: false,
    },
    yaxis: {
      showgrid: true,
      gridcolor: 'rgba(235, 232, 225, 0.5)',
      gridwidth: 1,
      tickfont: {
        family: 'Inter, sans-serif',
        size: 10,
        color: '#8A8578',
      },
      showline: false,
      zeroline: false,
      tickformat: ',.0f',
      nticks: 5,
    },
    hoverlabel: {
      bgcolor: '#1A1A18',
      bordercolor: '#2A2724',
      font: {
        family: 'Inter, sans-serif',
        size: 11,
        color: '#F2EFE8',
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
