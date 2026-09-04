import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, Loader2 } from 'lucide-react'
import Map, { Layer, Marker, Popup, Source } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { getReserveZones } from '../../api/client'
import {
  MAP_CENTER,
  MAP_STYLE,
  MAP_ZOOM,
  RESERVE_ZONES_FILL_LAYER_ID,
  RESERVE_ZONES_SOURCE_ID,
  RESERVE_ZONE_FILL_PAINT,
  SAMPLE_SITES,
  SPECTRAL_LAYER_CONFIG,
  DRONE_LAYER_CONFIG,
  NDVI_TIMESERIES_CONFIG,
  STRUCTURAL_LINES_SOURCE_ID,
  STRUCTURAL_LINES_LAYER_ID,
  STRUCTURAL_LINE_PAINT,
  STRUCTURAL_LINES_MIN_ZOOM,
  SITES_SOURCE_ID,
  CLUSTERS_LAYER_ID,
  CLUSTER_COUNT_LAYER_ID,
  UNCLUSTERED_POINT_LAYER_ID,
  SITE_MARKER_SHADOW_LAYER_ID,
  SITE_MARKER_SHADOW_PAINT,
  SITES_GEOJSON,
  DEFAULT_RASTER_OPACITY,
  PROSPECTIVITY_SOURCE_ID,
  PROSPECTIVITY_FILL_LAYER_ID,
  PROSPECTIVITY_BOUNDARY_LAYER_ID,
  PROSPECTIVITY_EDGE_LAYER_ID,
  PROSPECTIVITY_FILL_PAINT,
  PROSPECTIVITY_BOUNDARY_PAINT,
  PROSPECTIVITY_EDGE_PAINT,
  PROSPECTIVITY_BANDS_SOURCE_ID,
} from '../../lib/map'
import ConfidenceLegend from './ConfidenceLegend'
import NdviTimeSlider from './NdviTimeSlider'

export default function MineMap({
  prospectivityVisible,
  spectralVisible = false,
  droneVisible = false,
  ndviVisible = false,
  lineamentVisible = false,
  selectedWeek = 4,
  onWeekChange,
  onZoneSelect,
  flyToTarget = null,
  crossSectionActive = false,
  onToggleCrossSection,
  onSelectCrossSectionPoint,
  crossSectionPoint = null,
  rasterOpacity = DEFAULT_RASTER_OPACITY,
  prospectivityData = null,
  prospectivityBands = null,
  onProspectivityCellSelect,
}) {
  const mapRef = useRef(null)
  const [selectedSiteId, setSelectedSiteId] = useState(null)
  const [popupCoord, setPopupCoord] = useState(null)
  const [reserveZones, setReserveZones] = useState(null)
  const [structuralLines, setStructuralLines] = useState(null)
  const [zonesStatus, setZonesStatus] = useState('loading')

  const selectedSite = SAMPLE_SITES.find((site) => site.id === selectedSiteId)

  // Load Reserve Zones GeoJSON
  useEffect(() => {
    let cancelled = false

    async function loadReserveZones() {
      try {
        const data = await getReserveZones()
        if (!cancelled) {
          setReserveZones(data)
          setZonesStatus('ready')
        }
      } catch {
        if (!cancelled) setZonesStatus('error')
      }
    }

    loadReserveZones()
    return () => {
      cancelled = true
    }
  }, [])

  // Load Structural Lineaments GeoJSON (Day 4)
  useEffect(() => {
    let cancelled = false

    async function loadStructuralLines() {
      try {
        const res = await fetch('/structural_lines.geojson')
        if (res.ok) {
          const data = await res.json()
          if (!cancelled) setStructuralLines(data)
        }
      } catch (err) {
        console.warn('[MineMap] Failed to load structural_lines.geojson:', err)
      }
    }

    loadStructuralLines()
    return () => {
      cancelled = true
    }
  }, [])

  // Smooth Fly-To effect when flyToTarget changes (Day 4)
  useEffect(() => {
    if (flyToTarget && mapRef.current) {
      // Part 7.2 — 1.2 s eased transition to the selected site's boundary.
      mapRef.current.flyTo({
        center: [flyToTarget.longitude, flyToTarget.latitude],
        zoom: flyToTarget.zoom ?? 10.5,
        duration: 1200,
        essential: true,
      })
      if (flyToTarget.id) {
        setSelectedSiteId(flyToTarget.id)
        setPopupCoord([flyToTarget.longitude, flyToTarget.latitude])
      }
    }
  }, [flyToTarget])

  function handleMapClick(event) {
    // PART 7.10 — a click on a prospectivity grid cell opens its detail panel.
    // Checked first so cells stay selectable when the surface covers other layers.
    const cellFeature = event.features?.find((f) => f.layer.id === PROSPECTIVITY_FILL_LAYER_ID)
    if (cellFeature && onProspectivityCellSelect && !crossSectionActive) {
      onProspectivityCellSelect(cellFeature.properties)
      return
    }

    // 1. Cross-Section Tool Active: capture clicked coordinate and open drawer
    if (crossSectionActive && onSelectCrossSectionPoint) {
      const { lng, lat } = event.lngLat
      const zoneFeature = event.features?.find(
        (feature) => feature.layer.id === RESERVE_ZONES_FILL_LAYER_ID
      )
      onSelectCrossSectionPoint({
        lat,
        lng,
        zoneName: zoneFeature?.properties?.zone_name,
        site_id: zoneFeature?.properties?.site_id,
      })
      return
    }

    // 2. Click on Site Cluster: zoom in to expand
    const clusterFeature = event.features?.find((f) => f.layer.id === CLUSTERS_LAYER_ID)
    if (clusterFeature) {
      const clusterId = clusterFeature.properties.cluster_id
      const source = mapRef.current?.getSource(SITES_SOURCE_ID)
      if (source && typeof source.getClusterExpansionZoom === 'function') {
        source.getClusterExpansionZoom(clusterId, (err, zoom) => {
          if (err) return
          mapRef.current?.easeTo({
            center: clusterFeature.geometry.coordinates,
            zoom: zoom + 1,
            duration: 600,
          })
        })
      }
      return
    }

    // 3. Click on Unclustered Site Marker: select site & open popup
    const siteFeature = event.features?.find((f) => f.layer.id === UNCLUSTERED_POINT_LAYER_ID)
    if (siteFeature) {
      const siteId = siteFeature.properties.id
      setSelectedSiteId(siteId)
      setPopupCoord(siteFeature.geometry.coordinates)
      onZoneSelect(null)
      return
    }

    // 4. Click on Reserve Zone: select zone & open ZoneDetailPanel
    const zoneFeature = event.features?.find(
      (feature) => feature.layer.id === RESERVE_ZONES_FILL_LAYER_ID
    )
    if (zoneFeature && prospectivityVisible) {
      onZoneSelect(zoneFeature.properties)
      setSelectedSiteId(null)
      return
    }

    // Default: clear selection
    setSelectedSiteId(null)
    onZoneSelect(null)
  }

  function handleMouseMove(event) {
    const canvas = event.target.getCanvas()
    if (crossSectionActive) {
      canvas.style.cursor = 'crosshair'
      return
    }
    const overInteractive =
      event.features?.some(
        (f) =>
          f.layer.id === RESERVE_ZONES_FILL_LAYER_ID ||
          f.layer.id === CLUSTERS_LAYER_ID ||
          f.layer.id === UNCLUSTERED_POINT_LAYER_ID ||
          f.layer.id === PROSPECTIVITY_FILL_LAYER_ID
      )
    canvas.style.cursor = overInteractive ? 'pointer' : ''
  }

  const interactiveLayerIds = useMemo(() => {
    const ids = [CLUSTERS_LAYER_ID, UNCLUSTERED_POINT_LAYER_ID]
    if (prospectivityVisible && reserveZones) {
      ids.push(RESERVE_ZONES_FILL_LAYER_ID)
    }
    if (prospectivityData) {
      ids.push(PROSPECTIVITY_FILL_LAYER_ID)
    }
    return ids
  }, [prospectivityVisible, reserveZones, prospectivityData])

  return (
    <div className="relative h-full w-full">
      <Map
        ref={mapRef}
        initialViewState={{
          longitude: MAP_CENTER.longitude,
          latitude: MAP_CENTER.latitude,
          zoom: MAP_ZOOM,
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLE}
        interactiveLayerIds={interactiveLayerIds}
        onClick={handleMapClick}
        onMouseMove={handleMouseMove}
      >
        {/* Spectral Alteration ImageSource + Raster Layer */}
        <Source
          id={SPECTRAL_LAYER_CONFIG.sourceId}
          type="image"
          url={SPECTRAL_LAYER_CONFIG.url}
          coordinates={SPECTRAL_LAYER_CONFIG.coordinates}
        >
          <Layer
            id={SPECTRAL_LAYER_CONFIG.layerId}
            type="raster"
            paint={{ 'raster-opacity': rasterOpacity, 'raster-fade-duration': 200 }}
            layout={{
              visibility: spectralVisible ? 'visible' : 'none',
            }}
          />
        </Source>

        {/* Drone DSM / UAV Orthomosaic ImageSource + Raster Layer */}
        <Source
          id={DRONE_LAYER_CONFIG.sourceId}
          type="image"
          url={DRONE_LAYER_CONFIG.url}
          coordinates={DRONE_LAYER_CONFIG.coordinates}
        >
          <Layer
            id={DRONE_LAYER_CONFIG.layerId}
            type="raster"
            paint={{ 'raster-opacity': rasterOpacity, 'raster-fade-duration': 200 }}
            layout={{
              visibility: droneVisible ? 'visible' : 'none',
            }}
          />
        </Source>

        {/* 4 Weekly NDVI ImageSource + Raster Layers */}
        {NDVI_TIMESERIES_CONFIG.map((week) => (
          <Source
            key={week.id}
            id={`source-${week.id}`}
            type="image"
            url={week.url}
            coordinates={week.coordinates}
          >
            <Layer
              id={`layer-${week.id}`}
              type="raster"
              paint={{ 'raster-opacity': rasterOpacity, 'raster-fade-duration': 200 }}
              layout={{
                visibility:
                  ndviVisible && selectedWeek === week.week_index
                    ? 'visible'
                    : 'none',
              }}
            />
          </Source>
        ))}

        {/* PART 7.2/7.3/7.4 — Per-site prospectivity surface. Rendered ONLY when a
            site has been selected and its GeoJSON loaded (7.1 keeps the default
            view free of any heatmap). */}
        {prospectivityData && (
          <Source id={PROSPECTIVITY_SOURCE_ID} type="geojson" data={prospectivityData}>
            {/* 7.3 — flat discrete band colors, no gradient, no blur. Cells carry
                the per-cell properties the 7.10 detail panel reads on click.
                7.5 — opacity from the shared slider so the basemap's roads and
                place names stay legible underneath. */}
            <Layer
              id={PROSPECTIVITY_FILL_LAYER_ID}
              type="fill"
              paint={{ ...PROSPECTIVITY_FILL_PAINT, 'fill-opacity': rasterOpacity }}
            />
          </Source>
        )}

        {/* Dissolved band polygons: outlines only. Kept in a separate source so
            the hairline follows band boundaries rather than every cell edge. */}
        {prospectivityBands && (
          <Source id={PROSPECTIVITY_BANDS_SOURCE_ID} type="geojson" data={prospectivityBands}>
            {/* 7.4 — blurred stroke along the dissolved outer ring only. */}
            <Layer id={PROSPECTIVITY_EDGE_LAYER_ID} type="line" paint={PROSPECTIVITY_EDGE_PAINT} />
            {/* 7.3 — crisp hairline where two bands meet. */}
            <Layer id={PROSPECTIVITY_BOUNDARY_LAYER_ID} type="line" paint={PROSPECTIVITY_BOUNDARY_PAINT} />
          </Source>
        )}

        {/* Structural Lineament Vector Layer (Day 4) */}
        {structuralLines && (
          <Source id={STRUCTURAL_LINES_SOURCE_ID} type="geojson" data={structuralLines}>
            <Layer
              id={STRUCTURAL_LINES_LAYER_ID}
              type="line"
              minzoom={STRUCTURAL_LINES_MIN_ZOOM}
              paint={STRUCTURAL_LINE_PAINT}
              layout={{
                visibility: lineamentVisible ? 'visible' : 'none',
                'line-join': 'round',
                'line-cap': 'round',
              }}
            />
          </Source>
        )}

        {/* Reserve Zones GeoJSON Heatmap Fill Layer */}
        {reserveZones && (
          <Source id={RESERVE_ZONES_SOURCE_ID} type="geojson" data={reserveZones}>
            <Layer
              id={RESERVE_ZONES_FILL_LAYER_ID}
              type="fill"
              paint={RESERVE_ZONE_FILL_PAINT}
              layout={{
                visibility: prospectivityVisible ? 'visible' : 'none',
              }}
            />
          </Source>
        )}

        {/* Clustered Site Markers (Day 4) */}
        <Source
          id={SITES_SOURCE_ID}
          type="geojson"
          data={SITES_GEOJSON}
          cluster={true}
          clusterMaxZoom={8}
          clusterRadius={45}
        >
          {/* Soft shadow beneath individual site markers for legibility over overlays */}
          <Layer
            id={SITE_MARKER_SHADOW_LAYER_ID}
            type="circle"
            filter={['!', ['has', 'point_count']]}
            paint={SITE_MARKER_SHADOW_PAINT}
          />

          {/* Cluster Circles */}
          <Layer
            id={CLUSTERS_LAYER_ID}
            type="circle"
            filter={['has', 'point_count']}
            paint={{
              'circle-color': '#e0793a',
              'circle-radius': ['step', ['get', 'point_count'], 16, 2, 20, 5, 26],
              'circle-stroke-width': 2.5,
              'circle-stroke-color': '#ffffff',
            }}
          />

          {/* Cluster Count Numbers */}
          <Layer
            id={CLUSTER_COUNT_LAYER_ID}
            type="symbol"
            filter={['has', 'point_count']}
            layout={{
              'text-field': '{point_count_abbreviated}',
              'text-size': 12,
            }}
            paint={{
              'text-color': '#ffffff',
            }}
          />

          {/* Unclustered Individual Mine Points */}
          <Layer
            id={UNCLUSTERED_POINT_LAYER_ID}
            type="circle"
            filter={['!', ['has', 'point_count']]}
            paint={{
              'circle-color': '#e0793a',
              'circle-radius': 8,
              'circle-stroke-width': 2.5,
              'circle-stroke-color': '#ffffff',
            }}
          />
        </Source>

        {/* Cross-Section Sampling Pin (Day 4) */}
        {crossSectionPoint && (
          <Marker
            longitude={crossSectionPoint.lng ?? crossSectionPoint.longitude}
            latitude={crossSectionPoint.lat ?? crossSectionPoint.latitude}
            anchor="center"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-teal text-white shadow-xl ring-4 ring-teal/30 animate-pulse">
              <Activity size={15} />
            </div>
          </Marker>
        )}

        {/* Selected Site Popup */}
        {selectedSite && (
          <Popup
            longitude={popupCoord ? popupCoord[0] : selectedSite.longitude}
            latitude={popupCoord ? popupCoord[1] : selectedSite.latitude}
            anchor="bottom"
            offset={[0, -12]}
            closeButton
            closeOnClick={false}
            onClose={() => {
              setSelectedSiteId(null)
              setPopupCoord(null)
            }}
          >
            <div className="p-1">
              <p className="font-heading text-sm font-bold text-navy">{selectedSite.name} Mine</p>
              <p className="text-[11px] text-slate-500 font-medium">MOIL Manganese Belt</p>
              <p className="text-[10px] text-text-muted mt-0.5">
                {selectedSite.latitude.toFixed(3)}°N, {selectedSite.longitude.toFixed(3)}°E
              </p>
            </div>
          </Popup>
        )}
      </Map>

      {/* Floating Cross-Section Tool Button (Day 4) */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleCrossSection}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-[3px] text-xs font-semibold shadow-xs transition-all duration-150 border cursor-pointer ${
            crossSectionActive
              ? 'bg-teal text-white border-teal ring-2 ring-teal/30'
              : 'bg-bg-surface text-navy border-border hover:bg-bg hover:text-teal'
          }`}
        >
          <Activity size={15} className={crossSectionActive ? 'text-white' : 'text-teal'} />
          <span>{crossSectionActive ? 'Cross-Section Active: Click Map' : 'Cross-Section Tool'}</span>
        </button>
      </div>

      {/* Legend + NDVI time slider share one bottom row via flexbox so they can
          never overlap: they lay out in normal flow at opposite ends of the
          same container and wrap onto their own line if the map is too
          narrow to fit both side by side. */}
      <div className="pointer-events-none absolute inset-x-4 bottom-4 z-10 flex flex-wrap items-end gap-3">
        <NdviTimeSlider
          visible={ndviVisible}
          selectedWeek={selectedWeek}
          onWeekChange={onWeekChange}
        />
        {/* ml-auto pushes the legend to the right edge whether or not the
            slider above is currently rendered, so it never jumps to the
            left when NDVI is off. */}
        <div className="ml-auto">
          <ConfidenceLegend
            prospectivityVisible={prospectivityVisible}
            lineamentVisible={lineamentVisible}
            spectralVisible={spectralVisible}
            droneVisible={droneVisible}
            ndviVisible={ndviVisible}
          />
        </div>
      </div>

      {zonesStatus === 'loading' && (
        <div className="absolute left-4 top-16 z-10 flex items-center gap-2 rounded-[3px] border border-border bg-bg-surface px-3 py-2 text-xs text-text-secondary shadow-xs">
          <Loader2 size={14} className="shrink-0 animate-spin text-teal" />
          Loading reserve zones…
        </div>
      )}

      {zonesStatus === 'error' && (
        <div className="absolute left-4 top-16 z-10 rounded-[3px] border border-danger/30 bg-bg-surface px-3 py-2 text-xs text-danger shadow-xs">
          Unable to load reserve zones from the backend.
        </div>
      )}
    </div>
  )
}
