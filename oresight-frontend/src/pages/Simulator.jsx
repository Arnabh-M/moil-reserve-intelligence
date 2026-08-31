import React, { useState } from 'react';
import toast from 'react-hot-toast';
import {
  ArrowDown, ArrowUp, Play, ChevronDown, Loader2, AlertCircle, RefreshCw, Zap,
} from 'lucide-react';
import { Card, Button, CausalGraph } from '../components';
import { sites } from '../data/mockData';
import { postSimulate, SITE_MAP, USE_MOCK } from '../api/client';

const scenarios = [
  { id: 'equipment_down', label: 'Equipment Down' },
  { id: 'delay_blasting', label: 'Delay Blasting' },
  { id: 'rainfall_event', label: 'Rainfall Event' },
];

function ComparisonCard({ title, before, after, unit = '', higherIsBetter = true, isFloat = false }) {
  const numBefore = parseFloat(before) || 0;
  const numAfter = parseFloat(after) || 0;
  const diff = numAfter - numBefore;
  const improved = higherIsBetter ? diff >= 0 : diff <= 0;
  const ArrowIcon = diff >= 0 ? ArrowUp : ArrowDown;

  const formattedDiff = isFloat ? Math.abs(diff).toFixed(2) : Math.abs(diff).toLocaleString();
  const sign = diff > 0 ? '+' : diff < 0 ? '-' : '';

  return (
    <Card className="hover:shadow-md transition-all duration-200">
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">{title}</p>
      <div className="flex items-center justify-between gap-3">
        {/* Before */}
        <div className="text-center flex-1">
          <p className="text-[10px] text-text-muted font-medium mb-1 uppercase tracking-wide">Before</p>
          <p className="text-lg font-bold text-text-primary">
            {typeof before === 'number' && isFloat ? before.toFixed(1) : before}
            <span className="text-xs font-normal text-text-muted ml-0.5">{unit}</span>
          </p>
        </div>

        {/* Direction Arrow */}
        <div
          className={`p-2 rounded-full shadow-xs transition-transform duration-200 ${
            improved ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'
          }`}
        >
          <ArrowIcon size={18} />
        </div>

        {/* After */}
        <div className="text-center flex-1">
          <p className="text-[10px] text-text-muted font-medium mb-1 uppercase tracking-wide">After</p>
          <p className={`text-lg font-bold ${improved ? 'text-success' : 'text-danger'}`}>
            {typeof after === 'number' && isFloat ? after.toFixed(1) : after}
            <span className="text-xs font-normal text-text-muted ml-0.5">{unit}</span>
          </p>
        </div>
      </div>
      <div className="text-center mt-2.5 pt-2 border-t border-border/60">
        <span
          className={`text-xs font-bold px-2 py-0.5 rounded-md ${
            improved ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'
          }`}
        >
          {sign}{formattedDiff}{unit} {improved ? 'impact' : 'degradation'}
        </span>
      </div>
    </Card>
  );
}

function LoadingCardSkeleton({ title }) {
  return (
    <Card className="animate-pulse">
      <div className="h-3.5 bg-border rounded w-28 mb-4" />
      <div className="flex items-center justify-between gap-3 py-2">
        <div className="space-y-1.5 flex-1 flex flex-col items-center">
          <div className="h-2.5 bg-border rounded w-10" />
          <div className="h-5 bg-border rounded w-14" />
        </div>
        <div className="w-8 h-8 rounded-full bg-border" />
        <div className="space-y-1.5 flex-1 flex flex-col items-center">
          <div className="h-2.5 bg-border rounded w-10" />
          <div className="h-5 bg-border rounded w-14" />
        </div>
      </div>
      <div className="h-3 bg-border rounded w-24 mx-auto mt-3" />
    </Card>
  );
}

export default function Simulator() {
  const [scenario, setScenario] = useState('equipment_down');
  const [site, setSite] = useState('balaghat');
  const [duration, setDuration] = useState(3);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);

    const siteIdNum = SITE_MAP[site] || 1;

    try {
      const response = await postSimulate({
        scenario_type: scenario,
        site_id: siteIdNum,
        duration_days: duration,
      });

      setResults(response);
      toast.success(
        <div>
          <p className="font-semibold text-xs">Simulation Complete</p>
          <p className="text-[11px] text-white/70 mt-0.5">
            Evaluated {duration}-day {scenarios.find(s => s.id === scenario)?.label} impact.
          </p>
        </div>,
        { id: 'sim-toast' }
      );
    } catch (err) {
      console.error('[Simulator] Error running simulation:', err);
      setError(err.message || 'Simulation execution failed');
      toast.error(
        <div>
          <p className="font-semibold text-xs">Simulation Error</p>
          <p className="text-[11px] text-white/70 mt-0.5">{err.message}</p>
        </div>,
        { id: 'sim-error' }
      );
    } finally {
      setLoading(false);
    }
  };

  const selectedScenarioLabel = scenarios.find(s => s.id === scenario)?.label || 'Disruption Scenario';
  const selectedSiteObj = sites.find(s => s.id === site);

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="page-title">What-If Simulator</h2>
          <p className="page-subtitle mb-0">
            Model disruption scenarios (POST /simulate) and preview propagation through the twin causal graph
          </p>
        </div>

        {USE_MOCK && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs font-bold shadow-xs">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            USE_MOCK = true (Simulated Engine)
          </div>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-6" style={{ alignItems: 'flex-start' }}>
        {/* Left Panel — Config Form */}
        <div className="w-full lg:w-[340px] shrink-0">
          <Card title="Scenario Configuration" subtitle="Set parameters to evaluate twin response">
            <div className="space-y-4 mt-2">
              {/* Scenario selector */}
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Scenario Type
                </label>
                <div className="relative">
                  <select
                    value={scenario}
                    disabled={loading}
                    onChange={e => setScenario(e.target.value)}
                    className="w-full appearance-none bg-bg border border-border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
                  >
                    {scenarios.map(s => (
                      <option key={s.id} value={s.id}>{s.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
                </div>
              </div>

              {/* Site selector */}
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Target Mine Site
                </label>
                <div className="relative">
                  <select
                    value={site}
                    disabled={loading}
                    onChange={e => setSite(e.target.value)}
                    className="w-full appearance-none bg-bg border border-border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
                  >
                    {sites.map(s => (
                      <option key={s.id} value={s.id}>{s.name} ({s.state})</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
                </div>
              </div>

              {/* Duration input */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold text-text-secondary">
                    Duration (days)
                  </label>
                  <span className="text-xs font-bold text-orange">{duration} Days</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={30}
                  step={1}
                  value={duration}
                  disabled={loading}
                  onChange={e => setDuration(parseInt(e.target.value, 10) || 1)}
                  className="w-full accent-orange cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-text-muted mt-1">
                  <span>1 day</span>
                  <span>15 days</span>
                  <span>30 days</span>
                </div>
              </div>

              {/* Run button */}
              <Button
                variant="primary"
                className="w-full"
                icon={loading ? Loader2 : Play}
                disabled={loading}
                onClick={handleRun}
              >
                {loading ? 'Simulating Impact...' : 'Run Simulation'}
              </Button>
            </div>
          </Card>
        </div>

        {/* Right Panel — Results & Causal Graph */}
        <div className="flex-1 min-w-0 w-full space-y-6">
          {/* Error Banner if any */}
          {error && (
            <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 text-danger flex items-start gap-3">
              <AlertCircle size={18} className="shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-xs font-bold">Simulation Failed</p>
                <p className="text-xs text-text-secondary mt-0.5">{error}</p>
                <button
                  onClick={handleRun}
                  className="mt-2 text-xs font-semibold underline hover:text-danger/80 flex items-center gap-1"
                >
                  <RefreshCw size={12} /> Try Again
                </button>
              </div>
            </div>
          )}

          {/* Loading Skeletons */}
          {loading && (
            <div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <LoadingCardSkeleton title="Reserve Confidence" />
                <LoadingCardSkeleton title="Production Forecast" />
                <LoadingCardSkeleton title="Risk Score" />
              </div>
              <Card title="Updated Causal Graph" subtitle="Evaluating graph impact paths...">
                <div className="h-72 bg-bg rounded-xl flex items-center justify-center animate-pulse">
                  <div className="flex items-center gap-2 text-xs text-text-muted">
                    <Loader2 size={16} className="animate-spin text-orange" />
                    Propagating {selectedScenarioLabel} through twin state...
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* Real Results */}
          {!loading && results && (
            <div className="space-y-6 animate-fade-in">
              {/* 3 Side-by-Side Comparison Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <ComparisonCard
                  title="Reserve Confidence"
                  before={Math.round((results.before.reserve_confidence || 0) * 100)}
                  after={Math.round((results.after.reserve_confidence || 0) * 100)}
                  unit="%"
                  higherIsBetter={true}
                  isFloat={false}
                />
                <ComparisonCard
                  title="Production Forecast"
                  before={Math.round(results.before.production_forecast_tonnes || 0)}
                  after={Math.round(results.after.production_forecast_tonnes || 0)}
                  unit=" t"
                  higherIsBetter={true}
                  isFloat={false}
                />
                <ComparisonCard
                  title="Risk Score"
                  before={results.before.risk_score || 0}
                  after={results.after.risk_score || 0}
                  unit=""
                  higherIsBetter={false}
                  isFloat={true}
                />
              </div>

              {/* React Flow Causal Graph Visualizer */}
              <Card
                title="Updated Causal Graph"
                subtitle={`Propagated impact for ${selectedScenarioLabel} across ${selectedSiteObj?.name || 'Site'}`}
                action={
                  <div className="flex items-center gap-1.5 text-xs text-text-muted">
                    <span className="w-2 h-2 rounded-full bg-orange animate-pulse" />
                    <span>{results.affected_graph_path?.length || 0} Nodes Affected</span>
                  </div>
                }
              >
                <CausalGraph
                  graph={results.updated_graph}
                  affectedPath={results.affected_graph_path}
                  height={320}
                  className="mt-2"
                />
              </Card>
            </div>
          )}

          {/* Initial Unsimulated State */}
          {!loading && !results && !error && (
            <Card>
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-16 h-16 rounded-2xl bg-orange/10 flex items-center justify-center mb-4 text-orange">
                  <Play size={28} />
                </div>
                <h3 className="text-base font-bold text-text-primary mb-1">Configure & Run a Scenario</h3>
                <p className="text-sm text-text-secondary max-w-md">
                  Select a disruption scenario, target mine site, and duration from the left panel,
                  then click <span className="font-semibold text-text-primary">"Run Simulation"</span> to calculate
                  twin state perturbation and visualize the causal graph.
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
