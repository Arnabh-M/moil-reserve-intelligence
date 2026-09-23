// Display tiers for a reserve-zone confidence score. PURE DISPLAY: nothing here
// changes any stored or computed score.
//
// Thresholds are taken from the real distribution of the per-cell
// ensemble_confidence_score in public/prospectivity/*.geojson (12,934 cells):
//   0.25 ~ 57th percentile, 0.40 ~ 83rd percentile
//   => ~57% of cells "lower", ~26% "medium", ~17% "higher".
// The old 0.4 / 0.7 cut points assumed a 0-1 spread the trained models never
// produce (max cell 0.87, zone means 0.20-0.41), so no zone could ever be green.
// backend/tests/test_confidence_badge_thresholds.py pins these numbers and fails
// if a change to the score distribution makes every zone land in one tier.
//
// Labels are deliberately modest: the score is an ensemble agreement index on
// synthetic labels, a relative prioritisation signal, NOT a probability of ore.
export const CONFIDENCE_TIER_THRESHOLDS = { medium: 0.25, higher: 0.4 }

export const CONFIDENCE_TIERS = {
  higher: { key: 'higher', label: 'Higher priority', badgeVariant: 'operational', barClass: 'bg-success' },
  medium: { key: 'medium', label: 'Medium priority', badgeVariant: 'warning', barClass: 'bg-warning' },
  lower: { key: 'lower', label: 'Lower priority', badgeVariant: 'critical', barClass: 'bg-danger' },
}

export function confidenceTier(score) {
  if (score >= CONFIDENCE_TIER_THRESHOLDS.higher) return CONFIDENCE_TIERS.higher
  if (score >= CONFIDENCE_TIER_THRESHOLDS.medium) return CONFIDENCE_TIERS.medium
  return CONFIDENCE_TIERS.lower
}
