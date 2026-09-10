// Single source of truth for client-side numeric bound checks.
// Mirrored in the backend at app/constants/validation_limits.py — that file
// must agree with this one. If you change a value here, change it there too.
//
// Only constants an actual frontend validator uses are exported here.
// SEVERITY_PCT_* and SIMULATOR_CONDITION_DURATION_* also exist on the
// backend but have no frontend counterpart: the Scenario Simulator's
// severity/duration levers are preset segmented buttons and range sliders
// already clamped to safe values in the UI (see SimulatorPage in App.jsx) —
// the backend bound there is defence-in-depth against direct API calls
// only, not something the UI needs to re-check.

// Tonnage: no single production/blast entry physically produces more than
// 100,000 tonnes. Matches MAX_TONNES in validation_limits.py.
export const MAX_TONNES = 100_000;
