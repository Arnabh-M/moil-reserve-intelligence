// Site payloads aren't guaranteed to carry a reserve-confidence field yet,
// so this derives a stable mock value per site when one is missing —
// the same site always yields the same value.
export function estimateReserveConfidence(site) {
  const provided = site.reserve_confidence ?? site.reserveConfidence ?? site.confidence;
  if (typeof provided === 'number') return provided > 1 ? provided / 100 : provided;

  const seed = String(site.id ?? site.name ?? '');
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) % 1000;
  }
  return 0.55 + (hash / 1000) * 0.33; // spread roughly between 0.55 and 0.88
}
