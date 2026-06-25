/**
 * PredictionHistoryChart.jsx — Week 21
 * Recharts LineChart showing how predicted delay changes across all 24 hours
 * for the currently selected stop. Updates every time the user picks a stop.
 *
 * Two series:
 *   blue  = weekday prediction
 *   teal  = weekend prediction (lower — no rush hour effect)
 *
 * Recharts concepts used:
 *   ComposedChart     — lets you mix Line + Area in one chart
 *   Area              — fill below the weekday line
 *   Line              — weekend series (thinner, dashed)
 *   ReferenceLine     — vertical marker at the currently selected hour
 *   ReferenceDot      — highlighted point at exact (hour, prediction)
 *   Legend            — custom rendered legend
 */
import {
  ComposedChart, Area, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, ReferenceDot,
  Legend, ResponsiveContainer,
} from 'recharts'

// Synthetic delay curve per hour — mirrors the ML model's learned patterns
function buildCurve(routeType = 3) {
  const scale = routeType === 1 ? 0.38 : 1.0   // metro much lower
  return Array.from({ length: 24 }, (_, h) => {
    const isRush  = (h >= 7 && h <= 10) || (h >= 17 && h <= 20)
    const isNight = h < 6 || h > 22

    let wd = isNight ? 0.6 : isRush ? 3.9 + Math.sin(h) * 0.3 : 1.8 + Math.cos(h * 0.5) * 0.2
    let we = wd * 0.6
    return {
      hour:    `${String(h).padStart(2, '0')}:00`,
      weekday: parseFloat((wd * scale).toFixed(2)),
      weekend: parseFloat((we * scale).toFixed(2)),
    }
  })
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1 font-mono">{label}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {p.value} min
        </p>
      ))}
    </div>
  )
}

export default function PredictionHistoryChart({ hour = 8, routeType = 3 }) {
  const data        = buildCurve(routeType)
  const currentHour = `${String(hour).padStart(2, '0')}:00`
  const currentWd   = data[hour]?.weekday ?? 0
  const currentWe   = data[hour]?.weekend ?? 0

  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">
        Predicted delay across all hours for selected stop · drag slider to move marker
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="wdGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#378ADD" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#378ADD" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />

          <XAxis
            dataKey="hour"
            tick={{ fill: '#4b5563', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            interval={3}
          />
          <YAxis
            tick={{ fill: '#4b5563', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            unit=" m"
          />

          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#374151', strokeWidth: 1 }} />

          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 6 }}
            formatter={v => <span style={{ color: '#9ca3af' }}>{v}</span>}
          />

          {/* Weekday area */}
          <Area
            type="monotone"
            dataKey="weekday"
            name="Weekday"
            stroke="#378ADD"
            strokeWidth={2}
            fill="url(#wdGrad)"
            dot={false}
            activeDot={{ r: 4, stroke: '#fff', strokeWidth: 1.5 }}
          />

          {/* Weekend line */}
          <Line
            type="monotone"
            dataKey="weekend"
            name="Weekend"
            stroke="#1D9E75"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            dot={false}
            activeDot={{ r: 3 }}
          />

          {/* Current hour marker */}
          <ReferenceLine
            x={currentHour}
            stroke="#EF9F27"
            strokeWidth={1.5}
            strokeDasharray="4 3"
          />

          {/* Highlight dot at current hour */}
          <ReferenceDot
            x={currentHour}
            y={currentWd}
            r={5}
            fill="#EF9F27"
            stroke="#030712"
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Current reading */}
      <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
        <span>
          At <span className="font-mono text-gray-300">{currentHour}</span>:
          weekday <span className="text-blue-400 font-mono">{currentWd}m</span>
          · weekend <span className="text-teal-400 font-mono">{currentWe}m</span>
        </span>
        <span className={`badge text-[11px] ${
          currentWd > 3 ? 'badge-red' : currentWd > 1.8 ? 'badge-yellow' : 'badge-green'
        }`}>
          {currentWd > 3 ? '⚠ High delay' : currentWd > 1.8 ? 'Moderate' : 'Low delay'}
        </span>
      </div>
    </div>
  )
}
