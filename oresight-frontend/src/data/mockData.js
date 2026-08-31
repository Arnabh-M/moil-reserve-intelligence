// ─────────────────────────────────────────────────────────────────────
// Mock Data — derived from production_history.csv, equipment_downtime_log.csv,
// deposit_ground_truth.csv, and seed_graph.cypher
// ─────────────────────────────────────────────────────────────────────

// ── Sites ──────────────────────────────────────────────────────────────
export const sites = [
  { id: 'balaghat', name: 'Balaghat Mine', belt: 'Balaghat-Manganese Belt', state: 'Madhya Pradesh' },
  { id: 'nagpur', name: 'Nagpur Mine', belt: 'Nagpur-Bhandara Manganese Belt', state: 'Maharashtra' },
  { id: 'bhandara', name: 'Bhandara Mine', belt: 'Nagpur-Bhandara Manganese Belt', state: 'Maharashtra' },
];

// ── Production History (last 30 days sample per site) ──────────────────
function generateProductionData() {
  const data = [];
  const startDate = new Date('2026-08-01');

  const siteTargets = { balaghat: 1200, nagpur: 1050, bhandara: 980 };
  const siteBase = { balaghat: 1210, nagpur: 1030, bhandara: 960 };

  for (let d = 0; d < 30; d++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + d);
    const dateStr = date.toISOString().split('T')[0];

    for (const site of ['balaghat', 'nagpur', 'bhandara']) {
      const base = siteBase[site];
      const target = siteTargets[site];
      // Add realistic variance ±8%
      const variance = (Math.sin(d * 0.7 + site.length) * 0.06 + (Math.cos(d * 1.3) * 0.04)) * base;
      const actual = Math.round((base + variance) * 10) / 10;
      data.push({ date: dateStr, site_id: site, actual_output: actual, target_output: target });
    }
  }
  return data;
}

export const productionHistory = generateProductionData();

// Aggregate daily totals across all sites
export const dailyTotals = [];
const dateMap = {};
productionHistory.forEach(row => {
  if (!dateMap[row.date]) {
    dateMap[row.date] = { date: row.date, actual: 0, target: 0 };
    dailyTotals.push(dateMap[row.date]);
  }
  dateMap[row.date].actual += row.actual_output;
  dateMap[row.date].target += row.target_output;
});
dailyTotals.forEach(d => {
  d.actual = Math.round(d.actual * 10) / 10;
  d.target = Math.round(d.target * 10) / 10;
});

// ── Equipment ──────────────────────────────────────────────────────────
export const equipment = [
  { id: 'eq_bal_01', site_id: 'balaghat', name: 'Excavator BAL-1', type: 'Excavator', status: 'up', lastChange: '2026-08-01T06:00' },
  { id: 'eq_bal_02', site_id: 'balaghat', name: 'Drill BAL-1', type: 'Drill', status: 'up', lastChange: '2026-08-03T09:30' },
  { id: 'eq_bal_03', site_id: 'balaghat', name: 'Conveyor BAL-1', type: 'Conveyor', status: 'up', lastChange: '2026-07-20T11:00' },
  { id: 'eq_bal_04', site_id: 'balaghat', name: 'Loader BAL-1', type: 'Loader', status: 'up', lastChange: '2026-08-10T08:15' },
  { id: 'eq_bal_05', site_id: 'balaghat', name: 'Compressor BAL-1', type: 'Compressor', status: 'down', lastChange: '2026-08-27T14:20' },
  { id: 'eq_nag_01', site_id: 'nagpur', name: 'Excavator NAG-1', type: 'Excavator', status: 'up', lastChange: '2026-08-05T07:45' },
  { id: 'eq_nag_02', site_id: 'nagpur', name: 'Drill NAG-1', type: 'Drill', status: 'down', lastChange: '2026-08-28T10:05' },
  { id: 'eq_nag_03', site_id: 'nagpur', name: 'Conveyor NAG-1', type: 'Conveyor', status: 'up', lastChange: '2026-07-15T13:00' },
  { id: 'eq_nag_04', site_id: 'nagpur', name: 'Loader NAG-1', type: 'Loader', status: 'up', lastChange: '2026-08-12T09:00' },
  { id: 'eq_nag_05', site_id: 'nagpur', name: 'Compressor NAG-1', type: 'Compressor', status: 'up', lastChange: '2026-07-28T16:30' },
  { id: 'eq_bhd_01', site_id: 'bhandara', name: 'Excavator BHD-1', type: 'Excavator', status: 'up', lastChange: '2026-08-02T08:00' },
  { id: 'eq_bhd_02', site_id: 'bhandara', name: 'Drill BHD-1', type: 'Drill', status: 'up', lastChange: '2026-08-06T09:00' },
  { id: 'eq_bhd_03', site_id: 'bhandara', name: 'Conveyor BHD-1', type: 'Conveyor', status: 'up', lastChange: '2026-07-22T12:00' },
  { id: 'eq_bhd_04', site_id: 'bhandara', name: 'Loader BHD-1', type: 'Loader', status: 'up', lastChange: '2026-08-09T10:30' },
  { id: 'eq_bhd_05', site_id: 'bhandara', name: 'Compressor BHD-1', type: 'Compressor', status: 'up', lastChange: '2026-07-30T15:00' },
];

// ── Downtime Log ───────────────────────────────────────────────────────
export const downtimeLog = [
  { equipment_id: 'eq_bal_03', site_id: 'balaghat', down_start: '2026-03-01 06:00', down_end: '2026-03-01 12:45', duration_hours: 6.75, reason: 'Scheduled Maintenance' },
  { equipment_id: 'eq_bal_01', site_id: 'balaghat', down_start: '2026-03-04 22:00', down_end: '2026-03-05 01:08', duration_hours: 3.13, reason: 'Scheduled Maintenance' },
  { equipment_id: 'eq_nag_03', site_id: 'nagpur', down_start: '2026-03-06 07:00', down_end: '2026-03-07 21:47', duration_hours: 38.78, reason: 'Weather Delay' },
  { equipment_id: 'eq_nag_03', site_id: 'nagpur', down_start: '2026-03-09 01:00', down_end: '2026-03-09 10:51', duration_hours: 9.84, reason: 'Operator Shift Gap' },
  { equipment_id: 'eq_bal_03', site_id: 'balaghat', down_start: '2026-03-15 01:00', down_end: '2026-03-15 07:45', duration_hours: 6.74, reason: 'Weather Delay' },
  { equipment_id: 'eq_nag_03', site_id: 'nagpur', down_start: '2026-03-26 00:00', down_end: '2026-03-26 03:22', duration_hours: 3.37, reason: 'Hydraulic Leak' },
  { equipment_id: 'eq_nag_01', site_id: 'nagpur', down_start: '2026-03-28 00:00', down_end: '2026-03-29 18:14', duration_hours: 42.24, reason: 'Weather Delay' },
  { equipment_id: 'eq_bal_02', site_id: 'balaghat', down_start: '2026-03-30 00:00', down_end: '2026-03-30 04:56', duration_hours: 4.94, reason: 'Scheduled Maintenance' },
  { equipment_id: 'eq_bhd_02', site_id: 'bhandara', down_start: '2026-03-31 13:00', down_end: '2026-04-01 22:25', duration_hours: 33.42, reason: 'Weather Delay' },
  { equipment_id: 'eq_nag_02', site_id: 'nagpur', down_start: '2026-04-04 03:00', down_end: '2026-04-04 07:11', duration_hours: 4.18, reason: 'Spare Parts Unavailable' },
  { equipment_id: 'eq_nag_01', site_id: 'nagpur', down_start: '2026-04-09 11:00', down_end: '2026-04-10 08:21', duration_hours: 21.35, reason: 'Weather Delay' },
  { equipment_id: 'eq_bhd_05', site_id: 'bhandara', down_start: '2026-04-23 00:00', down_end: '2026-04-23 02:24', duration_hours: 2.39, reason: 'Scheduled Maintenance' },
  { equipment_id: 'eq_bal_05', site_id: 'balaghat', down_start: '2026-04-24 07:00', down_end: '2026-04-25 04:07', duration_hours: 21.11, reason: 'Mechanical Failure' },
  { equipment_id: 'eq_bal_04', site_id: 'balaghat', down_start: '2026-04-24 10:00', down_end: '2026-04-24 18:54', duration_hours: 8.9, reason: 'Hydraulic Leak' },
  { equipment_id: 'eq_bal_05', site_id: 'balaghat', down_start: '2026-04-25 12:00', down_end: '2026-04-26 02:35', duration_hours: 14.59, reason: 'Hydraulic Leak' },
  { equipment_id: 'eq_bal_02', site_id: 'balaghat', down_start: '2026-04-27 22:00', down_end: '2026-04-28 08:58', duration_hours: 10.96, reason: 'Operator Shift Gap' },
  { equipment_id: 'eq_nag_03', site_id: 'nagpur', down_start: '2026-04-30 05:00', down_end: '2026-05-01 03:24', duration_hours: 22.4, reason: 'Operator Shift Gap' },
  { equipment_id: 'eq_bal_05', site_id: 'balaghat', down_start: '2026-05-09 05:00', down_end: '2026-05-10 02:55', duration_hours: 21.91, reason: 'Electrical Fault' },
  { equipment_id: 'eq_nag_05', site_id: 'nagpur', down_start: '2026-05-21 10:00', down_end: '2026-05-22 04:18', duration_hours: 18.3, reason: 'Hydraulic Leak' },
  { equipment_id: 'eq_nag_02', site_id: 'nagpur', down_start: '2026-05-24 20:00', down_end: '2026-05-25 04:25', duration_hours: 8.42, reason: 'Electrical Fault' },
  { equipment_id: 'eq_bal_02', site_id: 'balaghat', down_start: '2026-05-26 05:00', down_end: '2026-05-26 10:32', duration_hours: 5.54, reason: 'Scheduled Maintenance' },
  { equipment_id: 'eq_bal_05', site_id: 'balaghat', down_start: '2026-05-27 01:00', down_end: '2026-05-27 18:22', duration_hours: 17.37, reason: 'Electrical Fault' },
  { equipment_id: 'eq_bhd_05', site_id: 'bhandara', down_start: '2026-05-31 12:00', down_end: '2026-06-01 09:38', duration_hours: 21.63, reason: 'Hydraulic Leak' },
  { equipment_id: 'eq_bal_01', site_id: 'balaghat', down_start: '2026-06-05 14:00', down_end: '2026-06-06 08:47', duration_hours: 18.78, reason: 'Electrical Fault' },
  { equipment_id: 'eq_nag_04', site_id: 'nagpur', down_start: '2026-06-14 18:00', down_end: '2026-06-15 05:57', duration_hours: 11.95, reason: 'Spare Parts Unavailable' },
  { equipment_id: 'eq_bal_04', site_id: 'balaghat', down_start: '2026-06-17 05:00', down_end: '2026-06-17 21:43', duration_hours: 16.71, reason: 'Hydraulic Leak' },
  { equipment_id: 'eq_bhd_02', site_id: 'bhandara', down_start: '2026-06-21 15:00', down_end: '2026-06-21 18:27', duration_hours: 3.45, reason: 'Scheduled Maintenance' },
  { equipment_id: 'eq_bhd_01', site_id: 'bhandara', down_start: '2026-06-30 21:00', down_end: '2026-07-01 02:16', duration_hours: 5.26, reason: 'Mechanical Failure' },
  { equipment_id: 'eq_nag_04', site_id: 'nagpur', down_start: '2026-07-03 20:00', down_end: '2026-07-04 16:38', duration_hours: 20.63, reason: 'Electrical Fault' },
  { equipment_id: 'eq_bhd_05', site_id: 'bhandara', down_start: '2026-07-11 14:00', down_end: '2026-07-11 21:30', duration_hours: 7.49, reason: 'Scheduled Maintenance' },
  { equipment_id: 'eq_bal_02', site_id: 'balaghat', down_start: '2026-07-19 01:00', down_end: '2026-07-19 06:46', duration_hours: 5.76, reason: 'Hydraulic Leak' },
  { equipment_id: 'eq_bal_01', site_id: 'balaghat', down_start: '2026-07-26 00:00', down_end: '2026-07-26 15:16', duration_hours: 15.26, reason: 'Mechanical Failure' },
  { equipment_id: 'eq_nag_02', site_id: 'nagpur', down_start: '2026-08-19 23:00', down_end: '2026-08-20 18:44', duration_hours: 19.74, reason: 'Spare Parts Unavailable' },
  { equipment_id: 'eq_bhd_01', site_id: 'bhandara', down_start: '2026-08-24 07:00', down_end: '2026-08-24 17:35', duration_hours: 10.58, reason: 'Electrical Fault' },
  { equipment_id: 'eq_bal_04', site_id: 'balaghat', down_start: '2026-08-26 10:00', down_end: '2026-08-26 18:11', duration_hours: 8.19, reason: 'Mechanical Failure' },
  { equipment_id: 'eq_bal_03', site_id: 'balaghat', down_start: '2026-08-28 20:00', down_end: '2026-08-30 16:35', duration_hours: 44.59, reason: 'Weather Delay' },
];

// Aggregate downtime by reason
export const downtimeByReason = Object.entries(
  downtimeLog.reduce((acc, d) => {
    acc[d.reason] = (acc[d.reason] || 0) + d.duration_hours;
    return acc;
  }, {})
).map(([reason, hours]) => ({ reason, hours: Math.round(hours * 10) / 10 }))
  .sort((a, b) => b.hours - a.hours);

// Monthly downtime breakdown
export const monthlyDowntime = (() => {
  const months = {};
  downtimeLog.forEach(d => {
    const month = d.down_start.slice(0, 7); // "2026-03"
    if (!months[month]) months[month] = {};
    months[month][d.reason] = (months[month][d.reason] || 0) + d.duration_hours;
  });
  return Object.entries(months)
    .map(([month, reasons]) => ({ month, ...reasons }))
    .sort((a, b) => a.month.localeCompare(b.month));
})();

// ── Deposits / Reserves ────────────────────────────────────────────────
export const deposits = [
  { id: 'dep_001', site_id: 'balaghat', lat: 21.93976, lon: 80.28022, depth_m: 80.6, grade_percent: 6.38, confirmed: false },
  { id: 'dep_002', site_id: 'balaghat', lat: 21.79529, lon: 80.12343, depth_m: 28.4, grade_percent: 25.39, confirmed: true },
  { id: 'dep_003', site_id: 'balaghat', lat: 21.70571, lon: 80.14965, depth_m: 223.1, grade_percent: 10.21, confirmed: false },
  { id: 'dep_004', site_id: 'balaghat', lat: 21.92157, lon: 80.19515, depth_m: 269.2, grade_percent: 32.81, confirmed: true },
  { id: 'dep_005', site_id: 'balaghat', lat: 21.73781, lon: 80.14312, depth_m: 214.1, grade_percent: 20.19, confirmed: true },
  { id: 'dep_006', site_id: 'balaghat', lat: 21.85219, lon: 80.39753, depth_m: 21.1, grade_percent: 15.5, confirmed: true },
  { id: 'dep_007', site_id: 'balaghat', lat: 21.99793, lon: 80.27539, depth_m: 55.5, grade_percent: 41.92, confirmed: true },
  { id: 'dep_008', site_id: 'balaghat', lat: 21.96411, lon: 80.26086, depth_m: 194.1, grade_percent: 23.2, confirmed: true },
  { id: 'dep_009', site_id: 'balaghat', lat: 21.71516, lon: 80.27837, depth_m: 102.5, grade_percent: 9.63, confirmed: false },
  { id: 'dep_010', site_id: 'balaghat', lat: 21.95087, lon: 80.10545, depth_m: 186.8, grade_percent: 21.94, confirmed: true },
  { id: 'dep_011', site_id: 'balaghat', lat: 21.96217, lon: 80.17610, depth_m: 191.0, grade_percent: 8.2, confirmed: false },
  { id: 'dep_012', site_id: 'balaghat', lat: 21.81885, lon: 80.30329, depth_m: 223.2, grade_percent: 8.37, confirmed: false },
  { id: 'dep_013', site_id: 'balaghat', lat: 21.92753, lon: 80.39503, depth_m: 137.4, grade_percent: 30.44, confirmed: true },
  { id: 'dep_014', site_id: 'nagpur', lat: 21.11850, lon: 79.20477, depth_m: 61.8, grade_percent: 13.5, confirmed: false },
  { id: 'dep_015', site_id: 'nagpur', lat: 21.05353, lon: 79.05986, depth_m: 260.5, grade_percent: 42.38, confirmed: true },
  { id: 'dep_016', site_id: 'nagpur', lat: 21.06364, lon: 79.14094, depth_m: 225.4, grade_percent: 12.42, confirmed: false },
  { id: 'dep_017', site_id: 'nagpur', lat: 21.11372, lon: 79.15511, depth_m: 227.7, grade_percent: 10.5, confirmed: false },
  { id: 'dep_018', site_id: 'nagpur', lat: 21.23489, lon: 79.17098, depth_m: 49.3, grade_percent: 42.12, confirmed: true },
  { id: 'dep_019', site_id: 'nagpur', lat: 21.25967, lon: 79.23943, depth_m: 48.0, grade_percent: 21.13, confirmed: true },
  { id: 'dep_020', site_id: 'nagpur', lat: 21.22308, lon: 79.00694, depth_m: 294.2, grade_percent: 26.31, confirmed: true },
  { id: 'dep_021', site_id: 'nagpur', lat: 21.21579, lon: 79.26627, depth_m: 130.5, grade_percent: 24.57, confirmed: true },
  { id: 'dep_022', site_id: 'nagpur', lat: 21.18262, lon: 79.17430, depth_m: 134.6, grade_percent: 8.82, confirmed: false },
  { id: 'dep_023', site_id: 'nagpur', lat: 21.28061, lon: 79.14029, depth_m: 75.1, grade_percent: 5.9, confirmed: false },
  { id: 'dep_024', site_id: 'nagpur', lat: 21.11823, lon: 79.03933, depth_m: 65.6, grade_percent: 35.54, confirmed: true },
  { id: 'dep_025', site_id: 'nagpur', lat: 21.10184, lon: 79.28647, depth_m: 88.2, grade_percent: 17.97, confirmed: true },
  { id: 'dep_026', site_id: 'nagpur', lat: 21.22605, lon: 79.26431, depth_m: 97.9, grade_percent: 21.06, confirmed: true },
  { id: 'dep_027', site_id: 'bhandara', lat: 21.13321, lon: 79.57573, depth_m: 102.5, grade_percent: 37.94, confirmed: true },
  { id: 'dep_028', site_id: 'bhandara', lat: 21.36301, lon: 79.77049, depth_m: 295.7, grade_percent: 44.47, confirmed: true },
  { id: 'dep_029', site_id: 'bhandara', lat: 21.38590, lon: 79.52155, depth_m: 58.6, grade_percent: 4.96, confirmed: false },
  { id: 'dep_030', site_id: 'bhandara', lat: 21.26587, lon: 79.52909, depth_m: 256.8, grade_percent: 9.02, confirmed: false },
  { id: 'dep_031', site_id: 'bhandara', lat: 21.26271, lon: 79.54959, depth_m: 90.9, grade_percent: 3.08, confirmed: false },
  { id: 'dep_032', site_id: 'bhandara', lat: 21.35558, lon: 79.67527, depth_m: 225.8, grade_percent: 23.88, confirmed: true },
  { id: 'dep_033', site_id: 'bhandara', lat: 21.21138, lon: 79.62146, depth_m: 232.8, grade_percent: 38.17, confirmed: true },
  { id: 'dep_034', site_id: 'bhandara', lat: 21.16204, lon: 79.78246, depth_m: 53.8, grade_percent: 12.65, confirmed: false },
  { id: 'dep_035', site_id: 'bhandara', lat: 21.13012, lon: 79.57936, depth_m: 257.0, grade_percent: 20.38, confirmed: true },
  { id: 'dep_036', site_id: 'bhandara', lat: 21.22407, lon: 79.63496, depth_m: 88.7, grade_percent: 10.23, confirmed: false },
  { id: 'dep_037', site_id: 'bhandara', lat: 21.35540, lon: 79.76237, depth_m: 115.0, grade_percent: 7.9, confirmed: false },
  { id: 'dep_038', site_id: 'bhandara', lat: 21.17452, lon: 79.57344, depth_m: 65.2, grade_percent: 43.2, confirmed: true },
  { id: 'dep_039', site_id: 'bhandara', lat: 21.36640, lon: 79.73321, depth_m: 164.9, grade_percent: 29.72, confirmed: true },
  { id: 'dep_040', site_id: 'bhandara', lat: 21.25892, lon: 79.66097, depth_m: 141.7, grade_percent: 18.95, confirmed: true },
];

// Grade distribution histogram bins
export const gradeDistribution = (() => {
  const bins = [
    { range: '0-10', count: 0 },
    { range: '10-20', count: 0 },
    { range: '20-30', count: 0 },
    { range: '30-40', count: 0 },
    { range: '40-50', count: 0 },
  ];
  deposits.forEach(d => {
    const idx = Math.min(Math.floor(d.grade_percent / 10), 4);
    bins[idx].count++;
  });
  return bins;
})();

// ── Ore Zones ──────────────────────────────────────────────────────────
export const oreZones = [
  { id: 'oz_bal_01', site_id: 'balaghat', confidence: 0.82, grade_estimate: 38.5 },
  { id: 'oz_bal_02', site_id: 'balaghat', confidence: 0.61, grade_estimate: 24.0 },
  { id: 'oz_nag_01', site_id: 'nagpur', confidence: 0.74, grade_estimate: 31.2 },
  { id: 'oz_nag_02', site_id: 'nagpur', confidence: 0.55, grade_estimate: 19.8 },
  { id: 'oz_bhd_01', site_id: 'bhandara', confidence: 0.69, grade_estimate: 27.6 },
  { id: 'oz_bhd_02', site_id: 'bhandara', confidence: 0.48, grade_estimate: 16.4 },
];

// ── Weather Events ─────────────────────────────────────────────────────
export const weatherEvents = [
  { id: 'we_bal_01', site_id: 'balaghat', type: 'Heavy Rain', severity: 5, start: '2026-08-24', end: '2026-08-29', status: 'active' },
  { id: 'we_bal_02', site_id: 'balaghat', type: 'Dust Storm', severity: 2, start: '2026-07-10', end: '2026-07-11', status: 'resolved' },
  { id: 'we_nag_01', site_id: 'nagpur', type: 'Thunderstorm', severity: 2, start: '2026-08-05', end: '2026-08-06', status: 'resolved' },
  { id: 'we_bhd_01', site_id: 'bhandara', type: 'Heavy Rain', severity: 3, start: '2026-08-14', end: '2026-08-17', status: 'resolved' },
];

// ── Blast Plans ────────────────────────────────────────────────────────
export const blastPlans = [
  { id: 'bp_bal_01', site_id: 'balaghat', scheduled_date: '2026-08-26', status: 'delayed', affectsZone: 'oz_bal_01', delayedBy: 'we_bal_01' },
  { id: 'bp_bal_02', site_id: 'balaghat', scheduled_date: '2026-09-05', status: 'planned', affectsZone: 'oz_bal_02', delayedBy: null },
  { id: 'bp_bal_03', site_id: 'balaghat', scheduled_date: '2026-08-10', status: 'completed', affectsZone: null, delayedBy: null },
  { id: 'bp_nag_01', site_id: 'nagpur', scheduled_date: '2026-09-02', status: 'planned', affectsZone: 'oz_nag_01', delayedBy: null },
  { id: 'bp_nag_02', site_id: 'nagpur', scheduled_date: '2026-08-08', status: 'completed', affectsZone: null, delayedBy: null },
  { id: 'bp_bhd_01', site_id: 'bhandara', scheduled_date: '2026-09-03', status: 'planned', affectsZone: 'oz_bhd_01', delayedBy: null },
  { id: 'bp_bhd_02', site_id: 'bhandara', scheduled_date: '2026-08-12', status: 'completed', affectsZone: null, delayedBy: null },
];

// ── Risk Events ────────────────────────────────────────────────────────
export const riskEvents = [
  {
    id: 're_bal_01',
    site_id: 'balaghat',
    risk_type: 'Weather Delay',
    score: 0.78,
    description: 'Heavy rain (severity 5) at Balaghat delayed BlastPlan bp_bal_01, threatening OreZone oz_bal_01 extraction schedule.',
    detected_at: '2026-08-25T07:00',
    status: 'active',
    severity: 'critical',
  },
  {
    id: 're_nag_01',
    site_id: 'nagpur',
    risk_type: 'Equipment Failure',
    score: 0.68,
    description: 'Drill eq_nag_02 at Nagpur went down, blocking BlastPlan bp_nag_01 readiness.',
    detected_at: '2026-08-28T10:15',
    status: 'active',
    severity: 'warning',
  },
];

// ── Structural Features ────────────────────────────────────────────────
export const structuralFeatures = [
  { id: 'sf_bal_01', site_id: 'balaghat', type: 'Fold Axis', density: 0.71 },
  { id: 'sf_bal_02', site_id: 'balaghat', type: 'Fault Line', density: 0.58 },
  { id: 'sf_nag_01', site_id: 'nagpur', type: 'Shear Zone', density: 0.63 },
  { id: 'sf_bhd_01', site_id: 'bhandara', type: 'Fault Line', density: 0.49 },
];

// ── Redeploy Suggestions ───────────────────────────────────────────────
export const redeploySuggestions = [
  {
    downEquipment: { id: 'eq_nag_02', name: 'Drill NAG-1', site: 'Nagpur', type: 'Drill' },
    candidate: { id: 'eq_bhd_02', name: 'Drill BHD-1', site: 'Bhandara', type: 'Drill' },
    reason: 'Drill BHD-1 at Bhandara is idle (up, no blast plan dependency) and matches the type of down Drill NAG-1 at Nagpur.',
    priority: 'high',
  },
];

// ── Site-level aggregates (for production page) ────────────────────────
export const siteProductionSummary = sites.map(site => {
  const siteData = productionHistory.filter(p => p.site_id === site.id);
  const totalActual = siteData.reduce((sum, p) => sum + p.actual_output, 0);
  const totalTarget = siteData.reduce((sum, p) => sum + p.target_output, 0);
  const avgActual = totalActual / siteData.length;
  const achievement = ((totalActual / totalTarget) * 100).toFixed(1);
  const eqCount = equipment.filter(e => e.site_id === site.id).length;
  const upCount = equipment.filter(e => e.site_id === site.id && e.status === 'up').length;

  return {
    ...site,
    totalActual: Math.round(totalActual),
    totalTarget: Math.round(totalTarget),
    avgDaily: Math.round(avgActual),
    achievement: parseFloat(achievement),
    equipmentTotal: eqCount,
    equipmentUp: upCount,
  };
});
