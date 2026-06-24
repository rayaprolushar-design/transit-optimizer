/**
 * pages/Analytics.jsx — Week 20
 * Full dashboard with four chart panels + live stats from the API.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────┐
 *   │ stat cards row (stops / edges / requests / uptime)   │
 *   ├───────────────────────┬──────────────────────────────┤
 *   │ Delay by hour         │ A* vs Dijkstra node count    │
 *   │ (AreaChart)           │ (BarChart)                   │
 *   ├───────────────────────┼──────────────────────────────┤
 *   │ Delay heatmap         │ Cache gauges (route/predict) │
 *   │ (CSS grid)            │ (RadialBarChart + sparkline)  │
 *   └───────────────────────┴──────────────────────────────┘
 */
import { useEffect, useState } from 'react'
import { Database, Zap, Server, GitBranch } from 'lucide-react'
import TopBar            from '../components/TopBar'
import LoadingSpinner    from '../components/LoadingSpinner'
import ErrorBanner       from '../components/ErrorBanner'
import DelayByHourChart  from '../components/DelayByHourChart'
import AlgoCompareChart  from '../components/AlgoCompareChart'
import DelayHeatmap      from '../components/DelayHeatmap'
import CacheGauge        from '../components/CacheGauge'
import { api }           from '../api/client'

function StatCard({ icon: Icon, label, value, sub, color = 'text-gray-100' }) {
  return (
    <div className="card flex items-start gap-3">
      <div className="p-2 rounded-lg bg-gray-800 flex-shrink-0">
        <Icon className="w-4 h-4 text-gray-400" />
      </div>
      <div>
        <p className={`text-xl font-semibold ${color}`}>{value ?? '—'}</p>
        <p className="text-xs text-gray-400">{label}</p>
        {sub && <p className="text-[11px] text-gray-600 mt-0.5 font-mono leading-none">{sub}</p>}
      </div>
    </div>
  )
}

export default function Analytics() {
  const [stats,   setStats]   = useState(null)
  const [model,   setModel]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    Promise.all([api.stats(), api.modelInfo()])
      .then(([s, m]) => { setStats(s); setModel(m) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const rc = stats?.cache?.route_cache
  const pc = stats?.cache?.prediction_cache
  const g  = stats?.graph

  return (
    <div>
      <TopBar
        title="Analytics"
        subtitle="Live server metrics · ML model performance · Algorithm comparison"
      />

      {loading && <LoadingSpinner text="Fetching server stats…" />}
      {error   && <ErrorBanner message={error} />}

      {!loading && (
        <>
          {/* ── Stat cards ─────────────────────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <StatCard
              icon={Server}
              label="Total stops"
              value={g?.stops}
              sub={`${g?.transit_edges} transit + ${g?.walk_edges} walk edges`}
              color="text-brand-neonBlue"
            />
            <StatCard
              icon={Zap}
              label="Model MAE"
              value={model?.test_mae != null ? `${model.test_mae} min` : null}
              sub={`R² = ${model?.test_r2 ?? '—'}`}
              color="text-teal-400"
            />
            <StatCard
              icon={Database}
              label="Route cache"
              value={rc?.hit_rate != null ? `${rc.hit_rate}%` : null}
              sub={`${rc?.hits ?? 0} hits / ${rc?.misses ?? 0} misses`}
              color="text-yellow-400"
            />
            <StatCard
              icon={GitBranch}
              label="Requests served"
              value={stats?.server?.requests_served}
              sub={`Uptime: ${stats?.server?.uptime_s ?? 0}s`}
              color="text-gray-100"
            />
          </div>

          {/* ── Charts row 1 ───────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">

            <div className="card">
              <p className="card-title text-sm font-bold text-slate-200">Average delay by hour</p>
              <p className="text-xs text-gray-600 mb-3">
                Predicted by the Gradient Boosting model across all stops · rush hour shaded
              </p>
              <DelayByHourChart />
            </div>

            <div className="card">
              <p className="card-title text-sm font-bold text-slate-200">A* vs Dijkstra — nodes explored</p>
              <p className="text-xs text-gray-600 mb-3">
                A* visits fewer nodes via Haversine heuristic · same optimal result
              </p>
              <AlgoCompareChart />
            </div>

          </div>

          {/* ── Charts row 2 ───────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            <div className="card">
              <p className="card-title text-sm font-bold text-slate-200">Delay heatmap — hour × day</p>
              <p className="text-xs text-gray-600 mb-4">
                Hover cells to inspect · darker = more delay
              </p>
              <DelayHeatmap />
            </div>

            <div className="card">
              <p className="card-title text-sm font-bold text-slate-200">Cache performance</p>
              <p className="text-xs text-gray-600 mb-4">
                LRU cache hit rate — repeat queries return in &lt;0.01ms
              </p>

              <div className="grid grid-cols-2 gap-4">
                <CacheGauge
                  hitRate={rc?.hit_rate ?? 0}
                  label="Route cache"
                />
                <CacheGauge
                  hitRate={pc?.hit_rate ?? 0}
                  label="Prediction cache"
                />
              </div>

              {/* Model feature table */}
              <div className="mt-5 border-t border-gray-800 pt-4">
                <p className="text-xs font-medium text-gray-400 mb-2">
                  Model features ({model?.feature_cols?.length ?? 0})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {model?.feature_cols?.map(f => (
                    <span key={f}
                      className="px-2 py-0.5 bg-gray-800 text-gray-400 border border-gray-700
                                 rounded-full text-[11px] font-mono">
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            </div>

          </div>

          {/* ── Algorithm insight ───────────────────────────────────── */}
          <div className="card mt-4">
            <p className="card-title text-sm font-bold text-slate-200">Why A* beats Dijkstra</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm mt-3">
              <div>
                <p className="text-gray-300 font-medium mb-1">Dijkstra</p>
                <p className="text-gray-500 text-xs leading-relaxed">
                  Explores all directions equally. Priority = cost so far (g).
                  Guaranteed optimal but visits more nodes.
                </p>
                <p className="mt-2 font-mono text-xs text-blue-400">
                  priority = g(n)
                </p>
              </div>
              <div>
                <p className="text-gray-300 font-medium mb-1">A*</p>
                <p className="text-gray-500 text-xs leading-relaxed">
                  Guided toward destination. Priority = cost so far + estimated
                  remaining (h). Same optimal result, fewer nodes visited.
                </p>
                <p className="mt-2 font-mono text-xs text-teal-400">
                  priority = g(n) + h(n)
                </p>
              </div>
              <div>
                <p className="text-gray-300 font-medium mb-1">h(n) — Haversine heuristic</p>
                <p className="text-gray-500 text-xs leading-relaxed">
                  Straight-line GPS distance ÷ bus speed. Always underestimates
                  (admissible), so A* stays optimal.
                </p>
                <p className="mt-2 font-mono text-xs text-yellow-400">
                  h = km / 0.333 min
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
