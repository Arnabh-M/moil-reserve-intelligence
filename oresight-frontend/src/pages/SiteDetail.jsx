import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  MapPin, ShieldAlert, Clock, Network, BarChart3, SearchX, Search, Loader2,
} from 'lucide-react';
import {
  Card, KPIStat, Badge, RecommendationCard, ProductionChart,
  EmptyState, ErrorState, SkeletonCard, SkeletonKPIRow,
} from '../components';
import CausalGraph from '../components/CausalGraph';
import {
  getSites, getEquipment, getRiskEvents, getRecommendations,
  getCausalGraph, searchSiteNotes, SITE_MAP, SITE_NAME_MAP,
} from '../api/client';

const tabs = [
  { id: 'production', label: 'Production History', icon: BarChart3 },
  { id: 'recommendations', label: 'Recommendations', icon: ShieldAlert },
  { id: 'graph', label: 'Graph', icon: Network },
];

function relevanceBadge(score) {
  if (score >= 0.7) return { label: 'High', variant: 'critical' };
  if (score >= 0.4) return { label: 'Medium', variant: 'warning' };
  return { label: 'Low', variant: 'unconfirmed' };
}

export default function SiteDetail() {
  const { id } = useParams();
  const [activeTab, setActiveTab] = useState('production');

  // ── Data states ──────────────────────────────────────────────────────
  const [site, setSite] = useState(null);
  const [siteEquipment, setSiteEquipment] = useState([]);
  const [riskEvents, setRiskEvents] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [causalGraph, setCausalGraph] = useState(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ── RAG Search states ────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null); // null = not searched yet
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const debounceRef = useRef(null);

  // Resolve numeric site ID from route param
  const numericSiteId = SITE_MAP[id] || Number(id) || null;

  // ── Load site data ───────────────────────────────────────────────────
  const loadSiteData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [sitesData, eqData, riskData] = await Promise.all([
        getSites(),
        getEquipment(numericSiteId),
        getRiskEvents({ site_id: numericSiteId }),
      ]);

      // Find the matching site
      const foundSite = sitesData.find(
        s => s.id === numericSiteId || String(s.id) === String(id) || s.name?.toLowerCase() === String(id).toLowerCase()
      );

      setSite(foundSite || null);
      setSiteEquipment(eqData || []);
      setRiskEvents(riskData || []);

      // Fetch recommendations for active risks (up to 3 to avoid overloading)
      const activeRisks = (riskData || []).filter(r => r.resolved === false);
      if (activeRisks.length > 0) {
        const recPromises = activeRisks.slice(0, 3).map(risk =>
          getRecommendations({ risk_event_id: risk.id }).catch(() => [])
        );
        const recResults = await Promise.all(recPromises);
        setRecommendations(recResults.flat());
      } else {
        setRecommendations([]);
      }
    } catch (err) {
      console.error('[SiteDetail] Failed to load site data:', err);
      setError(err.message || 'Failed to load site data.');
    } finally {
      setLoading(false);
    }
  }, [id, numericSiteId]);

  useEffect(() => {
    loadSiteData();
  }, [loadSiteData]);

  // ── Load causal graph when graph tab opened ──────────────────────────
  useEffect(() => {
    if (activeTab !== 'graph' || causalGraph || graphLoading) return;

    const firstRisk = riskEvents.find(r => r.resolved === false) || riskEvents[0];
    if (!firstRisk) return;

    setGraphLoading(true);
    setGraphError(null);
    getCausalGraph(firstRisk.id)
      .then(graph => setCausalGraph(graph))
      .catch(err => setGraphError(err.message || 'Failed to load causal graph.'))
      .finally(() => setGraphLoading(false));
  }, [activeTab, riskEvents, causalGraph, graphLoading]);

  // ── RAG Search with debounce ─────────────────────────────────────────
  const handleSearchChange = (value) => {
    setSearchQuery(value);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!value.trim()) {
      setSearchResults(null);
      setSearchLoading(false);
      setSearchError(null);
      return;
    }

    setSearchLoading(true);
    setSearchError(null);

    debounceRef.current = setTimeout(async () => {
      try {
        const results = await searchSiteNotes(value.trim(), numericSiteId);
        setSearchResults(results);
      } catch (err) {
        console.error('[SiteDetail] RAG search failed:', err);
        setSearchError(err.message || 'Search failed.');
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 400);
  };

  // Cleanup debounce on unmount
  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  // ── Derived values ───────────────────────────────────────────────────
  const activeRiskCount = riskEvents.filter(r => r.resolved === false).length;
  const eqUp = siteEquipment.filter(e => e.status === 'up').length;
  const eqTotal = siteEquipment.length;
  const uptimePct = eqTotal > 0 ? Math.round((eqUp / eqTotal) * 100) : 0;
  const reserveConfidence = site?.avg_reserve_confidence ?? site?.active_risk_count != null
    ? (site?.avg_reserve_confidence != null ? Math.round(site.avg_reserve_confidence * 100) : null)
    : null;

  // ── Error state: entire page failed ──────────────────────────────────
  if (!loading && error) {
    return (
      <div className="page-container">
        <ErrorState
          title="Failed to load site"
          message={error}
          onRetry={loadSiteData}
        />
      </div>
    );
  }

  // ── Loading state ────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="page-container">
        <div className="h-8 bg-border/70 rounded w-48 mb-2 animate-pulse" />
        <div className="h-4 bg-border/50 rounded w-72 mb-6 animate-pulse" />
        <SkeletonKPIRow count={3} />
        <div className="mt-6">
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  // ── Site not found ───────────────────────────────────────────────────
  if (!site) {
    return (
      <div className="page-container">
        <div className="animate-fade-in">
          <EmptyState
            icon={SearchX}
            title="Site Not Found"
            message={`No site found with ID "${id}". Try navigating from the dashboard.`}
            tone="neutral"
          />
        </div>
      </div>
    );
  }

  const siteName = site.name || SITE_NAME_MAP[numericSiteId] || id;
  const siteLocation = [site.belt_name, site.district, site.state].filter(Boolean).join(' — ');

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-start justify-between mb-1">
        <div>
          <h2 className="page-title">{siteName}</h2>
          {siteLocation && (
            <div className="flex items-center gap-2 mt-0.5">
              <MapPin size={13} className="text-text-muted" />
              <span className="text-sm text-text-secondary">{siteLocation}</span>
            </div>
          )}
        </div>
        <Badge variant={activeRiskCount > 0 ? 'warning' : 'operational'} dot>
          {activeRiskCount > 0 ? `${activeRiskCount} Active Risk${activeRiskCount > 1 ? 's' : ''}` : 'All Clear'}
        </Badge>
      </div>

      {/* KPI Stats */}
      <div className="grid-kpi stagger-children mt-4">
        <KPIStat
          label="Reserve Confidence"
          value={reserveConfidence != null ? `${reserveConfidence}%` : '—'}
          delta={null}
          deltaLabel={`${site.active_risk_count ?? 0} risk events at site`}
          icon={MapPin}
          color="teal"
        />
        <KPIStat
          label="Active Risks"
          value={activeRiskCount}
          delta={null}
          deltaLabel={activeRiskCount > 0 ? 'requires attention' : 'no active risks'}
          icon={ShieldAlert}
          color={activeRiskCount > 0 ? 'danger' : 'success'}
        />
        <KPIStat
          label="Equipment Online"
          value={eqTotal > 0 ? `${eqUp}/${eqTotal}` : '—'}
          delta={null}
          deltaLabel={eqTotal > 0 ? `${uptimePct}% uptime` : 'no equipment data'}
          icon={Clock}
          color="orange"
        />
      </div>

      {/* RAG Search Input */}
      <div className="mt-6 mb-4">
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-teal/10 text-teal shrink-0">
              <Search size={16} />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                Ask about this site
              </label>
              <input
                type="text"
                value={searchQuery}
                onChange={e => handleSearchChange(e.target.value)}
                placeholder="e.g. What are the recent geological findings?"
                className="w-full bg-bg border border-border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20 placeholder:text-text-muted"
              />
            </div>
          </div>

          {/* Search loading */}
          {searchLoading && (
            <div className="mt-3 space-y-2">
              <SkeletonCard lines={2} showIcon={false} />
              <SkeletonCard lines={2} showIcon={false} />
            </div>
          )}

          {/* Search error */}
          {!searchLoading && searchError && (
            <div className="mt-3">
              <ErrorState
                compact
                title="Search failed"
                message={searchError}
                onRetry={() => handleSearchChange(searchQuery)}
              />
            </div>
          )}

          {/* Search results */}
          {!searchLoading && !searchError && searchResults !== null && (
            <div className="mt-3">
              {searchResults.length === 0 ? (
                <EmptyState
                  icon={SearchX}
                  title="No matching notes"
                  message={`No results found for "${searchQuery}" at this site.`}
                  tone="neutral"
                  compact
                />
              ) : (
                <div className="space-y-2">
                  {searchResults.map((result, idx) => {
                    const badge = relevanceBadge(result.score ?? 0);
                    return (
                      <div
                        key={result.note_id || idx}
                        className="p-3 rounded-lg bg-bg border border-border hover:border-teal/30 transition-colors duration-150"
                      >
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <p className="text-sm text-text-primary leading-relaxed flex-1 break-words">
                            {result.text || '—'}
                          </p>
                          <Badge variant={badge.variant} className="shrink-0">
                            {badge.label}{result.score != null ? ` (${Math.round(result.score * 100)}%)` : ''}
                          </Badge>
                        </div>
                        {result.note_id && (
                          <span className="text-[10px] text-text-muted font-mono">
                            Note: {result.note_id}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 p-1 bg-bg-surface rounded-lg border border-border w-fit">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                activeTab === tab.id
                  ? 'bg-orange text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg'
              }`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content: Production History */}
      {activeTab === 'production' && (
        <Card
          title="Production History"
          subtitle={`30-day extraction telemetry for ${siteName} (Solid: Actual, Dashed: Target)`}
        >
          <ProductionChart site_id={numericSiteId} days={30} className="mt-2" />
        </Card>
      )}

      {/* Tab Content: Recommendations */}
      {activeTab === 'recommendations' && (
        <div className="space-y-5 stagger-children">
          {recommendations.length === 0 ? (
            <Card>
              <EmptyState
                title="No recommendations"
                message={activeRiskCount > 0
                  ? 'Recommendations are being generated for active risks.'
                  : 'No active risks at this site — no mitigations needed.'}
                tone={activeRiskCount > 0 ? 'neutral' : 'positive'}
              />
            </Card>
          ) : (
            recommendations.map((rec, idx) => (
              <RecommendationCard
                key={rec.risk_event_id ? `rec-${rec.risk_event_id}-${idx}` : `rec-${idx}`}
                trigger={rec.trigger}
                risk_event_id={rec.risk_event_id}
                site_id={numericSiteId}
                options={rec.options}
              />
            ))
          )}
        </div>
      )}

      {/* Tab Content: Graph */}
      {activeTab === 'graph' && (
        <Card title="Knowledge Graph" subtitle={`Neo4j subgraph for ${siteName}`}>
          {graphLoading && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Loader2 size={24} className="animate-spin text-teal mb-3" />
              <p className="text-sm text-text-muted">Loading causal graph…</p>
            </div>
          )}

          {graphError && (
            <ErrorState
              compact
              title="Graph unavailable"
              message={graphError}
              onRetry={() => {
                setCausalGraph(null);
                setGraphLoading(false);
                setGraphError(null);
              }}
            />
          )}

          {!graphLoading && !graphError && causalGraph && (
            <>
              {causalGraph.graph_source === 'postgres_fallback' && (
                <div className="mb-3 text-[11px] text-warning bg-warning/10 border border-warning/20 rounded-lg px-3 py-2">
                  {causalGraph.note || 'This site has no full causal graph yet — showing a single-node fallback.'}
                </div>
              )}
              <CausalGraph graph={causalGraph} height={320} />
            </>
          )}

          {!graphLoading && !graphError && !causalGraph && riskEvents.length === 0 && (
            <EmptyState
              icon={Network}
              title="No graph data"
              message="This site has no risk events to build a causal graph from."
              tone="neutral"
            />
          )}
        </Card>
      )}
    </div>
  );
}
