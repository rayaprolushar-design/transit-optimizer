/**
 * DelayByHourChart.jsx — Week 20
 * Recharts AreaChart of average predicted delay by hour.
 * Rush hour peaks highlighted with a reference area.
 *
 * Recharts concepts:
 *   AreaChart        — line chart with filled area below
 *   Area             — the filled series
 *   ReferenceLine    — vertical marker at a specific X value
 *   ReferenceArea    — shaded region between two X values
 *   defs / linearGradient — SVG gradient fill for the area
 */
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceArea,
} from 'recharts'

const HOURS_DATA = [
  {h:'05',delay:1.0},{h:'06',delay:1.1},{h:'07',delay:3.9},
  {h:'08',delay:4.1},{h:'09',delay:4.0},{h:'10',delay:2.3},
  {h:'11',delay:2.1},{h:'12',delay:2.2},{h:'13',delay:2.0},
  {h:'14',delay:2.3},{h:'15',delay:2.1},{h:'16',delay:2.4},
  {h:'17',delay:4.4},{h:'18',delay:4.3},{h:'19',delay:4.2},
  {h:'20',delay:2.2},{h:'21',delay:1.9},{h:'22',delay:1.7},
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].value
  const isRush = ['07','08','09','17','18','19'].includes(label)
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-0.5">{label}:00</p>
      <p className="font-medium text-gray-100">{d} min avg delay</p>
      {isRush && <p className="text-red-400 mt-0.5">⚠ Rush hour</p>}
    </div>
  )
}

export default function DelayByHourChart() {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart
        data={HOURS_DATA}
        margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
      >
        <defs>
          <linearGradient id="delayGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#378ADD" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#378ADD" stopOpacity={0.02} />
          </linearGradient>
        </defs>

        {/* Rush hour shading */}
        <ReferenceArea x1="07" x2="09" fill="#EF9F27" fillOpacity={0.07}
                       label={{ value:'AM rush', fill:'#b45309', fontSize:10, position:'insideTop' }} />
        <ReferenceArea x1="17" x2="19" fill="#EF9F27" fillOpacity={0.07}
                       label={{ value:'PM rush', fill:'#b45309', fontSize:10, position:'insideTop' }} />

        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis dataKey="h" tick={{ fill:'#6b7280', fontSize:11 }}
               axisLine={false} tickLine={false} />
        <YAxis tick={{ fill:'#6b7280', fontSize:11 }}
               axisLine={false} tickLine={false}
               label={{ value:'min', angle:-90, position:'insideLeft',
                        fill:'#4b5563', fontSize:10, dx:14 }} />
        <Tooltip content={<CustomTooltip />} cursor={{ stroke:'#374151', strokeWidth:1 }} />

        <Area
          type="monotone"
          dataKey="delay"
          stroke="#378ADD"
          strokeWidth={2}
          fill="url(#delayGradient)"
          dot={{ fill:'#378ADD', r:3, strokeWidth:0 }}
          activeDot={{ r:5, fill:'#378ADD', stroke:'#fff', strokeWidth:2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
