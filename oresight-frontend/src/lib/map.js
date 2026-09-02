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
