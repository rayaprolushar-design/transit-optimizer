/**
 * DelayHeatmap.jsx — Week 20
 * 9×7 grid of coloured cells showing average predicted delay
 * by hour (columns) and day of week (rows).
 *
 * No API call needed — we generate predictions client-side by
 * calling the model logic locally (simulated), so the chart
 * works even if the backend is slow.
 *
 * Recharts concept used: Tooltip on a custom SVG shape.
 * The heatmap itself is pure CSS grid — Recharts isn't ideal for
 * 2-D grids, so we use it only where it shines (bar/line charts).
 */
import React, { useState } from 'react'

const HOURS    = [6, 8, 10, 12, 14, 16, 18, 20, 22]
const DAYS     = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const RUSH     = new Set([8, 9, 17, 18, 19])

// Synthetic delay model matching the ML model's learned patterns
function estimateDelay(hour, dayIdx) {
  const isWeekend = dayIdx >= 5
  const isRush    = RUSH.has(hour)
  let base = isRush ? 3.8 : hour < 7 || hour > 21 ? 0.8 : 1.8
  if (isWeekend) base *= 0.62
  base += (Math.sin(hour * 0.4) * 0.3)   // smooth curve noise
  return Math.max(0, parseFloat(base.toFixed(1)))
}

// Map delay → colour (green → yellow → red)
function delayColor(d) {
  if (d < 1.2) return { bg: 'bg-teal-900/70',   text: 'text-teal-300',   border: 'border-teal-800/50' }
  if (d < 2.5) return { bg: 'bg-yellow-900/60',  text: 'text-yellow-300', border: 'border-yellow-800/50' }
  if (d < 4.0) return { bg: 'bg-orange-900/60',  text: 'text-orange-300', border: 'border-orange-800/50' }
  return              { bg: 'bg-red-900/70',     text: 'text-red-300',    border: 'border-red-800/50' }
}

export default function DelayHeatmap() {
  const [hovered, setHovered] = useState(null)   // {day, hour, delay}

  return (
    <div>
      {/* Hour labels */}
      <div className="flex gap-1 mb-1 ml-10">
        {HOURS.map(h => (
          <div key={h} className="flex-1 text-center text-[10px] text-gray-500 font-mono">
            {String(h).padStart(2,'0')}
          </div>
        ))}
      </div>

      {/* Grid rows */}
      <div className="space-y-1">
        {DAYS.map((day, di) => (
          <div key={day} className="flex items-center gap-1">
            {/* Day label */}
            <div className="w-9 text-[11px] text-gray-500 text-right flex-shrink-0 pr-1">
              {day}
            </div>
            {/* Hour cells */}
            {HOURS.map(h => {
              const delay = estimateDelay(h, di)
              const { bg, text, border } = delayColor(delay)
              const isHot = hovered?.day === di && hovered?.hour === h
              return (
                <div
                  key={h}
                  className={`flex-1 rounded text-[10px] font-mono text-center py-1.5
                              border cursor-default transition-all select-none
                              ${bg} ${text} ${border}
                              ${isHot ? 'ring-1 ring-white/30 scale-105' : ''}`}
                  onMouseEnter={() => setHovered({ day: di, hour: h, delay })}
                  onMouseLeave={() => setHovered(null)}
                >
                  {delay}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Hover tooltip */}
      {hovered && (
        <div className="mt-2 text-xs text-gray-400 text-center">
          {DAYS[hovered.day]} {String(hovered.hour).padStart(2,'0')}:00 →{' '}
          <span className="font-mono text-gray-200 font-medium">
            {hovered.delay} min
          </span>{' '}
          avg delay
          {RUSH.has(hovered.hour) && !( hovered.day >= 5) &&
            <span className="ml-2 text-red-400">⚠ rush hour</span>}
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-3 mt-3 justify-center text-[10px] text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-teal-900 border border-teal-800 inline-block" />
          &lt; 1.2m
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-yellow-900 border border-yellow-800 inline-block" />
          1.2–2.5m
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-orange-900 border border-orange-800 inline-block" />
          2.5–4m
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-900 border border-red-800 inline-block" />
          &gt; 4m
        </span>
      </div>
    </div>
  )
}
