import React, { useState, useEffect } from 'react';
import { Sparkles } from 'lucide-react';
import { RecommendationCard, EmptyState, ErrorState } from '../components';
import { getAllRecommendations, USE_MOCK } from '../api/client';

export default function Recommendations() {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchRecommendations = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAllRecommendations();
      setRecommendations(data || []);
    } catch (err) {
      console.error('[Recommendations] Error fetching recommendations:', err);
      setError(err.message || 'Failed to fetch recommendations from server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, []);

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-8 flex-wrap">
        <div>
          <h1 className="page-title flex items-center gap-2.5">
            <span>Corrective Actions &amp; Mitigations</span>
            <span className="px-2 py-0.5 rounded-full bg-[var(--accent-soft)] text-[var(--accent-primary)] text-[11px] font-semibold flex items-center gap-1">
              <Sparkles size={11} /> AI Decision Engine
            </span>
          </h1>
          <p className="page-subtitle">
            Real-time mitigation recommendations, multi-variable tradeoff matrices, and inline what-if scenario simulations
          </p>
        </div>

        {USE_MOCK && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[var(--accent-soft)] text-[var(--accent-primary)] text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)] animate-pulse" />
            <span>Simulated Engine Active</span>
          </div>
        )}
      </div>

      {/* Loading Skeletons */}
      {loading && (
        <div className="space-y-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[var(--bg-elevated)]/40 rounded-xl p-5 border border-[var(--divider)] animate-pulse">
              <div className="h-4 bg-[var(--divider)] rounded w-1/2 mb-4" />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[1, 2, 3].map(j => (
                  <div key={j} className="h-28 bg-[var(--divider)]/40 rounded-lg p-3" />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <ErrorState
          title="Failed to Load Recommendations"
          message={error}
          onRetry={fetchRecommendations}
        />
      )}

      {/* Recommendations List */}
      {!loading && !error && recommendations.length === 0 && (
        <EmptyState
          title="No recommendations required"
          message="All mine operations are running within optimal parameters. No mitigation actions required."
          tone="positive"
        />
      )}

      {!loading && !error && recommendations.length > 0 && (
        <div className="space-y-6">
          {recommendations.map((rec, idx) => (
            <RecommendationCard
              key={rec.risk_event_id ? `rec-${rec.risk_event_id}-${idx}` : `rec-${idx}`}
              trigger={rec.trigger}
              risk_event_id={rec.risk_event_id}
              site_id={rec.site_id || ((idx % 3) + 1)}
              options={rec.options}
            />
          ))}
        </div>
      )}
    </div>
  );
}


