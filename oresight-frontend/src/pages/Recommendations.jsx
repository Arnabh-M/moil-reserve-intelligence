import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, RefreshCw, Sparkles, Filter } from 'lucide-react';
import { RecommendationCard, Card, Button } from '../components';
import { getAllRecommendations, USE_MOCK } from '../api/client';

export default function Recommendations() {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterType, setFilterType] = useState('all');

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
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="page-title flex items-center gap-2">
            <span>AI Recommendations</span>
            <span className="p-1 rounded-md bg-orange/10 text-orange text-xs flex items-center gap-1 font-semibold">
              <Sparkles size={12} /> GET /recommendations
            </span>
          </h2>
          <p className="page-subtitle mb-0">
            Real-time mitigation and response options generated from active risk events
          </p>
        </div>

        {USE_MOCK && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs font-bold shadow-xs">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            USE_MOCK = true (Simulated Engine)
          </div>
        )}
      </div>

      {/* Loading Skeletons */}
      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <Card key={i} className="animate-pulse">
              <div className="flex items-center gap-3 mb-4 pb-3 border-b border-border">
                <div className="w-8 h-8 rounded-lg bg-border" />
                <div className="h-4 bg-border rounded w-3/4" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {[1, 2, 3].map(j => (
                  <div key={j} className="h-32 bg-border/40 rounded-lg p-3 space-y-2">
                    <div className="h-4 bg-border rounded w-20" />
                    <div className="h-3 bg-border rounded w-full" />
                    <div className="h-3 bg-border rounded w-4/5" />
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <Card className="border-danger/30">
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertCircle size={28} className="text-danger mb-2" />
            <h4 className="text-sm font-bold text-text-primary mb-1">Failed to Load Recommendations</h4>
            <p className="text-xs text-text-muted max-w-sm mb-4">{error}</p>
            <Button variant="ghost" size="sm" onClick={fetchRecommendations}>
              <RefreshCw size={14} /> Retry API Request
            </Button>
          </div>
        </Card>
      )}

      {/* Recommendations List */}
      {!loading && !error && recommendations.length === 0 && (
        <Card>
          <div className="flex flex-col items-center justify-center py-16 text-center text-text-muted text-xs">
            <p className="text-sm font-semibold text-text-primary mb-1">No Active Recommendations</p>
            <p>All mine operations are running within optimal parameters. No mitigation actions required.</p>
          </div>
        </Card>
      )}

      {!loading && !error && recommendations.length > 0 && (
        <div className="space-y-5 stagger-children">
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
