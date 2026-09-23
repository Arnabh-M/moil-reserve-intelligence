import React from 'react'
import Slider from 'rc-slider'
import 'rc-slider/assets/index.css'
import { Calendar, Layers, ChevronLeft, ChevronRight } from 'lucide-react'

export default function NdviTimeSlider({
  selectedWeek = 4,
  onWeekChange,
  visible = true,
  weeks = [],
}) {
  if (!visible) return null

  // Weeks come from tiles/manifest.json. A "no_data" week (too cloudy / no
  // scenes) has no image: it is greyed out and cannot be selected.
  const activeWeek = weeks.find((w) => w.week_index === selectedWeek) || null
  const unavailable = weeks.filter((w) => !w.available)
  const isAvailable = (n) => weeks.some((w) => w.week_index === n && w.available)

  const marks = Object.fromEntries(
    [1, 2, 3, 4].map((n) => [
      n,
      {
        style: {
          fontSize: '10px',
          fontWeight: 600,
          color: isAvailable(n) || weeks.length === 0 ? '#5a6577' : '#b8c0cc',
          textDecoration: isAvailable(n) || weeks.length === 0 ? 'none' : 'line-through',
        },
        label: `W${n}`,
      },
    ]),
  )

  function step(dir) {
    for (let n = selectedWeek + dir; n >= 1 && n <= 4; n += dir) {
      if (isAvailable(n)) {
        onWeekChange(n)
        return
      }
    }
  }
  const hasPrev = [1, 2, 3, 4].some((n) => n < selectedWeek && isAvailable(n))
  const hasNext = [1, 2, 3, 4].some((n) => n > selectedWeek && isAvailable(n))

  return (
    <div className="pointer-events-auto w-80 max-w-full rounded-[3px] border border-border bg-bg-surface p-4 shadow-xs">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Layers size={15} className="text-teal" />
          <h4 className="font-heading text-xs font-bold text-navy uppercase tracking-wider">
            NDVI Vegetation Time-Series
          </h4>
        </div>
        <span className="text-[10px] font-semibold text-orange bg-orange/10 px-2 py-0.5 rounded">
          Week {selectedWeek} of 4
        </span>
      </div>

      {/* Date Label above slider */}
      <div className="rounded-lg border border-border bg-bg/60 px-3 py-2 mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-text-muted shrink-0" />
          <div>
            <div className="text-xs font-bold text-navy">
              {!activeWeek
                ? 'Loading…'
                : activeWeek.available
                  ? activeWeek.date
                  : 'No clear imagery'}
            </div>
            <div className="text-[10px] text-text-muted">
              {activeWeek
                ? `Window: ${activeWeek.window_start} to ${activeWeek.window_end}`
                : ''}
              {activeWeek?.available && activeWeek.valid_fraction != null
                ? ` · ${Math.round(activeWeek.valid_fraction * 100)}% clear`
                : ''}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => step(-1)}
            disabled={!hasPrev}
            aria-label="Previous week"
            className="rounded p-1 text-navy hover:bg-bg-surface disabled:opacity-30 disabled:pointer-events-none transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            onClick={() => step(1)}
            disabled={!hasNext}
            aria-label="Next week"
            className="rounded p-1 text-navy hover:bg-bg-surface disabled:opacity-30 disabled:pointer-events-none transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* rc-slider */}
      <div className="px-2 pb-2 pt-1">
        <Slider
          min={1}
          max={4}
          step={1}
          value={selectedWeek}
          onChange={(val) => isAvailable(Number(val)) && onWeekChange(Number(val))}
          marks={marks}
          styles={{
            track: { backgroundColor: '#e0793a', height: 4 },
            rail: { backgroundColor: '#e2e7ee', height: 4 },
            handle: {
              borderColor: '#e0793a',
              backgroundColor: '#ffffff',
              boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
              opacity: 1,
            },
          }}
        />
      </div>

      {unavailable.length > 0 && (
        <div className="mt-1 text-[10px] text-text-muted">
          {unavailable
            .map((w) => `W${w.week_index} (${w.window_start} to ${w.window_end})`)
            .join(', ')}
          : no clear imagery (cloud cover) — not available.
        </div>
      )}
    </div>
  )
}
