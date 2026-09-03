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
  SITES_SOURCE_ID,
  CLUSTERS_LAYER_ID,
  CLUSTER_COUNT_LAYER_ID,
  UNCLUSTERED_POINT_LAYER_ID,
  SITES_GEOJSON,
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
      mapRef.current.flyTo({
        center: [flyToTarget.longitude, flyToTarget.latitude],
        zoom: flyToTarget.zoom ?? 10.5,
        duration: 1600,
        essential: true,
      })
      if (flyToTarget.id) {
        setSelectedSiteId(flyToTarget.id)
        setPopupCoord([flyToTarget.longitude, flyToTarget.latitude])
      }
    }
  }, [flyToTarget])

  function handleMapClick(event) {
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
          f.layer.id === UNCLUSTERED_POINT_LAYER_ID
      )
    canvas.style.cursor = overInteractive ? 'pointer' : ''
  }

  const interactiveLayerIds = useMemo(() => {
    const ids = [CLUSTERS_LAYER_ID, UNCLUSTERED_POINT_LAYER_ID]
    if (prospectivityVisible && reserveZones) {
      ids.push(RESERVE_ZONES_FILL_LAYER_ID)
    }
    return ids
  }, [prospectivityVisible, reserveZones])

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
            paint={{ 'raster-opacity': 0.75 }}
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
            paint={{ 'raster-opacity': 0.85 }}
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
              paint={{ 'raster-opacity': 0.75 }}
              layout={{
                visibility:
                  ndviVisible && selectedWeek === week.week_index
                    ? 'visible'
                    : 'none',
              }}
            />
          </Source>
        ))}

        {/* Structural Lineament Vector Layer (Day 4) */}
        {structuralLines && (
          <Source id={STRUCTURAL_LINES_SOURCE_ID} type="geojson" data={structuralLines}>
            <Layer
              id={STRUCTURAL_LINES_LAYER_ID}
              type="line"
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
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold shadow-md transition-all duration-150 border backdrop-blur-md cursor-pointer ${
            crossSectionActive
              ? 'bg-teal text-white border-teal ring-2 ring-teal/30 shadow-teal/20'
              : 'bg-bg-surface/95 text-navy border-border hover:bg-bg hover:text-teal'
          }`}
        >
          <Activity size={15} className={crossSectionActive ? 'text-white' : 'text-teal'} />
          <span>{crossSectionActive ? 'Cross-Section Active: Click Map' : 'Cross-Section Tool'}</span>
        </button>
      </div>

      {/* Upgraded Multi-Layer Collapsible Legend (Day 4) */}
      <ConfidenceLegend
        prospectivityVisible={prospectivityVisible}
        lineamentVisible={lineamentVisible}
        spectralVisible={spectralVisible}
        droneVisible={droneVisible}
        ndviVisible={ndviVisible}
      />

      {/* 4-Week NDVI Time Slider */}
      <NdviTimeSlider
        visible={ndviVisible}
        selectedWeek={selectedWeek}
        onWeekChange={onWeekChange}
      />

      {zonesStatus === 'loading' && (
        <div className="absolute left-4 top-16 z-10 flex items-center gap-2 rounded-xl border border-border bg-bg-surface/95 px-3 py-2 text-xs text-text-secondary shadow-lg backdrop-blur-md">
          <Loader2 size={14} className="shrink-0 animate-spin text-teal" />
          Loading reserve zones…
        </div>
      )}

      {zonesStatus === 'error' && (
        <div className="absolute left-4 top-16 z-10 rounded-xl border border-danger/30 bg-bg-surface/95 px-3 py-2 text-xs text-danger shadow-lg backdrop-blur-md">
          Unable to load reserve zones from the backend.
        </div>
      )}
    </div>
  )
}
