/**
 * CacheGauge.jsx — Week 20
 * Recharts RadialBarChart showing cache hit rate as a gauge.
 * Also shows a small sparkline of hit rate over "simulated time".
 *
 * Recharts concepts:
 *   RadialBarChart  — circular progress bar
 *   RadialBar       — the filled arc segment
 *   LineChart       — sparkline trend
 *   Line            — single data series
 */
import {
  RadialBarChart, RadialBar, ResponsiveContainer,
  LineChart, Line, Tooltip,
} from 'recharts'

// Sparkline data — simulated hit rate building up as cache warms
const SPARKLINE = [
  {t:1,v:0},{t:2,v:12},{t:3,v:28},{t:4,v:41},{t:5,v:55},
  {t:6,v:62},{t:7,v:68},{t:8,v:71},{t:9,v:73},{t:10,v:75},
]

export default function CacheGauge({ hitRate = 75, label = 'Route cache' }) {
  const gaugeData = [
    { name: 'bg',  value: 100, fill: '#1f2937' },
    { name: 'hit', value: hitRate, fill: hitRate > 60 ? '#1D9E75' : hitRate > 30 ? '#EF9F27' : '#E24B4A' },
  ]

  return (
    <div className="flex flex-col items-center">
      {/* Radial gauge */}
      <div className="relative w-28 h-28">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%" cy="50%"
            innerRadius="68%" outerRadius="100%"
            startAngle={220} endAngle={-40}
            data={gaugeData}
            barSize={10}
          >
            <RadialBar dataKey="value" cornerRadius={5} background={false} />
          </RadialBarChart>
        </ResponsiveContainer>
        {/* Centre label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-semibold text-gray-100">{hitRate}%</span>
          <span className="text-[10px] text-gray-500">hit rate</span>
        </div>
      </div>

      <p className="text-xs text-gray-500 mt-1 mb-3">{label}</p>

      {/* Sparkline: cache warming over time */}
      <div className="w-full">
        <p className="text-[10px] text-gray-600 mb-1 text-center">
          Hit rate as cache warms ↑
        </p>
        <ResponsiveContainer width="100%" height={48}>
          <LineChart data={SPARKLINE} margin={{ top:2, right:4, left:4, bottom:2 }}>
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.length
                  ? <div className="bg-gray-800 text-xs text-gray-200 px-2 py-1 rounded border border-gray-700">
                      {payload[0].value}% hit rate
                    </div>
                  : null
              }
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke="#1D9E75"
              strokeWidth={2}
              dot={false}
              strokeLinecap="round"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
