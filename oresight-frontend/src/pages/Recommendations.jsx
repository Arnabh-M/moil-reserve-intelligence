import React from 'react';
import { RecommendationCard } from '../components';

const recommendations = [
  {
    trigger:
      'Heavy rainfall detected near Balaghat — BlastPlan #14 (bp_bal_01) delayed by 2 days. OreZone oz_bal_01 extraction schedule at risk.',
    options: [
      {
        title: 'Reschedule',
        description:
          'Push bp_bal_01 to Sep 1 when weather clears. Extends timeline by 4 days but preserves equipment safety margins.',
        impact: '+12% safety margin',
        impactVariant: 'operational',
      },
      {
        title: 'Redeploy',
        description:
          'Move Excavator BAL-1 to Nagpur site for active extraction while Balaghat waits. Recovers 680 t of idle capacity.',
        impact: '+680 t recovered',
        impactVariant: 'info',
      },
      {
        title: 'Adjust Plan',
        description:
          'Reduce blast charge and proceed with modified parameters during lighter rain windows. Higher risk, faster turnaround.',
        impact: '-8% confidence',
        impactVariant: 'warning',
      },
    ],
  },
  {
    trigger:
      'Drill NAG-1 (eq_nag_02) at Nagpur went down due to hydraulic failure. BlastPlan bp_nag_01 readiness blocked — estimated 48hr repair.',
    options: [
      {
        title: 'Reschedule',
        description:
          'Delay bp_nag_01 by 3 days until eq_nag_02 repair is complete. No additional cost, schedule slips to Sep 5.',
        impact: '-3 day slip',
        impactVariant: 'warning',
      },
      {
        title: 'Redeploy',
        description:
          'Transfer idle Drill BHD-1 from Bhandara to Nagpur. Same type, no blast plan dependency. Transport takes 6 hours.',
        impact: '+15% recovery',
        impactVariant: 'operational',
      },
      {
        title: 'Adjust Plan',
        description:
          'Use Excavator NAG-1 as interim drilling substitute with modified bit. Slower but avoids full delay.',
        impact: '-22% efficiency',
        impactVariant: 'delayed',
      },
    ],
  },
  {
    trigger:
      'Production shortfall at Bhandara Mine — actual output 720 t/day vs 960 t target (25% below). Conveyor BHD-1 throughput degraded.',
    options: [
      {
        title: 'Reschedule',
        description:
          'Schedule conveyor maintenance for next weekend. Accept shortfall this week, full recovery by Monday.',
        impact: '+4 day delay',
        impactVariant: 'warning',
      },
      {
        title: 'Redeploy',
        description:
          'Route Bhandara output through Loader BHD-1 bypass path. 85% of conveyor capacity, eliminates bottleneck.',
        impact: '+85% capacity',
        impactVariant: 'operational',
      },
      {
        title: 'Adjust Plan',
        description:
          'Increase Balaghat and Nagpur targets by 120 t/day each to offset Bhandara shortfall across the portfolio.',
        impact: '+240 t/day offset',
        impactVariant: 'info',
      },
    ],
  },
];

export default function Recommendations() {
  return (
    <div className="page-container">
      <h2 className="page-title">AI Recommendations</h2>
      <p className="page-subtitle">
        Intelligent response options for active disruptions — review, simulate, and action
      </p>

      <div className="space-y-5 stagger-children">
        {recommendations.map((rec, idx) => (
          <RecommendationCard key={idx} trigger={rec.trigger} options={rec.options} />
        ))}
      </div>
    </div>
  );
}
