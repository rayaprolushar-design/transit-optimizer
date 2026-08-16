/**
 * app/predict.js — Delay Predictor tab
 * Slider-based delay prediction with p10/p50/p90 confidence intervals.
 * Calls POST /predict-delay-ci on your Railway backend.
 * Auto-predicts when stop or hour changes.
 */
import { useState, useEffect } from "react"
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Alert,
} from "react-native"
import Slider from "@react-native-community/slider"
import { Ionicons } from "@expo/vector-icons"
import { api } from "../api/client"
import { COLORS } from "../constants/config"

const S = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  body:      { padding: 14 },
  card:      { backgroundColor: COLORS.card, borderRadius: 12, padding: 14,
               borderWidth: 0.5, borderColor: COLORS.border, marginBottom: 12 },
  label:     { color: COLORS.sub, fontSize: 11, marginBottom: 8,
               textTransform: "uppercase", letterSpacing: 0.5 },
  row:       { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  val:       { color: COLORS.text, fontWeight: "600", fontSize: 13, fontVariant: ["tabular-nums"] },
  big:       { color: COLORS.text, fontSize: 48, fontWeight: "700",
               textAlign: "center", marginVertical: 8, fontVariant: ["tabular-nums"] },
  bigUnit:   { fontSize: 18, color: COLORS.sub, fontWeight: "400" },
  confBadge: { alignSelf: "center", paddingHorizontal: 14, paddingVertical: 5,
               borderRadius: 20, borderWidth: 0.5, marginBottom: 10 },
  confText:  { fontSize: 13, fontWeight: "600", textAlign: "center" },
  interp:    { color: COLORS.sub, fontSize: 13, textAlign: "center", lineHeight: 18 },
  ci:        { flexDirection: "row", justifyContent: "space-around", marginTop: 10 },
  ciBox:     { alignItems: "center" },
  ciLabel:   { color: COLORS.dim, fontSize: 11 },
  ciVal:     { fontWeight: "600", fontSize: 16, marginTop: 2, fontVariant:["tabular-nums"] },
  stopBtn:   { backgroundColor: COLORS.surface, borderRadius: 10, padding: 10,
               borderWidth: 0.5, borderColor: COLORS.border, marginBottom: 6 },
  stopText:  { color: COLORS.text, fontSize: 14 },
  stopSub:   { color: COLORS.dim, fontSize: 11 },
  toggle:    { flexDirection: "row", gap: 8, marginTop: 6 },
  pill:      { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20,
               borderWidth: 0.5 },
  pillText:  { fontSize: 12, fontWeight: "500" },
})

const CONF_COLORS = {
  high:   { bg:"#052e16", border:COLORS.teal,   text:COLORS.teal },
  medium: { bg:"#422006", border:COLORS.yellow, text:COLORS.yellow },
  low:    { bg:"#450a0a", border:COLORS.red,    text:COLORS.red },
}

function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

export default function DelayPredictor() {
  const [stops,      setStops]      = useState([])
  const [stop,       setStop]       = useState(null)
  const [hour,       setHour]       = useState(8)
  const [priorDelay, setPriorDelay] = useState(0)
  const [isWeekend,  setIsWeekend]  = useState(false)
  const [routeType,  setRouteType]  = useState(3)
  const [result,     setResult]     = useState(null)
  const [loading,    setLoading]    = useState(false)
  const [showStops,  setShowStops]  = useState(false)

  const dHour       = useDebounce(hour, 400)
  const dPriorDelay = useDebounce(priorDelay, 400)

  useEffect(() => {
    api.getStops().then(setStops).catch(() => {})
  }, [])

  useEffect(() => {
    if (!stop) return
    predict()
  }, [stop, dHour, isWeekend, dPriorDelay, routeType])

  const predict = async () => {
    if (!stop) return
    setLoading(true)
    try {
      const data = await api.predictCI({
        stop_id:            stop.stop_id,
        hour:               dHour,
        is_weekend:         isWeekend ? 1 : 0,
        prior_stop_delay:   dPriorDelay,
        temp_deviation:     0.5,
        stop_sequence_norm: 0.0,
        route_type:         routeType,
        n_stops_on_trip:    6,
      })
      setResult(data)
    } catch (e) {
      // fallback to regular prediction
      try {
        const data = await api.predictDelay({
          stop_id: stop.stop_id, hour: dHour, is_weekend: isWeekend ? 1 : 0,
          prior_stop_delay: dPriorDelay, temp_deviation: 0.5,
          stop_sequence_norm: 0.0, route_type: routeType, n_stops_on_trip: 6,
        })
        setResult({
          p50: data.predicted_delay, p10: Math.max(0, data.predicted_delay - data.model_mae),
          p90: data.predicted_delay + data.model_mae,
          confidence: data.confidence,
          interpretation: `Predicted delay: ${data.predicted_delay} min`,
        })
      } catch (_) {}
    } finally {
      setLoading(false)
    }
  }

  const isRush = (hour >= 7 && hour <= 10) || (hour >= 17 && hour <= 20)
  const conf   = result ? CONF_COLORS[result.confidence] ?? CONF_COLORS.medium : null

  return (
    <ScrollView style={S.container} contentContainerStyle={S.body}>

      {/* Stop picker */}
      <View style={S.card}>
        <Text style={S.label}>Select stop</Text>
        <TouchableOpacity style={S.stopBtn} onPress={() => setShowStops(v => !v)}>
          <Text style={S.stopText}>{stop ? stop.name : "Tap to select a stop…"}</Text>
          {stop && <Text style={S.stopSub}>{stop.stop_id}</Text>}
        </TouchableOpacity>
        {showStops && (
          <ScrollView style={{ maxHeight: 200 }} nestedScrollEnabled>
            {stops.map(s => (
              <TouchableOpacity key={s.stop_id} style={S.stopBtn}
                onPress={() => { setStop(s); setShowStops(false) }}>
                <Text style={S.stopText}>{s.name}</Text>
                <Text style={S.stopSub}>{s.stop_id}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}
      </View>

      {/* Controls */}
      <View style={S.card}>
        <View style={S.row}>
          <Text style={S.label}>Hour of departure</Text>
          <Text style={S.val}>
            {String(hour).padStart(2,"0")}:00
            {isRush ? "  🔴 Rush" : "  🟢 Off-peak"}
          </Text>
        </View>
        <Slider
          minimumValue={0} maximumValue={23} step={1} value={hour}
          onValueChange={setHour}
          minimumTrackTintColor={COLORS.brand}
          maximumTrackTintColor={COLORS.border}
          thumbTintColor={COLORS.brand}
        />

        <View style={[S.row, { marginTop: 12 }]}>
          <Text style={S.label}>Prior stop delay</Text>
          <Text style={S.val}>{priorDelay} min</Text>
        </View>
        <Slider
          minimumValue={0} maximumValue={15} step={0.5} value={priorDelay}
          onValueChange={setPriorDelay}
          minimumTrackTintColor={COLORS.yellow}
          maximumTrackTintColor={COLORS.border}
          thumbTintColor={COLORS.yellow}
        />

        <View style={[S.toggle, { marginTop: 10 }]}>
          {[{v:3,l:"🚌 Bus"},{v:1,l:"🚇 Metro"}].map(({v,l}) => (
            <TouchableOpacity key={v} style={[S.pill, {
              backgroundColor: routeType===v ? COLORS.brand+"22" : COLORS.card,
              borderColor:     routeType===v ? COLORS.brand       : COLORS.border,
            }]} onPress={() => setRouteType(v)}>
              <Text style={[S.pillText, { color: routeType===v ? COLORS.brand : COLORS.sub }]}>{l}</Text>
            </TouchableOpacity>
          ))}
          <TouchableOpacity style={[S.pill, {
            backgroundColor: isWeekend ? COLORS.teal+"22" : COLORS.card,
            borderColor:     isWeekend ? COLORS.teal       : COLORS.border,
          }]} onPress={() => setIsWeekend(v => !v)}>
            <Text style={[S.pillText, { color: isWeekend ? COLORS.teal : COLORS.sub }]}>
              {isWeekend ? "🌤 Weekend" : "Weekend"}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Result */}
      {!stop && (
        <View style={[S.card, { alignItems:"center", paddingVertical:30 }]}>
          <Ionicons name="time-outline" size={40} color={COLORS.dim} />
          <Text style={[S.interp, { marginTop: 8 }]}>Select a stop above to see predictions</Text>
        </View>
      )}

      {stop && loading && (
        <View style={[S.card, { alignItems:"center", paddingVertical:30 }]}>
          <ActivityIndicator color={COLORS.brand} />
          <Text style={[S.interp, { marginTop:8 }]}>Running model…</Text>
        </View>
      )}

      {stop && !loading && result && (
        <View style={S.card}>
          <Text style={[S.label, { textAlign:"center" }]}>
            {stop.name}
          </Text>
          <Text style={S.big}>
            {result.p50}
            <Text style={S.bigUnit}> min</Text>
          </Text>

          <View style={[S.confBadge, {
            backgroundColor: conf?.bg, borderColor: conf?.border,
          }]}>
            <Text style={[S.confText, { color: conf?.text }]}>
              {result.confidence} confidence
            </Text>
          </View>

          <Text style={S.interp}>{result.interpretation}</Text>

          {/* CI bar */}
          <View style={S.ci}>
            <View style={S.ciBox}>
              <Text style={S.ciLabel}>p10 (best)</Text>
              <Text style={[S.ciVal, { color: COLORS.teal }]}>{result.p10}m</Text>
            </View>
            <View style={S.ciBox}>
              <Text style={S.ciLabel}>p50 (median)</Text>
              <Text style={[S.ciVal, { color: COLORS.text }]}>{result.p50}m</Text>
            </View>
            <View style={S.ciBox}>
              <Text style={S.ciLabel}>p90 (worst)</Text>
              <Text style={[S.ciVal, { color: COLORS.red }]}>{result.p90}m</Text>
            </View>
          </View>

          <Text style={[S.interp, { marginTop: 10, fontSize: 11 }]}>
            Model MAE: ±{result.model_mae ?? "0.76"} min
            {result.cached ? "  ·  ⚡ cached" : ""}
          </Text>
        </View>
      )}
    </ScrollView>
  )
}
