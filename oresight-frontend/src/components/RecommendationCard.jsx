import React, { useState } from 'react';
import toast from 'react-hot-toast';
import {
  Zap, ArrowRight, ArrowUp, ArrowDown, Loader2, ChevronUp, ChevronDown, CheckCircle2, X,
} from 'lucide-react';
import Badge from './Badge';
import Button from './Button';
import CausalGraph from './CausalGraph';
import { InlineError } from './ErrorState';
import { postSimulate, SITE_MAP } from '../api/client';

export default function RecommendationCard({
  trigger,
  risk_event_id = 1,
  site_id = 1,
  options = [],
}) {
  const [actioned, setActioned] = useState({});
  const [activeSimIdx, setActiveSimIdx] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState(null);
  const [simError, setSimError] = useState(null);

  // Map option type to simulate scenario
  const getScenarioType = (optType, triggerText = '') => {
    const lower = (optType + ' ' + triggerText).toLowerCase();
    if (lower.includes('rain') || lower.includes('weather') || lower.includes('flood')) {
      return 'rainfall_event';
    }
    if (lower.includes('blast') || lower.includes('reschedule') || lower.includes('delay')) {
      return 'delay_blasting';
    }
    return 'equipment_down';
  };

  const handleSimulate = async (opt, idx) => {
    if (activeSimIdx === idx && simResult) {
      // Toggle close if already open
      setActiveSimIdx(null);
      return;
    }

    setActiveSimIdx(idx);
    setSimLoading(true);
    setSimError(null);
    setSimResult(null);

    const scenario_type = getScenarioType(opt.type || opt.title, trigger);
    const numSiteId = SITE_MAP[site_id] || 1;

    try {
      const result = await postSimulate({
        scenario_type,
        site_id: numSiteId,
        duration_days: 3,
      });

      setSimResult(result);
      toast.success(
        <div>
          <p className="font-semibold text-xs">Simulated: {opt.title || opt.type}</p>
          <p className="text-[11px] text-white/70 mt-0.5">Projected impact calculated inline.</p>
        </div>,
        { id: `sim-inline-${idx}` }
      );
    } catch (err) {
      console.error('[RecommendationCard] Simulation failed:', err);
      setSimError(err.message || 'Simulation failed');
      toast.error('Simulation failed: ' + err.message);
    } finally {
      setSimLoading(false);
    }
  };

  const handleAction = (idx, opt) => {
    setActioned(prev => ({ ...prev, [idx]: true }));
    toast.success(
      <div>
        <p className="font-semibold text-xs">Mitigation Actioned</p>
        <p className="text-[11px] text-white/70 mt-0.5">
          "{opt.title || opt.type}" logged for mine control dispatch.
        </p>
      </div>,
      { id: `action-${idx}` }
    );
  };

  return (
    <div className="bg-bg-surface rounded-xl border border-border shadow-sm transition-all duration-200 hover:shadow-md overflow-hidden">
      {/* Trigger Description */}
      <div className="flex items-start gap-3 px-5 pt-4 pb-3 border-b border-border bg-bg-surface">
        <div className="p-2 rounded-lg bg-orange/10 text-orange shrink-0 mt-0.5 shadow-xs">
          <Zap size={16} />
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-text-primary leading-relaxed">{trigger}</p>
          {risk_event_id && (
            <span className="inline-block text-[10px] text-text-muted mt-0.5 font-medium">
              Source: Risk Event #{risk_event_id}
            </span>
          )}
        </div>
      </div>

      {/* 3 Option Sub-Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 p-4">
        {(options || []).map((opt, idx) => {
          const isCurrentSimulating = activeSimIdx === idx;
          const isActioned = actioned[idx];

          // Normalize title and impact text
          const title = opt.title || (opt.type === 'reschedule' ? 'Reschedule' : opt.type === 'redeploy' ? 'Redeploy' : 'Adjust Plan');
          const impactLabel = opt.impact || (opt.projected_impact !== undefined ? `${opt.projected_impact >= 0 ? '+' : ''}${opt.projected_impact}% projected impact` : '+15% recovery');
          const variant = opt.impactVariant || (opt.type === 'redeploy' ? 'operational' : opt.type === 'reschedule' ? 'warning' : 'info');

          return (
            <div
              key={idx}
              className={`flex flex-col justify-between rounded-xl border p-4 transition-all duration-200 ${
                isActioned
                  ? 'bg-success/5 border-success/30 shadow-xs'
                  : isCurrentSimulating
                    ? 'bg-orange/5 border-orange ring-1 ring-orange/30 shadow-xs'
                    : 'bg-bg border-border hover:border-teal/40 hover:-translate-y-0.5'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <h4 className="text-sm font-bold text-text-primary capitalize">{title}</h4>
                  {opt.confidence !== undefined && (
                    <span className="text-[10px] font-semibold text-text-muted bg-bg-surface px-1.5 py-0.5 rounded border border-border">
                      {Math.round(opt.confidence * 100)}% conf
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-secondary mb-3 leading-relaxed min-h-[36px]">
                  {opt.description}
                </p>
                <div className="mb-4">
                  <Badge variant={variant} dot>{impactLabel}</Badge>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2 border-t border-border/50">
                <Button
                  variant={isCurrentSimulating ? 'primary' : 'ghost'}
                  size="sm"
                  className="flex-1"
                  disabled={isActioned}
                  onClick={() => handleSimulate(opt, idx)}
                >
                  {isCurrentSimulating ? (
                    <span className="flex items-center gap-1">
                      <ChevronUp size={13} /> Close
                    </span>
                  ) : (
                    'Simulate'
                  )}
                </Button>
                <Button
                  variant={isActioned ? 'secondary' : 'primary'}
                  size="sm"
                  className="flex-1"
                  disabled={isActioned}
                  onClick={() => handleAction(idx, opt)}
                >
                  {isActioned ? '✓ Actioned' : 'Action'}
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Inline Expandable Simulation Result Panel */}
      {activeSimIdx !== null && (
        <div className="border-t border-border bg-bg/70 p-4 transition-all duration-300 animate-fade-in">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-border">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-orange animate-pulse" />
              <h5 className="text-xs font-bold text-text-primary uppercase tracking-wide">
                Simulation Projection: {options[activeSimIdx]?.title || options[activeSimIdx]?.type}
              </h5>
            </div>
            <button
              onClick={() => setActiveSimIdx(null)}
              className="text-text-muted hover:text-text-primary transition-colors p-1"
            >
              <X size={14} />
            </button>
          </div>

          {/* Loading state */}
          {simLoading && (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <Loader2 size={24} className="animate-spin text-orange mb-2" />
              <p className="text-xs text-text-muted">Evaluating twin scenario model...</p>
            </div>
          )}

          {/* Error state */}
          {simError && (
            <InlineError
              message={simError}
              onRetry={() => handleSimulate(options[activeSimIdx], activeSimIdx)}
            />
          )}

          {/* Result content */}
          {!simLoading && simResult && (
            <div className="space-y-4">
              {/* 3 Metric Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="bg-bg-surface p-3 rounded-lg border border-border text-center shadow-xs">
                  <p className="text-[10px] text-text-muted font-bold uppercase">Reserve Confidence</p>
                  <div className="flex items-center justify-center gap-2 mt-1">
                    <span className="text-sm font-bold text-text-primary">
                      {Math.round((simResult.before.reserve_confidence || 0) * 100)}%
                    </span>
                    <ArrowRight size={12} className="text-text-muted" />
                    <span className="text-sm font-bold text-success">
                      {Math.round((simResult.after.reserve_confidence || 0) * 100)}%
                    </span>
                  </div>
                </div>

                <div className="bg-bg-surface p-3 rounded-lg border border-border text-center shadow-xs">
                  <p className="text-[10px] text-text-muted font-bold uppercase">Production Forecast</p>
                  <div className="flex items-center justify-center gap-2 mt-1">
                    <span className="text-sm font-bold text-text-primary">
                      {Math.round(simResult.before.production_forecast_tonnes || 0)} t
                    </span>
                    <ArrowRight size={12} className="text-text-muted" />
                    <span className="text-sm font-bold text-orange">
                      {Math.round(simResult.after.production_forecast_tonnes || 0)} t
                    </span>
                  </div>
                </div>

                <div className="bg-bg-surface p-3 rounded-lg border border-border text-center shadow-xs">
                  <p className="text-[10px] text-text-muted font-bold uppercase">Risk Score</p>
                  <div className="flex items-center justify-center gap-2 mt-1">
                    <span className="text-sm font-bold text-text-primary">
                      {simResult.before.risk_score?.toFixed(2)}
                    </span>
                    <ArrowRight size={12} className="text-text-muted" />
                    <span className="text-sm font-bold text-danger">
                      {simResult.after.risk_score?.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Causal Graph rendering */}
              {simResult.updated_graph && (
                <div>
                  <p className="text-[11px] font-bold text-text-secondary mb-1.5">
                    Perturbed Causal Graph Propagation:
                  </p>
                  <CausalGraph
                    graph={simResult.updated_graph}
                    affectedPath={simResult.affected_graph_path}
                    height={220}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
