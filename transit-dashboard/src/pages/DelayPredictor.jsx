/**
 * pages/DelayPredictor.jsx — Week 21
 * Interactive delay predictor with:
 *   - Live-updating predictions as sliders move (debounced API calls)
 *   - PredictionHistoryChart showing delay curve across all hours
 *   - Feature importance mini-chart (what the model is using)
 *   - Comparison card: rush hour vs off-peak vs weekend for the selected stop
 *
 * Key React concepts:
 *   useCallback + debounce  — avoid hammering the API on every slider tick
 *   useEffect dependency    — re-fetch when any input changes
 *   derived state           — confidence, isRush computed from raw values
 */
import { useState, useEffect } from 'react'
import { Brain, Info, TrendingUp } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import StopSearch             from '../components/StopSearch'
import ErrorBanner            from '../components/ErrorBanner'
import LoadingSpinner         from '../components/LoadingSpinner'
import TopBar                 from '../components/TopBar'
import PredictionHistoryChart from '../components/PredictionHistoryChart'
import { useStops }           from '../hooks/useStops'
import { api }                from '../api/client'

// ── Feature importances from Week 15 model ────────────────────────────────────
const FEATURE_IMPORTANCES = [
  { name: 'prior_delay',  value: 94.8, color: '#1D9E75' },
  { name: 'seq_norm',     value: 1.58, color: '#378ADD' },
  { name: 'is_rush',      value: 0.87, color: '#EF9F27' },
  { name: 'hour',         value: 0.85, color: '#EF9F27' },
  { name: 'temp_dev',     value: 0.82, color: '#6b7280' },
  { name: 'route_type',   value: 0.71, color: '#6b7280' },
]

const CONF_STYLES = {
  high:   { badge: 'badge-green',  label: 'High confidence',   icon: '✓' },
  medium: { badge: 'badge-yellow', label: 'Medium confidence',  icon: '~' },
  low:    { badge: 'badge-red',    label: 'Low confidence',     icon: '!' },
}

// Simple debounce hook
function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

export default function DelayPredictor() {
  const { stops, loading: stopsLoading, error: stopsError } = useStops()

  // ── Input state ───────────────────────────────────────────────────────────
  const [stopName,   setStopName]   = useState('')
  const [hour,       setHour]       = useState(8)
  const [isWeekend,  setIsWeekend]  = useState(false)
  const [priorDelay, setPriorDelay] = useState(0)
  const [seqNorm,    setSeqNorm]    = useState(0)
  const [routeType,  setRouteType]  = useState(3)

  // ── Output state ──────────────────────────────────────────────────────────
  const [result,   setResult]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)
  const [compares, setCompares] = useState(null)  // rush/offpeak/weekend compare

  // Debounce slider inputs so we don't spam the API
  const dHour       = useDebounce(hour, 300)
  const dPriorDelay = useDebounce(priorDelay, 300)
  const dSeqNorm    = useDebounce(seqNorm, 300)

  const selectedStop = stops.find(s => s.name === stopName)

  const predict = async (stopId, h, weekend, prior, seq, rtype) => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.predictDelay({
        stop_id:            stopId,
        hour:               h,
        is_weekend:         weekend,
        prior_stop_delay:   prior,
        temp_deviation:     0.5,
        stop_sequence_norm: seq,
        route_type:         rtype,
        n_stops_on_trip:    6,
      })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // ── Auto-predict when inputs change ───────────────────────────────────────
  useEffect(() => {
    if (!selectedStop) return
    predict(selectedStop.stop_id, dHour, isWeekend ? 1 : 0, dPriorDelay, dSeqNorm, routeType)
  }, [selectedStop, dHour, isWeekend, dPriorDelay, dSeqNorm, routeType])

  // ── Comparison predictions (rush / off-peak / weekend) ────────────────────
  useEffect(() => {
    if (!selectedStop) return
    const sid = selectedStop.stop_id
    Promise.all([
      api.predictDelay({ stop_id: sid, hour: 8,  is_weekend: 0, prior_stop_delay: 0, temp_deviation: 0.5, stop_sequence_norm: 0, route_type: routeType, n_stops_on_trip: 6 }),
      api.predictDelay({ stop_id: sid, hour: 14, is_weekend: 0, prior_stop_delay: 0, temp_deviation: 0.5, stop_sequence_norm: 0, route_type: routeType, n_stops_on_trip: 6 }),
      api.predictDelay({ stop_id: sid, hour: 10, is_weekend: 1, prior_stop_delay: 0, temp_deviation: 0.5, stop_sequence_norm: 0, route_type: routeType, n_stops_on_trip: 6 }),
    ]).then(([rush, offpeak, weekend]) => {
      setCompares({ rush, offpeak, weekend })
    }).catch(() => {})
  }, [selectedStop, routeType])

  const isRush = (hour >= 7 && hour <= 10) || (hour >= 17 && hour <= 20)
  const conf   = result ? CONF_STYLES[result.confidence] : null

  return (
    <div>
      <TopBar
        title="Delay Predictor"
        subtitle="Gradient Boosting model · MAE ≈ 0.76 min · predicts live as you drag"
      />

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4 items-start mt-4">

        {/* ── LEFT: Controls ──────────────────────────────────────── */}
        <div className="space-y-3">
          <div className="card">
            <p className="card-title text-sm font-bold text-slate-200">Inputs</p>

            {/* Stop picker */}
            <div className="mb-4">
              <label className="block text-xs text-gray-500 mb-1.5">Stop</label>
              <StopSearch
                stops={stops}
                value={stopName}
                onChange={setStopName}
                placeholder="Select a stop…"
              />
            </div>

            {/* Route type */}
            <div className="mb-4">
              <label className="block text-xs text-gray-500 mb-1.5">Route type</label>
              <div className="flex gap-2">
                {[{ v: 3, l: '🚌 Bus' }, { v: 1, l: '🚇 Metro' }].map(({ v, l }) => (
                  <button
                    key={v}
                    onClick={() => setRouteType(v)}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-colors
                      ${routeType === v
                        ? 'bg-brand-500/20 text-brand-400 border-brand-500/40'
                        : 'text-gray-500 border-gray-700 hover:text-gray-300'}`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Hour slider */}
            <div className="mb-4">
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs text-gray-500">Hour of departure</label>
                <div className="flex items-center gap-2">
                  <span className={`badge text-[11px] ${isRush ? 'badge-red' : 'badge-green'}`}>
                    {isRush ? '⚠ Rush' : 'Off-peak'}
                  </span>
                  <span className="font-mono text-sm text-gray-300">
                    {String(hour).padStart(2, '0')}:00
                  </span>
                </div>
              </div>
              <input
                type="range" min="0" max="23" step="1" value={hour}
                onChange={e => setHour(Number(e.target.value))}
                className="w-full accent-brand-500 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span>
              </div>
            </div>

            {/* Prior delay slider */}
            <div className="mb-4">
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs text-gray-500">Prior stop delay</label>
                <span className="font-mono text-sm text-gray-300">{priorDelay} min</span>
              </div>
              <input
                type="range" min="0" max="15" step="0.5" value={priorDelay}
                onChange={e => setPriorDelay(Number(e.target.value))}
                className="w-full accent-brand-500 cursor-pointer"
              />
              <p className="text-[10px] text-gray-600 mt-1 leading-relaxed">
                Delay at the previous stop — strongest predictor (r=0.89)
              </p>
            </div>

            {/* Seq norm slider */}
            <div className="mb-4">
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs text-gray-500">Position in trip</label>
                <span className="font-mono text-sm text-gray-300">
                  {seqNorm === 0 ? 'First stop' : seqNorm === 1 ? 'Last stop' : `${Math.round(seqNorm * 100)}%`}
                </span>
              </div>
              <input
                type="range" min="0" max="1" step="0.1" value={seqNorm}
                onChange={e => setSeqNorm(Number(e.target.value))}
                className="w-full accent-brand-500 cursor-pointer"
              />
            </div>

            {/* Weekend toggle */}
            <label className="flex items-center gap-3 cursor-pointer select-none">
              <div
                onClick={() => setIsWeekend(w => !w)}
                className={`relative w-10 h-5 rounded-full transition-colors
                  ${isWeekend ? 'bg-brand-primary' : 'bg-gray-700'}`}
              >
                <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow
                                 transition-transform duration-200
                                 ${isWeekend ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </div>
              <span className="text-sm text-gray-300">Weekend</span>
              {isWeekend && <span className="text-xs text-teal-400">~38% less delay</span>}
            </label>
          </div>

          {/* Loading / Error */}
          {stopsLoading && <LoadingSpinner text="Loading stops…" />}
          {(error || stopsError) && <ErrorBanner message={error ?? stopsError} />}

          {/* Comparison card */}
          {compares && (
            <div className="card">
              <p className="card-title text-sm font-bold text-slate-200">Compare scenarios</p>
              {[
                { label: '🚨 Rush hour (08:00)',  val: compares.rush?.predicted_delay,    color: 'text-red-400' },
                { label: '😌 Off-peak (14:00)',   val: compares.offpeak?.predicted_delay, color: 'text-yellow-400' },
                { label: '🌤 Weekend (10:00)',     val: compares.weekend?.predicted_delay, color: 'text-teal-400' },
              ].map(({ label, val, color }) => (
                <div key={label}
                  className="flex items-center justify-between py-2.5 border-b border-gray-800 last:border-0 text-sm">
                  <span className="text-gray-400">{label}</span>
                  <span className={`font-mono font-medium ${color}`}>
                    {val != null ? `${val} min` : '—'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── RIGHT: Result + charts ───────────────────────────────── */}
        <div className="space-y-4">

          {/* Big prediction result */}
          <div className="card">
            {!selectedStop ? (
              <div className="flex flex-col items-center justify-center py-10 text-gray-600">
                <Brain className="w-12 h-12 mb-3 opacity-20" />
                <p className="text-sm">Select a stop to see predictions</p>
                <p className="text-xs mt-1">Predictions update live as you drag the sliders</p>
              </div>
            ) : (
              <div>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs text-gray-500 mb-0.5">{result?.stop_name ?? stopName}</p>
                    <div className="flex items-baseline gap-2">
                      {loading ? (
                        <div className="h-12 flex items-center">
                          <LoadingSpinner text="Predicting…" />
                        </div>
                      ) : (
                        <>
                          <span className="text-5xl font-semibold font-mono text-gray-100">
                            {result?.predicted_delay ?? '—'}
                          </span>
                          <span className="text-xl text-gray-500">min delay</span>
                        </>
                      )}
                    </div>
                  </div>
                  {conf && !loading && (
                    <div className="text-right">
                      <span className={`badge ${conf.badge} text-sm px-3 py-1.5`}>
                        {conf.icon} {conf.label}
                      </span>
                      {result?.cached && (
                        <p className="text-[10px] text-teal-600 mt-1">⚡ cached</p>
                      )}
                    </div>
                  )}
                </div>

                {/* Input summary pills */}
                <div className="flex flex-wrap gap-1.5 text-[11px]">
                  <span className="badge badge-blue font-mono">
                    {String(hour).padStart(2,'0')}:00
                  </span>
                  {isRush && <span className="badge badge-red">Rush hour</span>}
                  {isWeekend && <span className="badge badge-green">Weekend</span>}
                  <span className="badge text-gray-500 bg-gray-800 border-gray-700">
                    Prior: {priorDelay}m
                  </span>
                  <span className="badge text-gray-500 bg-gray-800 border-gray-700">
                    {routeType === 1 ? 'Metro' : 'Bus'}
                  </span>
                  <span className="badge text-gray-500 bg-gray-800 border-gray-700">
                    MAE ±{result?.model_mae ?? '0.76'}m
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Prediction history chart */}
          <div className="card">
            <p className="card-title flex items-center gap-1.5 text-sm font-bold text-slate-200">
              <TrendingUp className="w-3.5 h-3.5 text-brand-neonBlue" />
              Delay curve — all hours
            </p>
            <PredictionHistoryChart hour={hour} routeType={routeType} />
          </div>

          {/* Feature importance mini chart */}
          <div className="card">
            <p className="card-title flex items-center gap-1.5 text-sm font-bold text-slate-200">
              <Info className="w-3.5 h-3.5 text-brand-neonPurple" />
              What the model is using
            </p>
            <p className="text-xs text-gray-600 mb-3">
              Feature importances from Random Forest (Week 14)
            </p>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart
                data={FEATURE_IMPORTANCES}
                layout="vertical"
                margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
              >
                <XAxis
                  type="number"
                  tick={{ fill: '#4b5563', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  unit="%"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={72}
                />
                <Tooltip
                  formatter={v => [`${v}%`, 'Importance']}
                  contentStyle={{
                    background: '#1f2937',
                    border: '1px solid #374151',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  cursor={{ fill: '#ffffff06' }}
                />
                <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14}>
                  {FEATURE_IMPORTANCES.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-gray-600 mt-2 leading-relaxed">
              prior_delay dominates at 94.8% — delay propagates stop-to-stop.
              At first stop (seq=0), temporal features take over.
            </p>
          </div>

        </div>
      </div>
    </div>
  )
}
