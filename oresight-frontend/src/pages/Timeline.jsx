import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, Clock } from 'lucide-react';
import { Badge, EmptyState } from '../components';

const events = [
  {
    id: 1,
    timestamp: '2 hrs ago',
    severity: 'critical',
    title: 'Conveyor BAL-1 down — weather delay',
    description:
      'eq_bal_03 went offline due to sustained heavy rain at Balaghat. Estimated downtime 44.6 hrs. Blast plan bp_bal_01 impacted.',
    site: 'Balaghat',
    dotColor: 'bg-[var(--critical)]',
  },
  {
    id: 2,
    timestamp: '5 hrs ago',
    severity: 'critical',
    title: 'Risk event re_bal_01 escalated to Critical',
    description:
      'Weather delay risk score increased from 0.65 to 0.78. Heavy rain severity 5 continues at Balaghat, threatening OreZone oz_bal_01 extraction.',
    site: 'Balaghat',
    dotColor: 'bg-[var(--critical)]',
  },
  {
    id: 3,
    timestamp: '1 day ago',
    severity: 'warning',
    title: 'Drill NAG-1 failure — hydraulic leak',
    description:
      'eq_nag_02 went down at Nagpur site. BlastPlan bp_nag_01 readiness now blocked. Spare drill available at Bhandara (eq_bhd_02).',
    site: 'Nagpur',
    dotColor: 'bg-[var(--warning-medium)]',
  },
  {
    id: 4,
    timestamp: '2 days ago',
    severity: 'warning',
    title: 'Loader BAL-1 mechanical failure resolved',
    description:
      'eq_bal_04 repaired after 8.19 hrs downtime at Balaghat. Back online and operational. No blast plan impact.',
    site: 'Balaghat',
    dotColor: 'bg-[var(--warning-medium)]',
  },
  {
    id: 5,
    timestamp: '4 days ago',
    severity: 'operational',
    title: 'BlastPlan bp_bhd_02 completed successfully',
    description:
      'Bhandara blasting operation completed on schedule (Aug 12). OreZone oz_bhd_01 ready for extraction. No incidents reported.',
    site: 'Bhandara',
    dotColor: 'bg-[var(--success)]',
  },
  {
    id: 6,
    timestamp: '7 days ago',
    severity: 'operational',
    title: 'Heavy rain at Bhandara concluded',
    description:
      'WeatherEvent we_bhd_01 (severity 3) ended Aug 17. Operations resumed at full capacity. Equipment inspections cleared.',
    site: 'Bhandara',
    dotColor: 'bg-[var(--success)]',
  },
];

export default function Timeline() {
  const navigate = useNavigate();

  if (events.length === 0) {
    return (
      <div className="page-container">
        <h1 className="page-title">Risk Timeline</h1>
        <p className="page-subtitle">
          Chronological record of disruptions, resolutions, and milestones across all mine sites
        </p>
        <EmptyState
          icon={Clock}
          title="No events recorded"
          message="Disruptions, resolutions, and milestones will appear here as they happen."
          tone="neutral"
        />
      </div>
    );
  }

  return (
    <div className="page-container">
      <h1 className="page-title">Risk Timeline</h1>
      <p className="page-subtitle">
        Chronological record of disruptions, resolutions, and milestones across all mine sites
      </p>

      {/* Timeline */}
      <div className="relative ml-2 mt-4">
        {/* Vertical connecting line */}
        <div
          className="absolute left-[5px] top-2 bottom-2 w-[1px] bg-[var(--divider)]"
          aria-hidden="true"
        />

        <div className="space-y-6">
          {events.map((event, idx) => (
            <div
              key={event.id}
              className="relative flex items-start gap-4 animate-fade-in"
              style={{ animationDelay: `${idx * 0.05}s` }}
            >
              {/* Dot */}
              <div className="relative z-10 shrink-0 mt-1">
                <span className={`block w-2.5 h-2.5 rounded-full ${event.dotColor}`} />
              </div>

              {/* Event content */}
              <div className="flex-1 min-w-0 pb-2">
                <div className="flex items-start justify-between gap-3 mb-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="text-xs font-semibold text-[var(--text-primary)]">{event.title}</h4>
                    <Badge variant={event.severity}>{event.severity}</Badge>
                  </div>
                  <span className="text-[11px] text-[var(--text-muted)] whitespace-nowrap shrink-0">
                    {event.timestamp}
                  </span>
                </div>
                <p className="text-xs text-[var(--text-muted)] leading-relaxed mb-2">
                  {event.description}
                </p>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wider">
                    {event.site}
                  </span>
                  <button
                    type="button"
                    onClick={() => navigate(`/site/${event.site.toLowerCase()}`)}
                    className="inline-flex items-center gap-1 text-[11px] text-[var(--accent-primary)] font-medium hover:underline cursor-pointer"
                  >
                    <span>View Details</span>
                    <ExternalLink size={11} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


