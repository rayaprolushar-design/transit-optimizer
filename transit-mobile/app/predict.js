/**
 * app/predict.js — Delay Predictor (auto-detect redesign)
 * - No manual sliders
 * - Auto-reads live GPS delay from /live-delays/{stop_id}
 * - Shows p10/p50/p90 cleanly
 * - Stop picker is the only input needed
 */
import { useState, useEffect, useCallback } from "react"
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from "react-native"
import { Ionicons } from "@expo/vector-icons"
import { api } from "../api/client"
import { COLORS } from "../constants/config"

const S = StyleSheet.create({
  container:   { flex: 1, backgroundColor: COLORS.bg },
  stopGrid:    { flexDirection: "row", flexWrap: "wrap", gap: 8, padding: 12 },
  stopChip:    { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20,
                 borderWidth: 0.5, minWidth: "44%" },
  stopText:    { fontSize: 13, fontWeight: "500", textAlign: "center" },
  section:     { paddingHorizontal: 14, marginTop: 6 },
  sLabel:      { color: COLORS.sub, fontSize: 11, textTransform: "uppercase",
                 letterSpacing: 0.5, marginBottom: 8 },
  card:        { backgroundColor: COLORS.card, borderRadius: 14, padding: 16,
                 borderWidth: 0.5, borderColor: COLORS.border, marginBottom: 12 },
  bigDelay:    { fontSize: 52, fontWeight: "800", textAlign: "center",
                 fontVariant: ["tabular-nums"], marginVertical: 4 },
  unit:        { fontSize: 20, fontWeight: "400" },
  confBadge:   { alignSelf: "center", paddingHorizontal: 16, paddingVertical: 6,
                 borderRadius: 20, borderWidth: 0.5, marginBottom: 8 },
  confText:    { fontSize: 13, fontWeight: "600", textAlign: "center" },
  interp:      { color: COLORS.sub, fontSize: 13, textAlign: "center",
                 lineHeight: 18, marginBottom: 12 },
  ciRow:       { flexDirection: "row", justifyContent: "space-around",
                 paddingTop: 12, borderTopWidth: 0.5, borderTopColor: COLORS.border },
  ciBox:       { alignItems: "center" },
  ciLabel:     { color: COLORS.dim, fontSize: 11 },
  ciVal:       { fontWeight: "700", fontSize: 17, marginTop: 3,
                 fontVariant: ["tabular-nums"] },
  infoRow:     { flexDirection: "row", alignItems: "center", gap: 8,
                 marginTop: 12, padding: 10, backgroundColor: COLORS.surface,
                 borderRadius: 10 },
  infoText:    { color: COLORS.sub, fontSize: 12, flex: 1, lineHeight: 17 },
  autoTag:     { flexDirection: "row", alignItems: "center", gap: 4,
                 alignSelf: "center", marginBottom: 6 },
  autoText:    { color: COLORS.teal, fontSize: 12, fontWeight: "500" },
  emptyState:  { alignItems: "center", paddingVertical: 40 },
  emptyText:   { color: COLORS.dim, fontSize: 14, marginTop: 10 },
})

const CONF_COLORS = {
  high:   { bg:"#052e16", border:COLORS.teal,   text:COLORS.teal },
  medium: { bg:"#422006", border:COLORS.yellow, text:COLORS.yellow },
  low:    { bg:"#450a0a", border:COLORS.red,    text:COLORS.red },
}

// Quick stops for one-tap selection
const QUICK_STOPS = [
  { stop_id:"S001", name:"MG Road" },
  { stop_id:"S004", name:"Indiranagar" },
  { stop_id:"S006", name:"Koramangala" },
  { stop_id:"S007", name:"BTM Layout" },
  { stop_id:"S017", name:"HSR Layout" },
  { stop_id:"S020", name:"Silk Board" },
  { stop_id:"S013", name:"Hebbal" },
  { stop_id:"S021", name:"MG Road Metro" },
]

function formatDelay(min) {
  if (min < 1)  return "On time"
  if (min < 60) return `${Math.round(min)} min`
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

export default function DelayPredictor() {
  const [stop,     setStop]     = useState(null)
  const [result,   setResult]   = useState(null)
  const [live,     setLive]     = useState(null)     // live GPS delay
  const [loading,  setLoading]  = useState(false)
  const [refresh,  setRefresh]  = useState(false)

  const fetchPrediction = useCallback(async (s, isRefresh = false) => {
    if (!s) return
    if (isRefresh) setRefresh(true)
    else           setLoading(true)

    try {
      // 1. Get live GPS delay for this stop (seeds prior_stop_delay)
      const liveData = await api.stopDelay(s.stop_id).catch(() => null)
      const priorDelay = liveData?.live_delay_min ?? 0
      setLive(liveData)

      // 2. Auto-detect current hour
      const hour     = new Date().getHours()
      const isWknd   = new Date().getDay() >= 6 ? 1 : 0

      // 3. Call ML model with real context
      const pred = await api.predictCI({
        stop_id:            s.stop_id,
        hour,
        is_weekend:         isWknd,
        prior_stop_delay:   priorDelay,
        temp_deviation:     0.5,
        stop_sequence_norm: 0.0,
        route_type:         3,
        n_stops_on_trip:    6,
      }).catch(async () => {
        // Fallback to regular predict
        const d = await api.predictDelay({
          stop_id: s.stop_id, hour, is_weekend: isWknd,
          prior_stop_delay: priorDelay, temp_deviation: 0.5,
          stop_sequence_norm: 0.0, route_type: 3, n_stops_on_trip: 6,
        })
        return {
          p10: Math.max(0, d.predicted_delay - (d.model_mae ?? 0.76)),
          p50: d.predicted_delay,
          p90: d.predicted_delay + (d.model_mae ?? 0.76),
          confidence: d.confidence,
          interpretation: `Predicted: ${d.predicted_delay} min`,
          model_mae: d.model_mae,
        }
      })
      setResult(pred)
    } catch (e) {
      console.log(e)
    } finally {
      setLoading(false)
      setRefresh(false)
    }
  }, [])

  const selectStop = (s) => {
    setStop(s)
    setResult(null)
    fetchPrediction(s)
  }

  // Auto-refresh every 30s when a stop is selected
  useEffect(() => {
    if (!stop) return
    const t = setInterval(() => fetchPrediction(stop, true), 30000)
    return () => clearInterval(t)
  }, [stop, fetchPrediction])

  const hour = new Date().getHours()
  const isRush = (hour >= 7 && hour <= 10) || (hour >= 17 && hour <= 20)
  const conf = result ? (CONF_COLORS[result.confidence] ?? CONF_COLORS.medium) : null

  // Clamp p50 to realistic range (0-60 min)
  const p50Display = result ? Math.min(result.p50 ?? 0, 60) : 0
  const p10Display = result ? Math.min(result.p10 ?? 0, 60) : 0
  const p90Display = result ? Math.min(result.p90 ?? 0, 60) : 0

  return (
    <ScrollView
      style={S.container}
      refreshControl={
        <RefreshControl
          refreshing={refresh}
          onRefresh={() => fetchPrediction(stop, true)}
          tintColor={COLORS.brand}
        />
      }
    >
      {/* Stop quick-select */}
      <View style={S.section}>
        <Text style={[S.sLabel, { marginTop: 14 }]}>Select your stop</Text>
      </View>
      <View style={S.stopGrid}>
        {QUICK_STOPS.map(s => {
          const active = stop?.stop_id === s.stop_id
          return (
            <TouchableOpacity
              key={s.stop_id}
              style={[S.stopChip, {
                backgroundColor: active ? COLORS.brand+"22" : COLORS.card,
                borderColor:     active ? COLORS.brand       : COLORS.border,
              }]}
              onPress={() => selectStop(s)}
            >
              <Text style={[S.stopText, { color: active ? COLORS.brand : COLORS.sub }]}>
                {s.name}
              </Text>
            </TouchableOpacity>
          )
        })}
      </View>

      {/* Empty state */}
      {!stop && (
        <View style={S.emptyState}>
          <Ionicons name="time-outline" size={48} color={COLORS.dim} />
          <Text style={S.emptyText}>Tap a stop to see delay prediction</Text>
          <Text style={{ color: COLORS.dim, fontSize: 12, marginTop: 4 }}>
            Uses live GPS + current time automatically
          </Text>
        </View>
      )}

      {/* Loading */}
      {stop && loading && (
        <View style={[S.card, { marginHorizontal: 14, alignItems: "center", padding: 30 }]}>
          <ActivityIndicator color={COLORS.brand} size="large" />
          <Text style={{ color: COLORS.sub, marginTop: 10, fontSize: 13 }}>
            Reading live GPS data…
          </Text>
        </View>
      )}

      {/* Result */}
      {stop && !loading && result && (
        <View style={{ paddingHorizontal: 14 }}>

          {/* Auto-detect badge */}
          <View style={S.autoTag}>
            <Ionicons name="locate" size={13} color={COLORS.teal} />
            <Text style={S.autoText}>
              Auto-detected · {String(hour).padStart(2,"0")}:00
              {isRush ? " · Rush hour" : " · Off-peak"}
              {live?.has_live_data ? " · Live GPS" : ""}
            </Text>
          </View>

          {/* Big prediction */}
          <View style={S.card}>
            <Text style={{ color: COLORS.sub, fontSize: 13, textAlign: "center" }}>
              {stop.name}
            </Text>
            <Text style={[S.bigDelay, {
              color: p50Display > 10 ? COLORS.red :
                     p50Display > 3  ? COLORS.yellow : COLORS.teal
            }]}>
              {formatDelay(p50Display)}
            </Text>

            <View style={[S.confBadge, { backgroundColor: conf.bg, borderColor: conf.border }]}>
              <Text style={[S.confText, { color: conf.text }]}>
                {result.confidence} confidence
              </Text>
            </View>

            <Text style={S.interp}>{result.interpretation}</Text>

            {/* p10 / p50 / p90 */}
            <View style={S.ciRow}>
              <View style={S.ciBox}>
                <Text style={S.ciLabel}>Best case</Text>
                <Text style={[S.ciVal, { color: COLORS.teal }]}>
                  {formatDelay(p10Display)}
                </Text>
              </View>
              <View style={[S.ciBox, {
                paddingHorizontal: 20,
                borderLeftWidth: 0.5, borderRightWidth: 0.5,
                borderColor: COLORS.border,
              }]}>
                <Text style={S.ciLabel}>Expected</Text>
                <Text style={[S.ciVal, { color: COLORS.text }]}>
                  {formatDelay(p50Display)}
                </Text>
              </View>
              <View style={S.ciBox}>
                <Text style={S.ciLabel}>Worst case</Text>
                <Text style={[S.ciVal, { color: COLORS.red }]}>
                  {formatDelay(p90Display)}
                </Text>
              </View>
            </View>
          </View>

          {/* Live GPS info */}
          {live && (
            <View style={S.infoRow}>
              <Ionicons name="navigate-circle" size={18} color={COLORS.teal} />
              <Text style={S.infoText}>
                {live.has_live_data
                  ? `Live GPS: bus at ${stop.name} is currently ${live.live_delay_min > 0
                      ? `+${live.live_delay_min?.toFixed(1)} min late`
                      : "on time"}.`
                  : "No live GPS data for this stop yet — using model estimate."
                }
              </Text>
            </View>
          )}

          <Text style={{ color: COLORS.dim, fontSize: 11, textAlign: "center",
                         marginTop: 8, marginBottom: 20 }}>
            Pull down to refresh · Auto-updates every 30s
          </Text>
        </View>
      )}
    </ScrollView>
  )
}
