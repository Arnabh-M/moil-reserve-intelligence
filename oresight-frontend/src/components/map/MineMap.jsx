import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, Loader2, Mountain, Sun } from 'lucide-react'
import Map, { Layer, Marker, Popup, Source } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { api } from '../../api/client'
import {
  MAP_CENTER,
  MAP_STYLE,
  BASEMAP_STYLES,
  TERRAIN_DEM_SOURCE,
  MAP_ATTRIBUTION,
  MAP_ZOOM,
  REGIONAL_BOUNDS,
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
  onSiteSelect = null,
  flyToTarget = null,
  selectedSiteId: selectedSiteIdProp = null,
  crossSectionActive = false,
  onToggleCrossSection,
  onSelectCrossSectionPoint,
  crossSectionPoint = null,
  rasterOpacity = DEFAULT_RASTER_OPACITY,
  prospectivityData = null,
  prospectivityBands = null,
  onProspectivityCellSelect,
  basemapMode: basemapModeProp = null,
  onBasemapModeChange = null,
}) {
  const mapRef = useRef(null)
  const [internalBasemapMode, setInternalBasemapMode] = useState('light')
  const basemapMode = basemapModeProp ?? internalBasemapMode

  function handleBasemapChange(mode) {
    setInternalBasemapMode(mode)
    if (onBasemapModeChange) onBasemapModeChange(mode)
  }

  const [selectedSiteIdState, setSelectedSiteIdState] = useState(null)
  const effectiveSiteId = selectedSiteIdProp ?? selectedSiteIdState
  const [popupCoord, setPopupCoord] = useState(null)
  const [reserveZones, setReserveZones] = useState(null)
  const [structuralLines, setStructuralLines] = useState(null)
  const [zonesStatus, setZonesStatus] = useState('loading')

  const selectedSite = SAMPLE_SITES.find((site) => site.id === effectiveSiteId)

  // On mount, frame the 3-area regional operational extent (Part 5)
  const initialFramedRef = useRef(false)
  const onMapLoad = () => {
    if (!initialFramedRef.current && !flyToTarget?.id && mapRef.current) {
      initialFramedRef.current = true
      mapRef.current.fitBounds(REGIONAL_BOUNDS, {
        padding: 60,
        duration: 0,
        essential: true,
      })
    }
  }

  // Load Reserve Zones GeoJSON
  useEffect(() => {
    let cancelled = false

    async function loadReserveZones() {
      try {
        const data = await api.getReserveZones()
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

  // Smooth Fly-To / Fit-Bounds effect when flyToTarget changes (Day 4 & P2 Single-Mine Focus)
  useEffect(() => {
    if (flyToTarget && mapRef.current) {
      if (flyToTarget.bounds) {
        // Fit bounds for precise site extent
        mapRef.current.fitBounds(flyToTarget.bounds, {
          padding: 60,
          duration: 1200,
          essential: true,
        })
      } else {
        // Fallback or regional reset flyTo
        mapRef.current.flyTo({
          center: [flyToTarget.longitude, flyToTarget.latitude],
          zoom: flyToTarget.zoom ?? 10.5,
          duration: 1200,
          essential: true,
        })
      }
      setSelectedSiteIdState(flyToTarget.id || null)
      if (flyToTarget.id) {
        setPopupCoord([flyToTarget.longitude, flyToTarget.latitude])
      } else {
        setPopupCoord(null)
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

    // 3. Click on Unclustered Site Marker: select site & trigger single-mine focus (Part 6)
    const siteFeature = event.features?.find((f) => f.layer.id === UNCLUSTERED_POINT_LAYER_ID)
    if (siteFeature) {
      const siteId = siteFeature.properties.id
      setSelectedSiteIdState(siteId)
      setPopupCoord(siteFeature.geometry.coordinates)
      onZoneSelect(null)
      if (onSiteSelect) {
        onSiteSelect(siteId)
      }
      return
    }

    // 4. Click on Reserve Zone: select zone & open ZoneDetailPanel
    const zoneFeature = event.features?.find(
      (feature) => feature.layer.id === RESERVE_ZONES_FILL_LAYER_ID
    )
    if (zoneFeature && prospectivityVisible) {
      onZoneSelect(zoneFeature.properties)
      setSelectedSiteIdState(null)
      return
    }

    // Default: clear selection
    setSelectedSiteIdState(null)
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

  // Priority 3 & Final Polish: Overlay separation & visual hierarchy
  // Balance raster opacity when multiple full-extent layers are active
  const effectiveRasterOpacity = useMemo(() => {
    if (spectralVisible && ndviVisible) {
      return Math.max(0.2, rasterOpacity * 0.7)
    }
    return rasterOpacity
  }, [spectralVisible, ndviVisible, rasterOpacity])

  // Restrain supporting raster opacity so they serve as gentle background context without overpowering prospectivity
  const supportingRasterOpacity = useMemo(() => {
    // If primary prospectivity surface is active for a site, keep supporting rasters subtle (capped at 0.32)
    if (prospectivityVisible && prospectivityData) {
      const base =
        spectralVisible && ndviVisible
          ? Math.max(0.18, rasterOpacity * 0.42)
          : Math.max(0.2, rasterOpacity * 0.48)
      return Math.min(0.32, base)
    }
    return effectiveRasterOpacity
  }, [spectralVisible, ndviVisible, prospectivityVisible, prospectivityData, rasterOpacity, effectiveRasterOpacity])

  // Ensure primary prospectivity surface maintains prominent analytical visual weight
  const prospectivityFillOpacity = useMemo(() => {
    return Math.min(0.88, Math.max(0.65, rasterOpacity))
  }, [rasterOpacity])

  const interactiveLayerIds = useMemo(() => {
    const ids = [CLUSTERS_LAYER_ID, UNCLUSTERED_POINT_LAYER_ID]
    if (prospectivityVisible && reserveZones && !prospectivityData) {
      ids.push(RESERVE_ZONES_FILL_LAYER_ID)
    }
    if (prospectivityVisible && prospectivityData) {
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
        mapStyle={BASEMAP_STYLES[basemapMode] || MAP_STYLE}
        attributionControl={false}
        interactiveLayerIds={interactiveLayerIds}
        onClick={handleMapClick}
        onMouseMove={handleMouseMove}
        onLoad={onMapLoad}
      >
        {/* Real Terrain DEM Hillshade (AWS Open Data Terrarium, active in Terrain mode) */}
        {basemapMode === 'terrain' && (
          <Source
            id={TERRAIN_DEM_SOURCE.id}
            type={TERRAIN_DEM_SOURCE.type}
            tiles={TERRAIN_DEM_SOURCE.tiles}
            encoding={TERRAIN_DEM_SOURCE.encoding}
            tileSize={TERRAIN_DEM_SOURCE.tileSize}
            maxzoom={TERRAIN_DEM_SOURCE.maxzoom}
          >
            <Layer
              id="terrain-hillshade"
              type="hillshade"
              paint={{
                'hillshade-exaggeration': 0.35,
                'hillshade-shadow-color': '#1e293b',
                'hillshade-highlight-color': '#ffffff',
                'hillshade-accent-color': '#475569',
              }}
            />
          </Source>
        )}

        {/* Supporting Raster 1: Spectral Alteration (Restrained background when prospectivity is active) */}
        <Source
          id={SPECTRAL_LAYER_CONFIG.sourceId}
          type="image"
          url={SPECTRAL_LAYER_CONFIG.url}
          coordinates={SPECTRAL_LAYER_CONFIG.coordinates}
        >
          <Layer
            id={SPECTRAL_LAYER_CONFIG.layerId}
            type="raster"
            paint={{
              'raster-opacity': supportingRasterOpacity,
              'raster-resampling': 'linear',
              'raster-fade-duration': 200,
            }}
            layout={{
              visibility: spectralVisible ? 'visible' : 'none',
            }}
          />
        </Source>

        {/* Supporting Raster 2: Drone DSM (Spatially localized to Balaghat Bharweli pit) */}
        <Source
          id={DRONE_LAYER_CONFIG.sourceId}
          type="image"
          url={DRONE_LAYER_CONFIG.url}
          coordinates={DRONE_LAYER_CONFIG.coordinates}
        >
          <Layer
            id={DRONE_LAYER_CONFIG.layerId}
            type="raster"
            paint={{
              'raster-opacity': rasterOpacity,
              'raster-resampling': 'linear',
              'raster-fade-duration': 200,
            }}
            layout={{
              visibility:
                droneVisible && (!effectiveSiteId || effectiveSiteId === 'balaghat' || effectiveSiteId === 1)
                  ? 'visible'
                  : 'none',
            }}
          />
        </Source>

        {/* Supporting Raster 3: Weekly NDVI Timeseries (Restrained background when prospectivity is active) */}
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
              paint={{
                'raster-opacity': supportingRasterOpacity,
                'raster-resampling': 'linear',
                'raster-fade-duration': 200,
              }}
              layout={{
                visibility:
                  ndviVisible && selectedWeek === week.week_index
                    ? 'visible'
                    : 'none',
              }}
            />
          </Source>
        ))}

        {/* Fallback Regional Reserve Zones (Only rendered when per-site prospectivity is not yet loaded) */}
        {reserveZones && (
          <Source id={RESERVE_ZONES_SOURCE_ID} type="geojson" data={reserveZones}>
            <Layer
              id={RESERVE_ZONES_FILL_LAYER_ID}
              type="fill"
              paint={RESERVE_ZONE_FILL_PAINT}
              filter={
                effectiveSiteId
                  ? [
                      'any',
                      ['==', ['get', 'site_id'], effectiveSiteId],
                      [
                        '==',
                        ['get', 'site_id'],
                        effectiveSiteId === 'balaghat' ? 1 : effectiveSiteId === 'nagpur' ? 2 : effectiveSiteId === 'bhandara' ? 3 : -1,
                      ],
                    ]
                  : ['literal', true]
              }
              layout={{
                visibility: prospectivityVisible && !prospectivityData ? 'visible' : 'none',
              }}
            />
          </Source>
        )}

        {/* PRIMARY ANALYTICAL SURFACE: Per-site prospectivity surface */}
        {prospectivityData && (
          <Source id={PROSPECTIVITY_SOURCE_ID} type="geojson" data={prospectivityData}>
            <Layer
              id={PROSPECTIVITY_FILL_LAYER_ID}
              type="fill"
              paint={{ ...PROSPECTIVITY_FILL_PAINT, 'fill-opacity': prospectivityFillOpacity }}
              layout={{
                visibility: prospectivityVisible ? 'visible' : 'none',
              }}
            />
          </Source>
        )}

        {/* STRUCTURAL DATA: Structural Lineament Vector Layer (Rendered crisply across prospectivity) */}
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

        {/* Dissolved band polygons: subtle hairlines and outer edge feather */}
        {prospectivityBands && (
          <Source id={PROSPECTIVITY_BANDS_SOURCE_ID} type="geojson" data={prospectivityBands}>
            <Layer
              id={PROSPECTIVITY_EDGE_LAYER_ID}
              type="line"
              paint={PROSPECTIVITY_EDGE_PAINT}
              layout={{
                visibility: prospectivityVisible ? 'visible' : 'none',
              }}
            />
            <Layer
              id={PROSPECTIVITY_BOUNDARY_LAYER_ID}
              type="line"
              paint={PROSPECTIVITY_BOUNDARY_PAINT}
              layout={{
                visibility: prospectivityVisible ? 'visible' : 'none',
              }}
            />
          </Source>
        )}

        {/* Clustered Site Markers (Day 4 & Part 5 Operational Focus) */}
        <Source
          id={SITES_SOURCE_ID}
          type="geojson"
          data={SITES_GEOJSON}
          cluster={true}
          clusterMaxZoom={7}
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

          {/* Site Name Labels for the 3 Operational Areas (Part 5) */}
          <Layer
            id="site-labels"
            type="symbol"
            filter={['!', ['has', 'point_count']]}
            layout={{
              'text-field': '{name} Mine',
              'text-size': 11,
              'text-offset': [0, 1.2],
              'text-anchor': 'top',
              'text-allow-overlap': true,
            }}
            paint={{
              'text-color': '#1a202c',
              'text-halo-color': '#ffffff',
              'text-halo-width': 2,
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
              setSelectedSiteIdState(null)
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

      {/* Floating Map Controls (Top-Left) */}
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

        {/* Basemap Toggle (Light / Terrain) */}
        <div
          className="flex items-center rounded-[3px] border border-border bg-bg-surface p-0.5 shadow-xs"
          role="group"
          aria-label="Basemap style"
        >
          <button
            type="button"
            onClick={() => handleBasemapChange('light')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-[2px] text-xs font-semibold transition-all duration-150 cursor-pointer ${
              basemapMode === 'light'
                ? 'bg-teal text-white shadow-xs'
                : 'text-slate-600 hover:text-navy hover:bg-bg'
            }`}
            title="Analytical Light Basemap (OpenFreeMap Positron)"
          >
            <Sun size={13} />
            <span>Light</span>
          </button>
          <button
            type="button"
            onClick={() => handleBasemapChange('terrain')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-[2px] text-xs font-semibold transition-all duration-150 cursor-pointer ${
              basemapMode === 'terrain'
                ? 'bg-teal text-white shadow-xs'
                : 'text-slate-600 hover:text-navy hover:bg-bg'
            }`}
            title="Topographic Terrain Basemap (OpenFreeMap Liberty + AWS Open Data Hillshade)"
          >
            <Mountain size={13} />
            <span>Terrain</span>
          </button>
        </div>
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
            selectedSiteId={effectiveSiteId}
          />
        </div>
      </div>

      {/* Required Data Source Attribution */}
      <div className="pointer-events-auto absolute bottom-1 right-4 z-10 select-none rounded-[3px] border border-border/60 bg-bg-surface/90 px-2 py-0.5 text-[10px] text-slate-500 shadow-xs backdrop-blur-xs">
        {MAP_ATTRIBUTION[basemapMode] || MAP_ATTRIBUTION.light}
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
