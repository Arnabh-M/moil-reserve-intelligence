import React from 'react'
import Slider from 'rc-slider'
import 'rc-slider/assets/index.css'
import { Calendar, Layers, ChevronLeft, ChevronRight } from 'lucide-react'
import { NDVI_TIMESERIES_CONFIG } from '../../lib/map'

export default function NdviTimeSlider({
  selectedWeek = 4,
  onWeekChange,
  visible = true,
}) {
  if (!visible) return null

  const activeWeek =
    NDVI_TIMESERIES_CONFIG.find((w) => w.week_index === selectedWeek) ||
    NDVI_TIMESERIES_CONFIG[NDVI_TIMESERIES_CONFIG.length - 1]

  const marks = {
    1: {
      style: { fontSize: '10px', fontWeight: 600, color: '#5a6577' },
      label: 'W1',
    },
    2: {
      style: { fontSize: '10px', fontWeight: 600, color: '#5a6577' },
      label: 'W2',
    },
    3: {
      style: { fontSize: '10px', fontWeight: 600, color: '#5a6577' },
      label: 'W3',
    },
    4: {
      style: { fontSize: '10px', fontWeight: 600, color: '#5a6577' },
      label: 'W4',
    },
  }

  function handlePrev() {
    if (selectedWeek > 1) {
      onWeekChange(selectedWeek - 1)
    }
  }

  function handleNext() {
    if (selectedWeek < 4) {
      onWeekChange(selectedWeek + 1)
    }
  }

  return (
    <div className="absolute bottom-6 left-6 z-10 w-84 rounded-xl border border-border bg-bg-surface/95 p-4 shadow-lg backdrop-blur-md">
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
              {activeWeek.date}
            </div>
            <div className="text-[10px] text-text-muted">
              Window: {activeWeek.window_start} to {activeWeek.window_end}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handlePrev}
            disabled={selectedWeek <= 1}
            aria-label="Previous week"
            className="rounded p-1 text-navy hover:bg-bg-surface disabled:opacity-30 disabled:pointer-events-none transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            onClick={handleNext}
            disabled={selectedWeek >= 4}
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
          onChange={(val) => onWeekChange(Number(val))}
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
    </div>
  )
}
