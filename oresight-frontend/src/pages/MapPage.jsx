import { useEffect, useMemo, useState } from 'react'
import { MapPin, Loader2, AlertCircle } from 'lucide-react'
import { getSites } from '../api/client'
import { SAMPLE_SITES, DEFAULT_RASTER_OPACITY, prospectivityUrl, prospectivityBandsUrl } from '../lib/map'
import LayerToggle from '../components/map/LayerToggle'
import MineMap from '../components/map/MineMap'
import ZoneDetailPanel from '../components/map/ZoneDetailPanel'
import CrossSectionDrawer from '../components/map/CrossSectionDrawer'
import ProspectivityCellPanel from '../components/map/ProspectivityCellPanel'

export default function MapPage() {
  const [prospectivityVisible, setProspectivityVisible] = useState(false)
  const [spectralVisible, setSpectralVisible] = useState(false)
  const [droneVisible, setDroneVisible] = useState(false)
  const [ndviVisible, setNdviVisible] = useState(false)
  const [lineamentVisible, setLineamentVisible] = useState(false)
  const [rasterOpacity, setRasterOpacity] = useState(DEFAULT_RASTER_OPACITY)

  // PART 7.1 — no prospectivity surface until a site is explicitly selected.
  const [prospectivitySiteId, setProspectivitySiteId] = useState(null)
  const [prospectivityData, setProspectivityData] = useState(null)
  const [prospectivityBands, setProspectivityBands] = useState(null)
  const [prospectivityStatus, setProspectivityStatus] = useState('idle') // idle|loading|ready|error
  const [selectedCell, setSelectedCell] = useState(null)

  const [selectedWeek, setSelectedWeek] = useState(4)
  const [selectedZone, setSelectedZone] = useState(null)
  const [sites, setSites] = useState([])

  // P4 Day 4: Fly-To navigation state
  const [flyToTarget, setFlyToTarget] = useState(null)
  const [selectedSiteIdForFlyTo, setSelectedSiteIdForFlyTo] = useState('')

  // P4 Day 4: Cross-section tool & drawer state
  const [crossSectionActive, setCrossSectionActive] = useState(false)
  const [crossSectionPoint, setCrossSectionPoint] = useState(null)
  const [crossSectionDrawerOpen, setCrossSectionDrawerOpen] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function loadSites() {
      try {
        const data = await getSites()
        if (!cancelled) setSites(data)
      } catch {
        // Site names are optional for the zone panel fallback.
      }
    }

    loadSites()
    return () => {
      cancelled = true
    }
  }, [])

  const siteNameById = useMemo(
    () => Object.fromEntries(sites.map((site) => [site.id, site.name])),
    [sites]
  )

  const selectedSiteName = useMemo(() => {
    if (!selectedZone) return null
    const siteId = selectedZone.site_id
    if (siteNameById[siteId]) return siteNameById[siteId]
    if (siteId === 'balaghat' || siteId === 1) return 'Balaghat Mine'
    if (siteId === 'nagpur' || siteId === 2) return 'Nagpur Mine'
    if (siteId === 'bhandara' || siteId === 3) return 'Bhandara Mine'
    return siteId ? String(siteId) : null
  }, [selectedZone, siteNameById])

  // PART 7.2 — on site selection: fly to the site, then load ONLY that site's
  // prospectivity surface. Clearing the selection removes the surface entirely,
  // returning to the clean 7.1 default state.
  useEffect(() => {
    if (!prospectivitySiteId) {
      setProspectivityData(null)
      setProspectivityBands(null)
      setProspectivityStatus('idle')
      return
    }

    let cancelled = false
    setProspectivityStatus('loading')
    setSelectedCell(null)

    async function loadProspectivity() {
      try {
        const res = await fetch(prospectivityUrl(prospectivitySiteId))
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        if (!data || data.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
          throw new Error('Malformed GeoJSON payload')
        }
        if (cancelled) return
        setProspectivityData(data)
        setProspectivityStatus('ready')

        // Band outlines are a small companion file; the surface is still usable
        // without them, so a failure here degrades the outline rather than the map.
        try {
          const bandsRes = await fetch(prospectivityBandsUrl(prospectivitySiteId))
          if (bandsRes.ok && !cancelled) setProspectivityBands(await bandsRes.json())
        } catch {
          if (!cancelled) setProspectivityBands(null)
        }
      } catch (err) {
        console.warn('[MapPage] prospectivity load failed:', err)
        if (!cancelled) {
          setProspectivityData(null)
          setProspectivityBands(null)
          setProspectivityStatus('error')
        }
      }
    }

    // Let the 1.2 s flyTo settle before painting ~3k polygons, so the
    // transition stays smooth rather than stuttering mid-flight.
    const timer = setTimeout(loadProspectivity, 1200)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [prospectivitySiteId])

  // Handle site selection from dropdown/search to smoothly flyTo
  function handleSiteSelect(siteId) {
    setSelectedSiteIdForFlyTo(siteId)
    if (!siteId) {
      setProspectivitySiteId(null)
      return
    }
    const site = SAMPLE_SITES.find((s) => s.id === siteId)
    if (site) {
      setFlyToTarget({
        id: site.id,
        name: site.name,
        latitude: site.latitude,
        longitude: site.longitude,
        zoom: 11,
      })
      setProspectivitySiteId(site.id)
    }
  }

  // Handle map cross-section point click
  function handleSelectCrossSectionPoint(point) {
    setCrossSectionPoint(point)
    setCrossSectionDrawerOpen(true)
  }

  // Handle Inspect Cross-Section action from ZoneDetailPanel
  function handleInspectZoneCrossSection() {
    if (!selectedZone) return
    // Approximate or direct coordinate for the zone
    const lat = selectedZone.latitude ?? (selectedZone.site_id === 'balaghat' ? 21.8 : selectedZone.site_id === 'nagpur' ? 21.1 : 21.2)
    const lng = selectedZone.longitude ?? (selectedZone.site_id === 'balaghat' ? 80.2 : selectedZone.site_id === 'nagpur' ? 79.1 : 79.6)
    setCrossSectionPoint({
      lat,
      lng,
      zoneName: selectedZone.zone_name,
      site_id: selectedZone.site_id,
      siteName: selectedSiteName,
    })
    setCrossSectionDrawerOpen(true)
  }

  return (
    <div className="-m-6 flex h-[calc(100vh-4rem)] overflow-hidden relative">
      {/* Sidebar Layer Toggle */}
      <LayerToggle
        prospectivityVisible={prospectivityVisible}
        onProspectivityChange={setProspectivityVisible}
        spectralVisible={spectralVisible}
        onSpectralChange={setSpectralVisible}
        lineamentVisible={lineamentVisible}
        onLineamentChange={setLineamentVisible}
        droneVisible={droneVisible}
        onDroneChange={setDroneVisible}
        ndviVisible={ndviVisible}
        onNdviChange={setNdviVisible}
        rasterOpacity={rasterOpacity}
        onRasterOpacityChange={setRasterOpacity}
      />

      <div className="relative min-h-0 flex-1 h-full">
        {/* Compact Site Selector / Fly-To Navigation Header */}
        <div className="absolute top-4 right-4 z-20 flex items-center gap-2 bg-bg-surface border border-border px-3 py-1.5 rounded-[3px] shadow-xs">
          <MapPin size={14} className="text-teal shrink-0" />
          <select
            aria-label="Jump to Mine Site"
            value={selectedSiteIdForFlyTo}
            onChange={(e) => handleSiteSelect(e.target.value)}
            className="bg-transparent text-xs font-semibold text-navy outline-none cursor-pointer pr-1"
          >
            <option value="">Jump to Mine Site…</option>
            {SAMPLE_SITES.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name} Mine ({site.latitude.toFixed(1)}°N, {site.longitude.toFixed(1)}°E)
              </option>
            ))}
          </select>
        </div>

        {/* Map Engine */}
        <MineMap
          prospectivityVisible={prospectivityVisible}
          spectralVisible={spectralVisible}
          droneVisible={droneVisible}
          ndviVisible={ndviVisible}
          lineamentVisible={lineamentVisible}
          selectedWeek={selectedWeek}
          onWeekChange={setSelectedWeek}
          onZoneSelect={setSelectedZone}
          flyToTarget={flyToTarget}
          crossSectionActive={crossSectionActive}
          onToggleCrossSection={() => setCrossSectionActive(!crossSectionActive)}
          onSelectCrossSectionPoint={handleSelectCrossSectionPoint}
          crossSectionPoint={crossSectionPoint}
          rasterOpacity={rasterOpacity}
          prospectivityData={prospectivityData}
          prospectivityBands={prospectivityBands}
          onProspectivityCellSelect={setSelectedCell}
        />

        {/* PART 7.2 — loading state while the selected site's surface streams in */}
        {prospectivityStatus === 'loading' && (
          <div className="absolute left-1/2 top-4 z-20 flex -translate-x-1/2 items-center gap-2 rounded-[3px] border border-border bg-bg-surface px-3 py-2 text-xs text-text-secondary shadow-xs">
            <Loader2 size={14} className="shrink-0 animate-spin text-teal" />
            Loading reserve surface…
          </div>
        )}

        {/* Robustness requirement — clear error state, never a blank/broken map */}
        {prospectivityStatus === 'error' && (
          <div className="absolute left-1/2 top-4 z-20 flex -translate-x-1/2 items-start gap-2 rounded-[3px] border border-danger/40 bg-bg-surface px-3 py-2 shadow-xs">
            <AlertCircle size={14} className="mt-0.5 shrink-0 text-danger" />
            <div>
              <p className="text-xs font-semibold text-danger">Reserve data unavailable for this site</p>
              <button
                type="button"
                onClick={() => setProspectivitySiteId((id) => (id ? `${id}` : id))}
                className="mt-0.5 text-[10px] text-text-muted underline hover:text-navy cursor-pointer"
              >
                Select another site to retry
              </button>
            </div>
          </div>
        )}

        {/* PART 7.10 — clicked-cell detail panel */}
        <ProspectivityCellPanel
          cell={selectedCell}
          siteName={selectedCell ? siteNameById[selectedCell.site_id] || selectedCell.site_id : null}
          isPlaceholder={prospectivityData?.provenance?.status === 'PLACEHOLDER_SCORES'}
          onClose={() => setSelectedCell(null)}
        />

        {/* Right Feature Detail Panel */}
        <ZoneDetailPanel
          zone={selectedZone}
          siteName={selectedSiteName}
          onClose={() => setSelectedZone(null)}
          onInspectCrossSection={handleInspectZoneCrossSection}
        />

        {/* Bottom Cross-Section Profile Drawer (Day 4) */}
        <CrossSectionDrawer
          isOpen={crossSectionDrawerOpen}
          onClose={() => {
            setCrossSectionDrawerOpen(false)
            setCrossSectionPoint(null)
            setCrossSectionActive(false)
          }}
          point={crossSectionPoint}
        />
      </div>
    </div>
  )
}
