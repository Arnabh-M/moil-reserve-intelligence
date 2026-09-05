import React, { useState } from 'react';
import toast from 'react-hot-toast';
import {
  ArrowDown, ArrowUp, Play, ChevronDown, Loader2, AlertCircle, RefreshCw,
} from 'lucide-react';
import { Card, Button, CausalGraph, SectionDivider } from '../components';
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
    <div className="bg-[var(--bg-elevated)]/50 rounded-xl p-5 border border-[var(--divider)]">
      <p className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">{title}</p>
      <div className="flex items-center justify-between gap-4">
        {/* Before */}
        <div className="text-left flex-1">
          <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-0.5">Pre-Sim</p>
          <p className="text-xl font-semibold text-[var(--text-primary)]">
            {typeof before === 'number' && isFloat ? before.toFixed(1) : before}
            <span className="text-xs font-normal text-[var(--text-muted)] ml-0.5">{unit}</span>
          </p>
        </div>

        {/* Direction Arrow */}
        <div
          className={`p-2 rounded-full transition-transform ${
            improved ? 'bg-[var(--success)]/12 text-[var(--success)]' : 'bg-[var(--critical)]/12 text-[var(--critical)]'
          }`}
        >
          <ArrowIcon size={16} strokeWidth={2.5} />
        </div>

        {/* After */}
        <div className="text-right flex-1">
          <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-0.5">Post-Sim</p>
          <p className={`text-xl font-semibold ${improved ? 'text-[var(--success)]' : 'text-[var(--critical)]'}`}>
            {typeof after === 'number' && isFloat ? after.toFixed(1) : after}
            <span className="text-xs font-normal text-[var(--text-muted)] ml-0.5">{unit}</span>
          </p>
        </div>
      </div>
      <div className="text-left mt-3 pt-2.5 border-t border-[var(--divider)]">
        <span
          className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
            improved ? 'bg-[var(--success)]/10 text-[var(--success)]' : 'bg-[var(--critical)]/10 text-[var(--critical)]'
          }`}
        >
          {sign}{formattedDiff}{unit} {improved ? 'impact' : 'degradation'}
        </span>
      </div>
    </div>
  );
}

function LoadingCardSkeleton({ title }) {
  return (
    <div className="bg-[var(--bg-elevated)]/50 rounded-xl p-5 border border-[var(--divider)] animate-pulse">
      <div className="h-3 bg-[var(--divider)] rounded w-24 mb-4" />
      <div className="flex items-center justify-between gap-3 py-2">
        <div className="space-y-1.5 flex-1 flex flex-col items-start">
          <div className="h-2 bg-[var(--divider)] rounded w-8" />
          <div className="h-5 bg-[var(--divider)] rounded w-12" />
        </div>
        <div className="w-8 h-8 rounded-full bg-[var(--divider)]" />
        <div className="space-y-1.5 flex-1 flex flex-col items-end">
          <div className="h-2 bg-[var(--divider)] rounded w-8" />
          <div className="h-5 bg-[var(--divider)] rounded w-12" />
        </div>
      </div>
      <div className="h-3 bg-[var(--divider)] rounded w-20 mt-3" />
    </div>
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
          <p className="text-[11px] opacity-80 mt-0.5">
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
          <p className="text-[11px] opacity-80 mt-0.5">{err.message}</p>
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
      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
        <div>
          <h1 className="page-title">Scenario Simulator</h1>
          <p className="page-subtitle">
            Model disruption scenarios (POST /simulate) and preview propagation through the twin causal graph
          </p>
        </div>

        {USE_MOCK && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[var(--accent-soft)] text-[var(--accent-primary)] text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)] animate-pulse" />
            <span>Simulated Engine Active</span>
          </div>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-8" style={{ alignItems: 'flex-start' }}>
        {/* Left Panel — Config Form */}
        <div className="w-full lg:w-[320px] shrink-0">
          <div className="bg-[var(--bg-elevated)]/50 rounded-xl p-5 border border-[var(--divider)]">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Scenario Parameters</h3>
            <p className="text-xs text-[var(--text-muted)] mb-4">Set parameters to evaluate twin perturbation</p>

            <div className="space-y-4">
              {/* Scenario selector */}
              <div>
                <label className="block text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1.5">
                  Scenario Type
                </label>
                <div className="relative">
                  <select
                    value={scenario}
                    disabled={loading}
                    onChange={e => setScenario(e.target.value)}
                    className="w-full appearance-none bg-[var(--bg-primary)] border border-[var(--divider)] rounded-lg px-3.5 py-2 text-xs text-[var(--text-primary)] outline-none cursor-pointer"
                  >
                    {scenarios.map(s => (
                      <option key={s.id} value={s.id}>{s.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
                </div>
              </div>

              {/* Site selector */}
              <div>
                <label className="block text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1.5">
                  Target Mine Site
                </label>
                <div className="relative">
                  <select
                    value={site}
                    disabled={loading}
                    onChange={e => setSite(e.target.value)}
                    className="w-full appearance-none bg-[var(--bg-primary)] border border-[var(--divider)] rounded-lg px-3.5 py-2 text-xs text-[var(--text-primary)] outline-none cursor-pointer"
                  >
                    {sites.map(s => (
                      <option key={s.id} value={s.id}>{s.name} ({s.state})</option>
                    ))}
                  </select>
                  <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
                </div>
              </div>

              {/* Duration input */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    Duration
                  </label>
                  <span className="text-xs font-semibold text-[var(--accent-primary)]">{duration} Days</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={30}
                  step={1}
                  value={duration}
                  disabled={loading}
                  onChange={e => setDuration(parseInt(e.target.value, 10) || 1)}
                  className="w-full accent-[var(--accent-primary)] cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-[var(--text-muted)] mt-1 font-mono">
                  <span>1d</span>
                  <span>15d</span>
                  <span>30d</span>
                </div>
              </div>

              {/* Run button */}
              <Button
                variant="primary"
                className="w-full mt-2"
                icon={loading ? Loader2 : Play}
                disabled={loading}
                onClick={handleRun}
              >
                {loading ? 'Simulating Impact...' : 'Run Simulation'}
              </Button>
            </div>
          </div>
        </div>

        {/* Right Panel — Results & Causal Graph */}
        <div className="flex-1 min-w-0 w-full space-y-6">
          {error && (
            <div className="p-4 rounded-xl bg-[var(--critical)]/10 text-[var(--critical)] flex items-start gap-3">
              <AlertCircle size={18} className="shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-xs font-semibold">Simulation Failed</p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">{error}</p>
                <button
                  type="button"
                  onClick={handleRun}
                  className="mt-2 text-xs font-semibold underline flex items-center gap-1 cursor-pointer"
                >
                  <RefreshCw size={12} /> Try Again
                </button>
              </div>
            </div>
          )}

          {/* Loading Skeletons */}
          {loading && (
            <div>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
                <LoadingCardSkeleton title="Reserve Confidence" />
                <LoadingCardSkeleton title="Production Forecast" />
                <LoadingCardSkeleton title="Risk Score" />
              </div>
              <div className="h-72 bg-[var(--bg-elevated)]/40 rounded-xl flex items-center justify-center animate-pulse">
                <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                  <Loader2 size={16} className="animate-spin text-[var(--accent-primary)]" />
                  <span>Propagating {selectedScenarioLabel} through twin graph...</span>
                </div>
              </div>
            </div>
          )}

          {/* Real Results */}
          {!loading && results && (
            <div className="space-y-6 animate-fade-in">
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
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

              {/* Perturbed Causal Graph & AI Recommendation Output */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)]">Perturbed Causal Graph</h3>
                    <p className="text-xs text-[var(--text-muted)]">
                      Propagated impact for {selectedScenarioLabel} across {selectedSiteObj?.name || 'Site'}
                    </p>
                  </div>
                  <span className="text-xs text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] font-mono font-semibold">
                    {results.affected_graph_path?.length || 0} Nodes Impacted
                  </span>
                </div>

                <CausalGraph
                  graph={results.updated_graph}
                  affectedPath={results.affected_graph_path}
                  height={300}
                />
              </div>

              {/* Visually Dominant AI Recommendation Output */}
              <Card title="Simulated Mitigation Recommendation" subtitle="Optimized dispatch & schedule adjustments to offset disruption">
                <div className="p-4 rounded-lg bg-[var(--accent-soft)] border border-[var(--border)] space-y-3 font-body text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] text-sm">
                      Recommended Action: Shift Ore Haulage to Pit 3
                    </span>
                    <span className="font-mono text-[11px] text-[var(--success)] font-semibold">+18.5% Recovery</span>
                  </div>
                  <p className="text-[var(--text-primary)] leading-relaxed">
                    By redeploying 2 CAT-777 dump trucks to secondary crushing plant B, estimated 3-day production deficit will be reduced from -240 tonnes to -45 tonnes.
                  </p>
                </div>
              </Card>
            </div>
          )}

          {/* Initial Unsimulated State */}
          {!loading && !results && !error && (
            <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl bg-[var(--bg-surface)] border border-[var(--border)]">
              <div className="w-12 h-12 rounded-lg bg-[var(--accent-soft)] flex items-center justify-center mb-3 text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]">
                <Play size={20} className="ml-0.5" />
              </div>
              <h3 className="text-sm font-heading font-semibold text-[var(--text-primary)] mb-1">
                Step 1: Configure &amp; Run Disruption Simulation
              </h3>
              <p className="text-xs text-[var(--text-muted)] max-w-sm font-body">
                Select scenario type, target mine site, and duration from the left parameters panel to evaluate twin state perturbation and generate mitigation actions.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


