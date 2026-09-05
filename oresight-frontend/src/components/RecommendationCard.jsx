import React, { useState } from 'react';
import toast from 'react-hot-toast';
import {
  Zap, ArrowRight, Loader2, ChevronUp, X,
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
          <p className="text-[11px] opacity-80 mt-0.5">Projected impact calculated inline.</p>
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
        <p className="text-[11px] opacity-80 mt-0.5">
          "{opt.title || opt.type}" logged for mine control dispatch.
        </p>
      </div>,
      { id: `action-${idx}` }
    );
  };

  return (
    <div className="bg-[var(--bg-elevated)]/50 rounded-xl border border-[var(--divider)] overflow-hidden">
      {/* Trigger Description */}
      <div className="flex items-start gap-3 px-5 py-4 border-b border-[var(--divider)]">
        <div className="p-1.5 rounded-md bg-[var(--accent-soft)] text-[var(--accent-primary)] shrink-0 mt-0.5">
          <Zap size={15} />
        </div>
        <div className="flex-1">
          <p className="text-xs font-semibold text-[var(--text-primary)] leading-relaxed">{trigger}</p>
          {risk_event_id && (
            <span className="inline-block text-[11px] text-[var(--text-muted)] mt-0.5">
              Source: Risk Event #{risk_event_id}
            </span>
          )}
        </div>
      </div>

      {/* 3 Option Sub-Blocks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-5">
        {(options || []).map((opt, idx) => {
          const isCurrentSimulating = activeSimIdx === idx;
          const isActioned = actioned[idx];

          const title = opt.title || (opt.type === 'reschedule' ? 'Reschedule' : opt.type === 'redeploy' ? 'Redeploy' : 'Adjust Plan');
          const impactLabel = opt.impact || (opt.projected_impact !== undefined ? `${opt.projected_impact >= 0 ? '+' : ''}${opt.projected_impact}% projected impact` : '+15% recovery');
          const variant = opt.impactVariant || (opt.type === 'redeploy' ? 'operational' : opt.type === 'reschedule' ? 'warning' : 'info');

          return (
            <div
              key={idx}
              className={`flex flex-col justify-between rounded-lg p-4 transition-colors ${
                isActioned
                  ? 'bg-[var(--success)]/8 border border-[var(--success)]/30'
                  : isCurrentSimulating
                    ? 'bg-[var(--accent-soft)]/50 border border-[var(--accent-primary)]'
                    : 'bg-[var(--bg-primary)] border border-[var(--divider)]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <h4 className="text-xs font-semibold text-[var(--text-primary)] capitalize">{title}</h4>
                  {opt.confidence !== undefined && (
                    <span className="text-[10px] text-[var(--text-muted)] font-mono">
                      {Math.round(opt.confidence * 100)}% conf
                    </span>
                  )}
                </div>
                <p className="text-xs text-[var(--text-muted)] mb-3 leading-relaxed min-h-[36px]">
                  {opt.description}
                </p>
                <div className="mb-4">
                  <Badge variant={variant} dot>{impactLabel}</Badge>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2 border-t border-[var(--divider)]">
                <Button
                  variant={isCurrentSimulating ? 'primary' : 'ghost'}
                  size="sm"
                  className="flex-1"
                  disabled={isActioned}
                  onClick={() => handleSimulate(opt, idx)}
                >
                  {isCurrentSimulating ? (
                    <span className="flex items-center gap-1">
                      <ChevronUp size={12} /> Close
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
        <div className="border-t border-[var(--divider)] bg-[var(--bg-primary)] p-5 animate-fade-in">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-[var(--divider)]">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />
              <h5 className="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">
                Projected Impact: {options[activeSimIdx]?.title || options[activeSimIdx]?.type}
              </h5>
            </div>
            <button
              type="button"
              onClick={() => setActiveSimIdx(null)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1 cursor-pointer"
            >
              <X size={14} />
            </button>
          </div>

          {simLoading && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Loader2 size={20} className="animate-spin text-[var(--accent-primary)] mb-2" />
              <p className="text-xs text-[var(--text-muted)]">Evaluating twin scenario model...</p>
            </div>
          )}

          {simError && (
            <InlineError
              message={simError}
              onRetry={() => handleSimulate(options[activeSimIdx], activeSimIdx)}
            />
          )}

          {!simLoading && simResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="bg-[var(--bg-elevated)]/60 p-3 rounded-lg border border-[var(--divider)] text-left">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">Reserve Confidence</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-sm font-semibold text-[var(--text-primary)]">
                      {Math.round((simResult.before.reserve_confidence || 0) * 100)}%
                    </span>
                    <ArrowRight size={12} className="text-[var(--text-muted)]" />
                    <span className="text-sm font-semibold text-[var(--success)]">
                      {Math.round((simResult.after.reserve_confidence || 0) * 100)}%
                    </span>
                  </div>
                </div>

                <div className="bg-[var(--bg-elevated)]/60 p-3 rounded-lg border border-[var(--divider)] text-left">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">Production Forecast</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-sm font-semibold text-[var(--text-primary)]">
                      {Math.round(simResult.before.production_forecast_tonnes || 0)} t
                    </span>
                    <ArrowRight size={12} className="text-[var(--text-muted)]" />
                    <span className="text-sm font-semibold text-[var(--accent-primary)]">
                      {Math.round(simResult.after.production_forecast_tonnes || 0)} t
                    </span>
                  </div>
                </div>

                <div className="bg-[var(--bg-elevated)]/60 p-3 rounded-lg border border-[var(--divider)] text-left">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">Risk Score</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-sm font-semibold text-[var(--text-primary)]">
                      {simResult.before.risk_score?.toFixed(2)}
                    </span>
                    <ArrowRight size={12} className="text-[var(--text-muted)]" />
                    <span className="text-sm font-semibold text-[var(--critical)]">
                      {simResult.after.risk_score?.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>

              {simResult.updated_graph && (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    Perturbed Causal Propagation:
                  </p>
                  <CausalGraph
                    graph={simResult.updated_graph}
                    affectedPath={simResult.affected_graph_path}
                    height={200}
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
