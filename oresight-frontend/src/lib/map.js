// Map configuration for the MOIL manganese belt (P4 Day 1).

// Muted, low-saturation basemap so semi-transparent data overlays (NDVI,
// spectral alteration, reserve confidence) stay legible against it — a
// bright/colorful basemap competes with the data layers drawn on top of it.
export const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron'

export const MAP_ZOOM = 7

// Centered on the Balaghat / Nagpur / Bhandara belt
export const MAP_CENTER = {
  latitude: 21.367,
  longitude: 79.633,
}

export const SAMPLE_SITES = [
  { id: 'balaghat', name: 'Balaghat', latitude: 21.8, longitude: 80.2 },
  { id: 'nagpur', name: 'Nagpur', latitude: 21.1, longitude: 79.1 },
  { id: 'bhandara', name: 'Bhandara', latitude: 21.2, longitude: 79.6 },
]

export const MAP_LAYERS = [
  { id: 'prospectivity', label: 'Prospectivity Heatmap' },
  { id: 'spectral', label: 'Spectral Alteration' },
  { id: 'lineament', label: 'Structural Lineament' },
  { id: 'dsm', label: 'Drone DSM' },
  { id: 'ndvi', label: 'NDVI Time-Series' },
]

export const RESERVE_ZONES_SOURCE_ID = 'reserve-zones'
export const RESERVE_ZONES_FILL_LAYER_ID = 'reserve-zones-fill'

export const CONFIDENCE_COLOR_RAMP = {
  low: '#c0392b',
  mid: '#e0793a',
  high: '#3f8f5f',
}

export const RESERVE_ZONE_FILL_PAINT = {
  'fill-color': [
    'interpolate',
    ['linear'],
    ['get', 'confidence_score'],
    0,
    CONFIDENCE_COLOR_RAMP.low,
    0.5,
    CONFIDENCE_COLOR_RAMP.mid,
    1,
    CONFIDENCE_COLOR_RAMP.high,
  ],
  'fill-opacity': 0.65,
}

// P4 Day 4: Structural Lineament Layer Configuration
export const STRUCTURAL_LINES_SOURCE_ID = 'structural-lines'
export const STRUCTURAL_LINES_LAYER_ID = 'structural-lines-layer'

export const STRUCTURAL_LINE_COLORS = {
  fault: '#ef4444',       // vibrant red
  shear_zone: '#f59e0b',  // warm amber
  fold_axis: '#8b5cf6',   // deep violet
  default: '#3b82f6',     // operational blue
}

// Structural lineaments span the whole mining belt, so at a zoomed-out view
// their short segments render as an illegible scatter of tiny marks. Fade
// them in and thicken them as the user zooms in, rather than showing
// everything at once regardless of scale.
export const STRUCTURAL_LINE_PAINT = {
  'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 10, 1.75, 13, 3],
  'line-color': [
    'match',
    ['get', 'structure_type'],
    'fault', STRUCTURAL_LINE_COLORS.fault,
    'shear_zone', STRUCTURAL_LINE_COLORS.shear_zone,
    'fold_axis', STRUCTURAL_LINE_COLORS.fold_axis,
    STRUCTURAL_LINE_COLORS.default,
  ],
  'line-opacity': ['interpolate', ['linear'], ['zoom'], 7.5, 0, 9, 0.9],
}

// Below this zoom the lineament layer is fully faded out (see line-opacity
// above); skipping rendering entirely below it avoids paying for a layer
// nobody can read yet.
export const STRUCTURAL_LINES_MIN_ZOOM = 7.5

// P4 Day 4: Site Clustering Configuration
export const SITES_SOURCE_ID = 'sites-source'
export const CLUSTERS_LAYER_ID = 'clusters'
export const CLUSTER_COUNT_LAYER_ID = 'cluster-count'
export const UNCLUSTERED_POINT_LAYER_ID = 'unclustered-point'
export const SITE_MARKER_SHADOW_LAYER_ID = 'site-marker-shadow'
export const SITE_MARKER_COLOR = '#e0793a'

// Soft blurred halo drawn beneath the site markers so they read clearly
// against both light basemap and dark overlay colors underneath them.
export const SITE_MARKER_SHADOW_PAINT = {
  'circle-color': '#000000',
  'circle-opacity': 0.22,
  'circle-radius': 11,
  'circle-blur': 0.9,
  'circle-translate': [0, 1.5],
}

// Raster overlays default to a partial opacity so basemap roads/labels stay
// visible underneath the data layer, rather than fully obscuring it.
export const DEFAULT_RASTER_OPACITY = 0.6

// ---------------------------------------------------------------------------
// PART 7 — Per-site prospectivity surface (from prospectivity/classify_export.py)
// ---------------------------------------------------------------------------
export const PROSPECTIVITY_SOURCE_ID = 'prospectivity-source'
export const PROSPECTIVITY_FILL_LAYER_ID = 'prospectivity-fill'
export const PROSPECTIVITY_BOUNDARY_LAYER_ID = 'prospectivity-band-boundary'
export const PROSPECTIVITY_EDGE_LAYER_ID = 'prospectivity-edge-feather'

export const CONFIDENCE_BANDS = ['Very Low', 'Low', 'Moderate', 'High', 'Very High']

// Part 7.3 — five DISCRETE flat colors, no gradient. These follow the semantic
// already established by CONFIDENCE_COLOR_RAMP (red = low confidence, green =
// high) and are interpolated from those same three anchors, so the app's
// existing palette is extended rather than replaced.
export const CONFIDENCE_BAND_COLORS = {
  'Very Low': '#8c2f22',
  'Low': '#c0392b',
  'Moderate': '#e0793a',
  'High': '#7a9a52',
  'Very High': '#3f8f5f',
}

// Part 7.3 — flat fill keyed off the discrete band, never an interpolation.
export const PROSPECTIVITY_FILL_PAINT = {
  'fill-color': [
    'match',
    ['get', 'confidence_band'],
    'Very Low', CONFIDENCE_BAND_COLORS['Very Low'],
    'Low', CONFIDENCE_BAND_COLORS['Low'],
    'Moderate', CONFIDENCE_BAND_COLORS['Moderate'],
    'High', CONFIDENCE_BAND_COLORS['High'],
    'Very High', CONFIDENCE_BAND_COLORS['Very High'],
    '#999999',
  ],
  'fill-opacity': 1,
  // MapLibre defaults `fill-outline-color` to `fill-color`, which strokes EVERY
  // cell and renders the surface as a graph-paper mesh (confirmed in-browser).
  // Force it transparent so adjacent same-band cells merge into one flat area
  // and the only visible boundary is the dissolved band outline drawn above.
  'fill-outline-color': 'rgba(0,0,0,0)',
}

// Part 7.3 — subtle hairline drawn ONLY where two bands meet. This is applied
// to the dissolved band polygons (*_bands.geojson), never per-cell: stroking
// every 300 m cell produces a graph-paper mesh across the whole surface
// (confirmed in-browser) rather than a band boundary.
export const PROSPECTIVITY_BOUNDARY_PAINT = {
  'line-color': 'rgba(26,24,21,0.35)',
  'line-width': 0.8,
}

// Part 7.4 — the ONLY place softness is correct: a blurred stroke following the
// dissolved surface's outer ring, so it fades into the basemap instead of
// terminating on a hard rectangular cut. Interior band colors stay crisp.
export const PROSPECTIVITY_EDGE_PAINT = {
  'line-color': 'rgba(26,24,21,0.22)',
  'line-width': 14,
  'line-blur': 16,
}

export const PROSPECTIVITY_BANDS_SOURCE_ID = 'prospectivity-bands-source'

export function prospectivityUrl(siteId) {
  return `/prospectivity/${siteId}.geojson`
}

export function prospectivityBandsUrl(siteId) {
  return `/prospectivity/${siteId}_bands.geojson`
}
export const MIN_RASTER_OPACITY = 0.25
export const MAX_RASTER_OPACITY = 0.95

export const SITES_GEOJSON = {
  type: 'FeatureCollection',
  features: SAMPLE_SITES.map((site) => ({
    type: 'Feature',
    properties: {
      id: site.id,
      name: site.name,
    },
    geometry: {
      type: 'Point',
      coordinates: [site.longitude, site.latitude],
    },
  })),
}


// P6 Raster Layer Configurations (from gis/tiles/manifest.json)
export const SPECTRAL_LAYER_CONFIG = {
  sourceId: 'spectral-alteration-source',
  layerId: 'spectral-alteration-layer',
  url: '/tiles/iron_oxide_latest.png',
  date: '2026-08-31',
  coordinates: [
    [78.5, 22.25],
    [80.8, 22.25],
    [80.8, 20.9],
    [78.5, 20.9],
  ],
}

export const DRONE_LAYER_CONFIG = {
  sourceId: 'drone-dsm-source',
  layerId: 'drone-dsm-layer',
  url: '/tiles/odm_orthophoto.png',
  date: '2026-08-30',
  coordinates: [
    [80.215, 21.885],
    [80.235, 21.885],
    [80.235, 21.865],
    [80.215, 21.865],
  ],
}

export const NDVI_TIMESERIES_CONFIG = [
  {
    week_index: 1,
    id: 'ndvi-week-1',
    name: 'NDVI Week 1',
    date: '2026-08-10',
    window_start: '2026-08-03',
    window_end: '2026-08-10',
    url: '/tiles/ndvi_week_1.png',
    coordinates: [
      [78.5, 22.25],
      [80.8, 22.25],
      [80.8, 20.9],
      [78.5, 20.9],
    ],
  },
  {
    week_index: 2,
    id: 'ndvi-week-2',
    name: 'NDVI Week 2',
    date: '2026-08-17',
    window_start: '2026-08-10',
    window_end: '2026-08-17',
    url: '/tiles/ndvi_week_2.png',
    coordinates: [
      [78.5, 22.25],
      [80.8, 22.25],
      [80.8, 20.9],
      [78.5, 20.9],
    ],
  },
  {
    week_index: 3,
    id: 'ndvi-week-3',
    name: 'NDVI Week 3',
    date: '2026-08-24',
    window_start: '2026-08-17',
    window_end: '2026-08-24',
    url: '/tiles/ndvi_week_3.png',
    coordinates: [
      [78.5, 22.25],
      [80.8, 22.25],
      [80.8, 20.9],
      [78.5, 20.9],
    ],
  },
  {
    week_index: 4,
    id: 'ndvi-week-4',
    name: 'NDVI Week 4',
    date: '2026-08-31',
    window_start: '2026-08-24',
    window_end: '2026-08-31',
    url: '/tiles/ndvi_week_4.png',
    coordinates: [
      [78.5, 22.25],
      [80.8, 22.25],
      [80.8, 20.9],
      [78.5, 20.9],
    ],
  },
]
