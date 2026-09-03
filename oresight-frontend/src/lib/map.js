// Map configuration for the MOIL manganese belt (P4 Day 1).

export const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

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

export const STRUCTURAL_LINE_PAINT = {
  'line-width': 2.5,
  'line-color': [
    'match',
    ['get', 'structure_type'],
    'fault', STRUCTURAL_LINE_COLORS.fault,
    'shear_zone', STRUCTURAL_LINE_COLORS.shear_zone,
    'fold_axis', STRUCTURAL_LINE_COLORS.fold_axis,
    STRUCTURAL_LINE_COLORS.default,
  ],
  'line-opacity': 0.9,
}

// P4 Day 4: Site Clustering Configuration
export const SITES_SOURCE_ID = 'sites-source'
export const CLUSTERS_LAYER_ID = 'clusters'
export const CLUSTER_COUNT_LAYER_ID = 'cluster-count'
export const UNCLUSTERED_POINT_LAYER_ID = 'unclustered-point'

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
