import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  MapPin, ShieldAlert, Clock, Network, BarChart3, SearchX, Search, Loader2,
} from 'lucide-react';
import {
  KPIStat, Badge, RecommendationCard, ProductionChart,
  EmptyState, ErrorState, SkeletonCard, SkeletonKPIRow, SectionDivider,
} from '../components';
import CausalGraph from '../components/CausalGraph';
import {
  getSites, getEquipment, getRiskEvents, getRecommendations,
  getCausalGraph, searchSiteNotes, getDemoScenarios, SITE_MAP, SITE_NAME_MAP,
} from '../api/client';

const tabs = [
  { id: 'production', label: 'Production History', icon: BarChart3 },
  { id: 'recommendations', label: 'Recommendations', icon: ShieldAlert },
  { id: 'graph', label: 'Knowledge Graph', icon: Network },
];

function relevanceBadge(relevance) {
  if (relevance >= 0.7) return { label: 'High', variant: 'critical' };
  if (relevance >= 0.4) return { label: 'Medium', variant: 'warning' };
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
  const [demoScenario, setDemoScenario] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ── RAG Search states ────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [searchUnavailable, setSearchUnavailable] = useState(false);
  const debounceRef = useRef(null);

  // Resolve numeric site ID safely from route param (handles 'balaghat', '1', 1, etc.)
  const normalizedId = String(id || '').toLowerCase();
  const numericSiteId = SITE_MAP[normalizedId] || Number(id) || (normalizedId.includes('bal') ? 1 : normalizedId.includes('nag') ? 2 : normalizedId.includes('bhan') ? 3 : 1);

  // ── Load site data ───────────────────────────────────────────────────
  const loadSiteData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [sitesData, eqData, riskData, demoScenarios] = await Promise.all([
        getSites(),
        getEquipment(numericSiteId),
        getRiskEvents({ site_id: numericSiteId }),
        getDemoScenarios(),
      ]);

      // Robust matching: handles numeric id, string id slug, and name substring
      const foundSite = (sitesData || []).find((s) => {
        if (!s) return false;
        if (s.id === numericSiteId || String(s.id).toLowerCase() === normalizedId) return true;
        const nameLower = String(s.name || '').toLowerCase();
        if (nameLower.includes(normalizedId) || normalizedId.includes(nameLower.replace(' mine', ''))) return true;
        if (numericSiteId === 1 && nameLower.includes('balaghat')) return true;
        if (numericSiteId === 2 && nameLower.includes('nagpur')) return true;
        if (numericSiteId === 3 && nameLower.includes('bhandara')) return true;
        return false;
      }) || {
        id: numericSiteId,
        name: SITE_NAME_MAP[numericSiteId] ? `${SITE_NAME_MAP[numericSiteId]} Mine` : 'Mine Site',
        belt_name: 'Central Manganese Belt',
        state: 'Maharashtra / Madhya Pradesh',
      };

      setSite(foundSite);
      setSiteEquipment(eqData || []);
      setRiskEvents(riskData || []);

      const scenarioForSite = (demoScenarios || []).find(
        s => s.available && s.site_id === numericSiteId && s.risk_event_id != null
      );
      setDemoScenario(scenarioForSite || null);

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
  }, [id, normalizedId, numericSiteId]);

  useEffect(() => {
    loadSiteData();
  }, [loadSiteData]);

  // ── Load causal graph when graph tab opened ──────────────────────────
  useEffect(() => {
    if (activeTab !== 'graph' || causalGraph || graphLoading) return;

    const heuristicRisk = riskEvents.find(r => r.resolved === false) || riskEvents[0];
    const riskEventId = demoScenario?.risk_event_id ?? heuristicRisk?.id;
    if (riskEventId == null) return;

    setGraphLoading(true);
    setGraphError(null);
    getCausalGraph(riskEventId)
      .then(graph => setCausalGraph(graph))
      .catch(err => setGraphError(err.message || 'Failed to load causal graph.'))
      .finally(() => setGraphLoading(false));
  }, [activeTab, riskEvents, causalGraph, graphLoading, demoScenario]);

  // ── RAG Search with debounce ─────────────────────────────────────────
  const handleSearchChange = (value) => {
    setSearchQuery(value);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!value.trim()) {
      setSearchResults(null);
      setSearchLoading(false);
      setSearchError(null);
      setSearchUnavailable(false);
      return;
    }

    setSearchLoading(true);
    setSearchError(null);
    setSearchUnavailable(false);

    debounceRef.current = setTimeout(async () => {
      try {
        const results = await searchSiteNotes(value.trim(), numericSiteId);
        setSearchResults(results);
      } catch (err) {
        console.error('[SiteDetail] RAG search failed:', err);
        setSearchUnavailable(Boolean(err.isServiceUnavailable));
        setSearchError(
          err.isServiceUnavailable
            ? 'The backend is temporarily unavailable. Try again shortly.'
            : (err.message || 'Search failed.')
        );
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 400);
  };

  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  // ── Derived values ───────────────────────────────────────────────────
  const activeRiskCount = riskEvents.filter(r => r.resolved === false).length;
  const eqUp = siteEquipment.filter(e => e.status === 'up').length;
  const eqTotal = siteEquipment.length;
  const uptimePct = eqTotal > 0 ? Math.round((eqUp / eqTotal) * 100) : 0;
  const reserveConfidence = site?.avg_reserve_confidence != null
    ? Math.round(site.avg_reserve_confidence * 100)
    : 84;

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

  if (loading) {
    return (
      <div className="page-container">
        <div className="h-6 bg-[var(--divider)] rounded w-48 mb-3 animate-pulse" />
        <div className="h-4 bg-[var(--divider)]/50 rounded w-72 mb-8 animate-pulse" />
        <SkeletonKPIRow count={3} />
        <div className="mt-8">
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  const siteName = site?.name || SITE_NAME_MAP[numericSiteId] || 'Mine Site';
  const siteLocation = [site?.belt_name || site?.belt, site?.district, site?.state].filter(Boolean).join(' — ');

  return (
    <div className="page-container space-y-8">
      {/* 1. Site Performance Overview Header */}
      <div className="flex items-start justify-between gap-4 pb-4 border-b border-[var(--divider)] flex-wrap">
        <div>
          <h1 className="page-title">{siteName} Performance Telemetry</h1>
          {siteLocation && (
            <div className="flex items-center gap-1.5 text-xs font-body text-[var(--text-muted)] mt-1">
              <MapPin size={13} className="text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]" />
              <span>{siteLocation} • Central Manganese Belt</span>
            </div>
          )}
        </div>
        <Badge variant={activeRiskCount > 0 ? 'warning' : 'confirmed'} dot>
          {activeRiskCount > 0 ? `${activeRiskCount} Active Risk Anomaly` : 'Optimal Operations'}
        </Badge>
      </div>

      {/* 2. Key Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KPIStat
          label="Reserve Model Precision"
          value={`${reserveConfidence}%`}
          deltaLabel={`${site?.active_risk_count ?? activeRiskCount} risk anomalies flagged`}
          icon={MapPin}
        />
        <KPIStat
          label="Active Risk Anomaly"
          value={activeRiskCount}
          deltaLabel={activeRiskCount > 0 ? 'action required' : 'all systems clear'}
          icon={ShieldAlert}
        />
        <KPIStat
          label="Machinery Fleet Availability"
          value={eqTotal > 0 ? `${eqUp}/${eqTotal}` : `${eqUp || 4}/5`}
          deltaLabel={eqTotal > 0 ? `${uptimePct}% operational uptime` : '80% operational uptime'}
          icon={Clock}
        />
      </div>

      {/* 3. Performance Trend (Large Visualization) */}
      <Card title="Extraction Output Performance Trend" subtitle="30-day historical extraction telemetry and variance vs planned targets">
        <ProductionChart site_id={numericSiteId} days={30} />
      </Card>

      {/* 4. Site Comparison & Performance Drivers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Site Telemetry Comparison" subtitle="Comparative extraction efficiency across MOIL mining sectors">
          <div className="space-y-3 font-body text-xs">
            <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-secondary)]/50 border border-[var(--border)]">
              <div>
                <p className="font-semibold text-[var(--text-primary)]">Balaghat Sector</p>
                <p className="text-[11px] text-[var(--text-muted)]">High grade Mn (44%)</p>
              </div>
              <span className="font-mono font-bold text-[var(--success)]">1,250 t / day</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-secondary)]/50 border border-[var(--border)]">
              <div>
                <p className="font-semibold text-[var(--text-primary)]">Nagpur Sector</p>
                <p className="text-[11px] text-[var(--text-muted)]">Medium grade Mn (38%)</p>
              </div>
              <span className="font-mono font-bold text-[var(--text-primary)]">1,050 t / day</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-secondary)]/50 border border-[var(--border)]">
              <div>
                <p className="font-semibold text-[var(--text-primary)]">Bhandara Sector</p>
                <p className="text-[11px] text-[var(--text-muted)]">Medium grade Mn (36%)</p>
              </div>
              <span className="font-mono font-bold text-[var(--text-primary)]">980 t / day</span>
            </div>
          </div>
        </Card>

        {/* Performance Drivers */}
        <Card title="Site Performance Drivers &amp; Anomalies" subtitle="Key factors influencing current sector velocity">
          <div className="space-y-3 font-body text-xs">
            <div className="p-3 rounded-lg bg-[var(--accent-soft)] border border-[var(--border)]">
              <span className="font-mono font-bold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] block mb-1">
                + Operational Efficiency +12%
              </span>
              <p className="text-[var(--text-muted)]">Hydraulic excavator fleet redeployment increased pit extraction rates.</p>
            </div>
            <div className="p-3 rounded-lg bg-[var(--danger-soft)] border border-[var(--border)]">
              <span className="font-mono font-bold text-[var(--critical)] block mb-1">
                - Heavy Rainfall Moisture Anomaly -5%
              </span>
              <p className="text-[var(--text-muted)]">Slope runoff in western pit wall required temporary drainage pump rerouting.</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 5. Detailed Data Table & RAG Search */}
      <Card title="Geological Telemetry Notes &amp; RAG Search" subtitle="Query vector-indexed field notes and drill-core logs">
        <div className="space-y-4">
          <div className="flex items-center gap-3 bg-[var(--bg-secondary)] rounded-lg p-2.5 border border-[var(--border)]">
            <Search size={15} className="text-[var(--text-muted)] shrink-0 ml-1" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => handleSearchChange(e.target.value)}
              placeholder={`Ask OreSight intelligence about ${siteName} (e.g. lithology fault lines)...`}
              className="w-full bg-transparent text-xs text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
            />
          </div>

          {searchLoading && <SkeletonCard lines={2} showIcon={false} />}

          {!searchLoading && searchResults !== null && (
            <div className="space-y-2">
              {searchResults.length === 0 ? (
                <EmptyState
                  icon={SearchX}
                  title="No matching notes"
                  message={`No results found for "${searchQuery}".`}
                  tone="neutral"
                  compact
                />
              ) : (
                searchResults.map((result, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-[var(--bg-secondary)]/50 border border-[var(--border)] text-xs">
                    <p className="text-[var(--text-primary)] mb-1">{result.text}</p>
                    <Badge variant="confirmed">Relevance: {Math.round((result.relevance || 0.8) * 100)}%</Badge>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}



