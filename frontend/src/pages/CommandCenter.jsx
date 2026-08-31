import { useEffect, useState } from 'react'
import { AlertTriangle, Gauge, Eye, RefreshCw, Map as MapIcon, GitBranch, AlertCircle } from 'lucide-react'
import Card from '../components/Card'
import KPIStat from '../components/KPIStat'
import LiveEventFeed from '../components/LiveEventFeed'
import { getSites, getRiskEvents } from '../api/client'
import { getEventTimestamp, formatRelativeTime } from '../lib/time'

// The /sites payload isn't guaranteed to carry a reserve-confidence field
// yet, so this derives a stable mock value per site when one is missing —
// same site always yields the same value.
function estimateReserveConfidence(site) {
  const provided = site.reserve_confidence ?? site.reserveConfidence ?? site.confidence
  if (typeof provided === 'number') return provided > 1 ? provided / 100 : provided

  const seed = String(site.id ?? site.name ?? '')
  let hash = 0
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) % 1000
  }
  return 0.55 + (hash / 1000) * 0.33 // spread roughly between 0.55 and 0.88
}

export default function CommandCenter() {
  const [sites, setSites] = useState([])
  const [riskEvents, setRiskEvents] = useState([])
  const [kpiStatus, setKpiStatus] = useState('loading') // 'loading' | 'ready' | 'error'

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [sitesData, riskData] = await Promise.all([getSites(), getRiskEvents()])
        if (cancelled) return
        setSites(sitesData)
        setRiskEvents(riskData)
        setKpiStatus('ready')
      } catch {
        if (!cancelled) setKpiStatus('error')
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  const activeRiskEvents = riskEvents.filter((e) => e.resolved === false).length

  const avgReserveConfidence = sites.length
    ? sites.reduce((sum, s) => sum + estimateReserveConfidence(s), 0) / sites.length
    : 0

  const sitesUnderWatch = sites.length

  const latestUpdateDate = riskEvents.reduce((latest, e) => {
    const ts = getEventTimestamp(e)
    if (!ts) return latest
    return !latest || ts > latest ? ts : latest
  }, null)

  const kpiValue = (value) => (kpiStatus === 'ready' ? value : '—')

  return (
    <div className="flex flex-col gap-6">
      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPIStat
          icon={AlertTriangle}
          value={kpiValue(String(activeRiskEvents).padStart(2, '0'))}
          label="Active Risk Events"
          accent="orange"
        />
        <KPIStat
          icon={Gauge}
          value={kpiValue(`${(avgReserveConfidence * 100).toFixed(1)}%`)}
          label="Avg Reserve Confidence"
          accent="teal"
        />
        <KPIStat
          icon={Eye}
          value={kpiValue(String(sitesUnderWatch).padStart(2, '0'))}
          label="Sites Under Watch"
          accent="navy"
        />
        <KPIStat
          icon={RefreshCw}
          value={kpiValue(latestUpdateDate ? formatRelativeTime(latestUpdateDate) : 'no data')}
          label="Twin Last Updated"
          accent="teal"
        />
      </div>

      {kpiStatus === 'error' && (
        <div className="flex items-center gap-2 rounded-sm border border-orange/30 bg-orange/5 px-4 py-2.5 text-xs text-orange">
          <AlertCircle size={14} className="shrink-0" />
          Unable to reach the backend at http://localhost:8000 — showing unavailable KPI data.
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 items-start">
        {/* Map + graph preview panel (placeholder) */}
        <Card padded={false} className="overflow-hidden">
          <div className="p-5 pb-4 border-b border-border">
            <h3 className="font-heading text-[15px] font-semibold text-navy">Mine Intelligence Map &amp; Causal Graph</h3>
            <p className="text-xs text-slate-500 mt-1">Reserve confidence, risk events, and causal relationships</p>
          </div>
          <div className="p-5">
            <div className="flex h-[380px] flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-border bg-bg text-center">
              <div className="flex items-center gap-3 text-navy2">
                <MapIcon size={28} strokeWidth={1.5} />
                <GitBranch size={28} strokeWidth={1.5} />
              </div>
              <p className="text-sm font-medium text-navy">Map &amp; causal graph preview</p>
              <p className="max-w-xs text-xs text-slate-500">
                Site map and causal intelligence visualization will render here.
              </p>
            </div>
          </div>
        </Card>

        {/* Live Event Feed */}
        <LiveEventFeed />
      </div>
    </div>
  )
}
