/**
 * AlgoCompareChart.jsx — Week 20
 * Recharts BarChart comparing A* vs Dijkstra across 5 routes:
 *   - nodes visited (lower = more efficient)
 *   - query time in ms
 *
 * Recharts concepts:
 *   ResponsiveContainer  — fills parent width automatically
 *   BarChart             — grouped bar chart
 *   CartesianGrid        — subtle grid lines
 *   XAxis / YAxis        — labelled axes
 *   Tooltip              — hover card
 *   Legend               — colour key
 *   Bar                  — one series per algorithm metric
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts'

// Static benchmark data (from Week 5 profiling output)
const DATA = [
  { route: 'MG→BTM',    astar: 3,  dijkstra: 8  },
  { route: 'MG→HSR',    astar: 4,  dijkstra: 10 },
  { route: 'MG→Yshntr', astar: 4,  dijkstra: 12 },
  { route: 'Hebbal→EC', astar: 6,  dijkstra: 22 },
  { route: 'Rajaj→HSR', astar: 5,  dijkstra: 15 },
]

const COLORS = { astar: '#1D9E75', dijkstra: '#378ADD' }

// Custom tooltip card
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const astar    = payload.find(p => p.dataKey === 'astar')?.value
  const dijkstra = payload.find(p => p.dataKey === 'dijkstra')?.value
  const saving   = dijkstra && astar ? Math.round((1 - astar / dijkstra) * 100) : 0
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="font-medium text-gray-200 mb-1">{label}</p>
      <p className="text-teal-400">A*: {astar} nodes</p>
      <p className="text-blue-400">Dijkstra: {dijkstra} nodes</p>
      <p className="text-gray-400 mt-1">A* explored {saving}% fewer nodes</p>
    </div>
  )
}

export default function AlgoCompareChart() {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart
        data={DATA}
        margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
        barCategoryGap="28%"
        barGap={3}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="#1f2937"
          vertical={false}
        />
        <XAxis
          dataKey="route"
          tick={{ fill: '#6b7280', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: '#6b7280', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          label={{
            value: 'Nodes visited',
            angle: -90,
            position: 'insideLeft',
            fill: '#4b5563',
            fontSize: 10,
            dx: 14,
          }}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#ffffff08' }} />
        <Legend
          wrapperStyle={{ fontSize: 11, color: '#9ca3af', paddingTop: 6 }}
          formatter={v => v === 'astar' ? 'A*' : 'Dijkstra'}
        />
        <Bar dataKey="astar"    fill={COLORS.astar}    radius={[3,3,0,0]} name="A*" />
        <Bar dataKey="dijkstra" fill={COLORS.dijkstra} radius={[3,3,0,0]} name="Dijkstra" />
      </BarChart>
    </ResponsiveContainer>
  )
}
