import React, { useState } from 'react';
import {
  ArrowDown, ArrowUp, Play, ChevronDown, Network,
} from 'lucide-react';
import { Card, Button } from '../components';
import { sites } from '../data/mockData';

const scenarios = [
  { id: 'equipment_down', label: 'Equipment Down' },
  { id: 'delay_blasting', label: 'Delay Blasting' },
  { id: 'rainfall_event', label: 'Rainfall Event' },
];

// Mock simulation results keyed by scenario + site
const mockResults = {
  equipment_down: {
    balaghat: { confBefore: 78, confAfter: 71, prodBefore: 1210, prodAfter: 985, riskBefore: 0.32, riskAfter: 0.61 },
    nagpur:   { confBefore: 74, confAfter: 68, prodBefore: 1030, prodAfter: 870, riskBefore: 0.28, riskAfter: 0.55 },
    bhandara: { confBefore: 69, confAfter: 64, prodBefore: 960, prodAfter: 810, riskBefore: 0.22, riskAfter: 0.48 },
  },
  delay_blasting: {
    balaghat: { confBefore: 78, confAfter: 73, prodBefore: 1210, prodAfter: 1050, riskBefore: 0.32, riskAfter: 0.51 },
    nagpur:   { confBefore: 74, confAfter: 70, prodBefore: 1030, prodAfter: 920, riskBefore: 0.28, riskAfter: 0.44 },
    bhandara: { confBefore: 69, confAfter: 65, prodBefore: 960, prodAfter: 855, riskBefore: 0.22, riskAfter: 0.39 },
  },
  rainfall_event: {
    balaghat: { confBefore: 78, confAfter: 70, prodBefore: 1210, prodAfter: 890, riskBefore: 0.32, riskAfter: 0.78 },
    nagpur:   { confBefore: 74, confAfter: 67, prodBefore: 1030, prodAfter: 790, riskBefore: 0.28, riskAfter: 0.65 },
    bhandara: { confBefore: 69, confAfter: 62, prodBefore: 960, prodAfter: 720, riskBefore: 0.22, riskAfter: 0.58 },
  },
};

function ComparisonCard({ title, before, after, unit, higherIsBetter = true }) {
  const diff = after - before;
  const improved = higherIsBetter ? diff >= 0 : diff <= 0;
  const ArrowIcon = diff >= 0 ? ArrowUp : ArrowDown;

  return (
    <Card>
      <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-3">{title}</p>
      <div className="flex items-center justify-between gap-3">
        {/* Before */}
        <div className="text-center flex-1">
          <p className="text-[10px] text-text-muted mb-1">Before</p>
          <p className="text-xl font-bold text-text-primary">{before}{unit}</p>
        </div>

        {/* Arrow */}
        <div className={`p-2 rounded-full ${improved ? 'bg-success/10' : 'bg-danger/10'}`}>
          <ArrowIcon size={18} className={improved ? 'text-success' : 'text-danger'} />
        </div>

        {/* After */}
        <div className="text-center flex-1">
          <p className="text-[10px] text-text-muted mb-1">After</p>
          <p className={`text-xl font-bold ${improved ? 'text-success' : 'text-danger'}`}>
            {after}{unit}
          </p>
        </div>
      </div>
      <div className="text-center mt-2">
        <span className={`text-xs font-semibold ${improved ? 'text-success' : 'text-danger'}`}>
          {diff >= 0 ? '+' : ''}{typeof before === 'number' && before < 1 ? diff.toFixed(2) : diff}{unit}
        </span>
      </div>
    </Card>
  );
}

export default function Simulator() {
  const [scenario, setScenario] = useState('equipment_down');
  const [site, setSite] = useState('balaghat');
  const [duration, setDuration] = useState(3);
  const [hasRun, setHasRun] = useState(false);
  const [results, setResults] = useState(null);

  const handleRun = () => {
    const res = mockResults[scenario]?.[site];
    if (res) {
      // Scale slightly by duration
      const scale = Math.min(duration / 3, 2);
      setResults({
        confBefore: res.confBefore,
        confAfter: Math.max(Math.round(res.confBefore - (res.confBefore - res.confAfter) * scale), 40),
        prodBefore: res.prodBefore,
        prodAfter: Math.max(Math.round(res.prodBefore - (res.prodBefore - res.prodAfter) * scale), 500),
        riskBefore: res.riskBefore,
        riskAfter: Math.min(parseFloat((res.riskBefore + (res.riskAfter - res.riskBefore) * scale).toFixed(2)), 0.99),
      });
      setHasRun(true);
    }
  };

  return (
    <div className="page-container">
      <h2 className="page-title">What-If Simulator</h2>
      <p className="page-subtitle">Model disruption scenarios and preview impacts on reserves, production, and risk</p>

      <div className="flex gap-6" style={{ alignItems: 'flex-start' }}>
        {/* Left Panel — Config Form */}
        <div className="shrink-0" style={{ width: 340 }}>
          <Card title="Scenario Configuration" subtitle="Set up simulation parameters">
            <div className="space-y-4 mt-1">
              {/* Scenario selector */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">
                  Scenario Type
                </label>
                <div className="relative">
                  <select
                    value={scenario}
                    onChange={e => setScenario(e.target.value)}
                    className="w-full appearance-none bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
                  >
                    {scenarios.map(s => (
                      <option key={s.id} value={s.id}>{s.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
                </div>
              </div>

              {/* Site selector */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">
                  Mine Site
                </label>
                <div className="relative">
                  <select
                    value={site}
                    onChange={e => setSite(e.target.value)}
                    className="w-full appearance-none bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
                  >
                    {sites.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
                </div>
              </div>

              {/* Duration input */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">
                  Duration (days)
                </label>
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={duration}
                  onChange={e => setDuration(parseInt(e.target.value) || 1)}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
                />
              </div>

              {/* Run button */}
              <Button
                variant="primary"
                className="w-full"
                icon={Play}
                onClick={handleRun}
              >
                Run Simulation
              </Button>
            </div>
          </Card>
        </div>

        {/* Right Panel — Results */}
        <div className="flex-1 min-w-0">
          {hasRun && results ? (
            <>
              {/* Comparison cards */}
              <div className="grid grid-cols-3 gap-4 mb-6 stagger-children">
                <ComparisonCard
                  title="Reserve Confidence"
                  before={results.confBefore}
                  after={results.confAfter}
                  unit="%"
                  higherIsBetter={true}
                />
                <ComparisonCard
                  title="Production Forecast"
                  before={results.prodBefore}
                  after={results.prodAfter}
                  unit=" t"
                  higherIsBetter={true}
                />
                <ComparisonCard
                  title="Risk Score"
                  before={results.riskBefore}
                  after={results.riskAfter}
                  unit=""
                  higherIsBetter={false}
                />
              </div>

              {/* Causal Graph Placeholder */}
              <Card title="Updated Causal Graph" subtitle="Graph visualization will render here after API integration">
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="w-14 h-14 rounded-2xl bg-teal/10 flex items-center justify-center mb-3">
                    <Network size={24} className="text-teal" />
                  </div>
                  <p className="text-sm font-medium text-text-secondary mb-1">
                    Causal Graph Visualization
                  </p>
                  <p className="text-xs text-text-muted max-w-sm">
                    This panel will display the Neo4j causal chain graph reflecting how the
                    simulated scenario propagates through equipment → blast plans → ore zones → risk events.
                  </p>
                  <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg border border-border text-[10px] text-text-muted">
                    <span className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse" />
                    Pending Day 3-4 API integration
                  </div>
                </div>
              </Card>
            </>
          ) : (
            /* Empty state before running */
            <Card>
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-16 h-16 rounded-2xl bg-orange/10 flex items-center justify-center mb-4">
                  <Play size={28} className="text-orange" />
                </div>
                <h3 className="text-base font-semibold text-text-primary mb-1">Configure & Run a Scenario</h3>
                <p className="text-sm text-text-secondary max-w-md">
                  Select a disruption scenario, target site, and duration from the left panel,
                  then click "Run Simulation" to preview the projected impact on reserves,
                  production, and risk.
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
