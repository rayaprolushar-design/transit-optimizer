/**
 * pages/RoutePlanner.jsx — Week 19
 * Full layout: search form + directions panel on the left,
 * live Leaflet map on the right.
 *
 * Layout:
 *   ┌─────────────────────┬──────────────────────┐
 *   │ Search form         │                      │
 *   │ Algorithm toggle    │   Leaflet map        │
 *   │ Find route btn      │   (stops + route)    │
 *   ├─────────────────────│                      │
 *   │ Route result card   │                      │
 *   │ (directions)        │                      │
 *   └─────────────────────┴──────────────────────┘
 */
import { useState, Suspense, lazy } from 'react'
import { ArrowRight, Zap, Clock, GitBranch, ArrowLeftRight } from 'lucide-react'
import StopSearch     from '../components/StopSearch'
import ErrorBanner    from '../components/ErrorBanner'
import LoadingSpinner from '../components/LoadingSpinner'
import TopBar         from '../components/TopBar'
import { useStops }   from '../hooks/useStops'
import { useRoute }   from '../hooks/useRoute'

// Lazy-load map so Leaflet doesn't delay initial paint
const TransitMap = lazy(() => import('../components/TransitMap'))

const ALGO_OPTIONS = [
  { value: 'astar',    label: 'A*',       hint: 'Guided by Haversine heuristic' },
  { value: 'dijkstra', label: 'Dijkstra', hint: 'Exhaustive — explores all nodes' },
]

export default function RoutePlanner() {
  const { stops, loading: stopsLoading, error: stopsError } = useStops()
  const { result, loading, error, search } = useRoute()

  const [from,      setFrom]      = useState('')
  const [to,        setTo]        = useState('')
  const [algorithm, setAlgorithm] = useState('astar')
  const [apiError,  setApiError]  = useState(null)

  // Called when user clicks a stop marker on the map
  const handleMapStopClick = (stopName, role) => {
    if (role === 'from' || (!from && role !== 'to')) setFrom(stopName)
    else setTo(stopName)
  }

  const handleSwap = () => {
    setFrom(to)
    setTo(from)
  }

  const handleSearch = async () => {
    setApiError(null)
    try {
      await search(from, to, algorithm)
    } catch (e) {
      setApiError(e.message)
    }
  }

  const canSearch = from.trim() && to.trim() && from !== to && !loading

  return (
    <div>
      <TopBar
        title="Route Planner"
        subtitle="Click stops on the map or type below — A* finds the fastest path"
      />

      {/* ── Two-column layout ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4 items-start mt-4">

        {/* ── LEFT: form + result ──────────────────────────────────── */}
        <div className="space-y-3">

          {/* Search card */}
          <div className="card">
            <div className="space-y-2 mb-3">
              <StopSearch
                stops={stops}
                value={from}
                onChange={setFrom}
                placeholder="From stop…"
                icon="from"
              />

              {/* Swap button */}
              <div className="flex justify-center">
                <button
                  onClick={handleSwap}
                  className="p-1.5 rounded-full bg-gray-800 border border-gray-700
                             hover:bg-gray-700 transition-colors text-gray-400 hover:text-gray-200"
                  title="Swap stops"
                >
                  <ArrowLeftRight className="w-3.5 h-3.5" />
                </button>
              </div>

              <StopSearch
                stops={stops}
                value={to}
                onChange={setTo}
                placeholder="To stop…"
                icon="to"
              />
            </div>

            {/* Algorithm pills */}
            <div className="flex gap-2 mb-3">
              {ALGO_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setAlgorithm(opt.value)}
                  title={opt.hint}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
                    ${algorithm === opt.value
                      ? 'bg-brand-500/20 text-brand-400 border-brand-500/40'
                      : 'text-gray-500 border-gray-700 hover:text-gray-300 hover:border-gray-600'}`}
                >
                  {opt.label}
                </button>
              ))}
              <span className="text-xs text-gray-600 self-center ml-1 leading-tight">
                {ALGO_OPTIONS.find(o => o.value === algorithm)?.hint}
              </span>
            </div>

            <button
              onClick={handleSearch}
              disabled={!canSearch}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              <Zap className="w-4 h-4" />
              {loading ? 'Searching…' : 'Find fastest route'}
            </button>
          </div>

          {/* Loading / error states */}
          {(stopsLoading || loading) && (
            <LoadingSpinner text={stopsLoading ? 'Loading stops…' : 'Running algorithm…'} />
          )}
          {(error || apiError || stopsError) && (
            <ErrorBanner
              message={error ?? apiError ?? stopsError}
              onDismiss={() => setApiError(null)}
            />
          )}

          {/* Route result */}
          {result && !loading && (
            <div className="card animate-slide-down">

              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5 text-sm font-medium text-gray-200 min-w-0">
                  <span className="truncate">{result.from_stop}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
                  <span className="truncate">{result.to_stop}</span>
                </div>
                <span className="text-lg font-semibold text-teal-400 flex-shrink-0 ml-2">
                  {result.total_minutes} min
                </span>
              </div>

              {/* Meta badges */}
              <div className="flex flex-wrap gap-1.5 mb-3">
                <span className="badge badge-blue text-[11px] flex items-center">
                  <Zap className="w-2.5 h-2.5 mr-1" />{result.algorithm}
                </span>
                <span className="badge badge-green text-[11px] flex items-center">
                  <GitBranch className="w-2.5 h-2.5 mr-1" />
                  {result.segments} seg
                </span>
                <span className="badge badge-yellow text-[11px] flex items-center">
                  <Clock className="w-2.5 h-2.5 mr-1" />
                  {result.transfers} xfer
                </span>
                {result.cached && (
                  <span className="badge badge-green text-[11px] flex items-center">⚡ cached</span>
                )}
                <span className="badge text-gray-500 bg-gray-800 border-gray-700 font-mono text-[10px]">
                  {result.nodes_visited} nodes · {result.elapsed_ms}ms
                </span>
              </div>

              {/* Step-by-step directions */}
              <div className="space-y-1.5">
                {result.directions.map((step, i) => (
                  <div
                    key={i}
                    className={`rounded-lg px-3 py-2.5 text-sm
                      ${step.type === 'walk'
                        ? 'bg-amber-900/20 border border-amber-800/40'
                        : 'bg-blue-900/15 border border-blue-800/30'}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2 min-w-0">
                        <span className="text-base flex-shrink-0 mt-0.5">
                          {step.type === 'walk' ? '🚶' : '🚌'}
                        </span>
                        <div className="min-w-0">
                          {step.type === 'transit' ? (
                            <>
                              <span className="font-medium text-gray-200">
                                Route {step.route}
                              </span>
                              <span className="text-gray-400 text-xs block truncate">
                                {step.from} → {step.to}
                                {step.stops != null && ` · ${step.stops} stop${step.stops !== 1 ? 's' : ''}`}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="text-amber-300 font-medium">Walk</span>
                              <span className="text-gray-400 text-xs block truncate">
                                {step.from} → {step.to}
                                {step.dist_km && ` · ${Math.round(step.dist_km * 1000)}m`}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                      <span className="text-gray-400 text-xs font-mono flex-shrink-0 mt-0.5">
                        {step.minutes}m
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT: Leaflet map ───────────────────────────────────── */}
        <div className="card p-0 overflow-hidden" style={{ height: '600px' }}>
          <Suspense
            fallback={
              <div className="w-full h-full flex items-center justify-center bg-gray-900 rounded-xl">
                <LoadingSpinner text="Loading map…" />
              </div>
            }
          >
            {!stopsLoading && (
              <TransitMap
                stops={stops}
                route={result}
                fromStop={from}
                toStop={to}
                onStopClick={handleMapStopClick}
              />
            )}
          </Suspense>
        </div>

      </div>

      {/* ── Map legend ────────────────────────────────────────────── */}
      {stops.length > 0 && (
        <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-blue-500 inline-block" />From stop
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-teal-500 inline-block" />To stop
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-yellow-500 inline-block" />On route
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-gray-600 inline-block" />Other stop
          </span>
          <span className="flex items-center gap-1.5 ml-auto">
            Click any stop marker to set it as From / To
          </span>
        </div>
      )}
    </div>
  )
}
