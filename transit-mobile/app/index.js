/**
 * app/index.js — Route Planner (clean redesign)
 * - Simple two-input search, no algorithm toggle visible by default
 * - Map shows route polyline properly
 * - Step cards are compact and readable
 */
import { useState, useEffect } from "react"
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, ScrollView, ActivityIndicator,
} from "react-native"
import MapView, { Marker, Polyline } from "react-native-maps"
import { Ionicons } from "@expo/vector-icons"
import { api } from "../api/client"
import { COLORS, BENGALURU } from "../constants/config"

const S = StyleSheet.create({
  container:  { flex: 1, backgroundColor: COLORS.bg },
  map:        { height: 220 },
  searchBox:  { backgroundColor: COLORS.card, margin: 12, borderRadius: 14,
                borderWidth: 0.5, borderColor: COLORS.border, overflow: "hidden" },
  inputRow:   { flexDirection: "row", alignItems: "center", paddingHorizontal: 12,
                paddingVertical: 10, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  dot:        { width: 10, height: 10, borderRadius: 5, marginRight: 10 },
  input:      { flex: 1, color: COLORS.text, fontSize: 14 },
  swapBtn:    { padding: 8 },
  searchBtn:  { flexDirection: "row", alignItems: "center", justifyContent: "center",
                gap: 8, padding: 12, backgroundColor: COLORS.brand },
  searchText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  dropdown:   { backgroundColor: COLORS.surface, borderWidth: 0.5,
                borderColor: COLORS.border, borderRadius: 10,
                marginHorizontal: 12, marginTop: -4, maxHeight: 160, zIndex: 99 },
  dropItem:   { padding: 12, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  dropText:   { color: COLORS.text, fontSize: 13 },
  resultCard: { marginHorizontal: 12, backgroundColor: COLORS.card, borderRadius: 14,
                borderWidth: 0.5, borderColor: COLORS.border, overflow: "hidden" },
  resultHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center",
                padding: 14 },
  resultTitle:{ color: COLORS.text, fontWeight: "700", fontSize: 15, flex: 1 },
  resultTime: { color: COLORS.teal, fontWeight: "800", fontSize: 20 },
  metaRow:    { flexDirection: "row", gap: 8, paddingHorizontal: 14, paddingBottom: 10 },
  metaPill:   { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20,
                backgroundColor: COLORS.surface, borderWidth: 0.5, borderColor: COLORS.border },
  metaText:   { color: COLORS.sub, fontSize: 11 },
  step:       { flexDirection: "row", alignItems: "flex-start", gap: 10,
                padding: 12, borderTopWidth: 0.5, borderTopColor: COLORS.border },
  stepIcon:   { width: 28, height: 28, borderRadius: 14, alignItems: "center",
                justifyContent: "center", flexShrink: 0 },
  stepLabel:  { color: COLORS.text, fontSize: 13, fontWeight: "500", flex: 1 },
  stepSub:    { color: COLORS.sub, fontSize: 11, marginTop: 2 },
  stepTime:   { color: COLORS.sub, fontSize: 12, fontVariant: ["tabular-nums"] },
  emptyMap:   { position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
                alignItems: "center", justifyContent: "center",
                backgroundColor: COLORS.surface },
  scroll:     { flex: 1 },
})

export default function RoutePlanner() {
  const [stops,       setStops]       = useState([])
  const [fromText,    setFromText]    = useState("")
  const [toText,      setToText]      = useState("")
  const [fromStop,    setFromStop]    = useState(null)
  const [toStop,      setToStop]      = useState(null)
  const [activeField, setActiveField] = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [result,      setResult]      = useState(null)
  const [error,       setError]       = useState("")

  useEffect(() => {
    api.getStops().then(setStops).catch(() => {})
  }, [])

  const filtered = (q) => q.length < 1 ? [] :
    stops.filter(s => s.name.toLowerCase().includes(q.toLowerCase())).slice(0, 6)

  const pick = (stop, field) => {
    if (field === "from") { setFromStop(stop); setFromText(stop.name) }
    else                  { setToStop(stop);   setToText(stop.name)   }
    setActiveField(null)
  }

  const swap = () => {
    setFromStop(toStop);   setFromText(toText)
    setToStop(fromStop);   setToText(fromText)
    setResult(null)
  }

  const search = async () => {
    if (!fromStop || !toStop) { setError("Pick both stops"); return }
    setError(""); setLoading(true); setResult(null)
    try {
      setResult(await api.getRoute(fromStop.name, toStop.name, "astar"))
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  // Build polyline coords from directions
  const polyline = result?.directions?.reduce((acc, d) => {
    const a = stops.find(s => s.name === d.from)
    const b = stops.find(s => s.name === d.to)
    if (a) acc.push({ latitude: parseFloat(a.lat), longitude: parseFloat(a.lon) })
    if (b) acc.push({ latitude: parseFloat(b.lat), longitude: parseFloat(b.lon) })
    return acc
  }, []) ?? []

  // Dedupe consecutive identical coords
  const dedupedPolyline = polyline.filter((p, i) =>
    i === 0 || p.latitude !== polyline[i-1].latitude || p.longitude !== polyline[i-1].longitude
  )

  // Map region to fit route
  const mapRegion = dedupedPolyline.length > 1 ? {
    latitude:       (dedupedPolyline[0].latitude + dedupedPolyline[dedupedPolyline.length-1].latitude) / 2,
    longitude:      (dedupedPolyline[0].longitude + dedupedPolyline[dedupedPolyline.length-1].longitude) / 2,
    latitudeDelta:  Math.abs(dedupedPolyline[0].latitude - dedupedPolyline[dedupedPolyline.length-1].latitude) + 0.05,
    longitudeDelta: Math.abs(dedupedPolyline[0].longitude - dedupedPolyline[dedupedPolyline.length-1].longitude) + 0.05,
  } : BENGALURU

  return (
    <View style={S.container}>
      {/* Map */}
      <MapView style={S.map} region={mapRegion} userInterfaceStyle="dark">
        {fromStop && (
          <Marker
            coordinate={{ latitude: parseFloat(fromStop.lat), longitude: parseFloat(fromStop.lon) }}
            pinColor={COLORS.brand}
            title={fromStop.name}
          />
        )}
        {toStop && (
          <Marker
            coordinate={{ latitude: parseFloat(toStop.lat), longitude: parseFloat(toStop.lon) }}
            pinColor={COLORS.teal}
            title={toStop.name}
          />
        )}
        {dedupedPolyline.length > 1 && (
          <Polyline
            coordinates={dedupedPolyline}
            strokeColor={COLORS.teal}
            strokeWidth={4}
            lineDashPattern={null}
          />
        )}
      </MapView>

      <ScrollView style={S.scroll} keyboardShouldPersistTaps="handled">
        {/* Search box */}
        <View style={S.searchBox}>
          {/* From */}
          <View style={S.inputRow}>
            <View style={[S.dot, { backgroundColor: COLORS.brand }]} />
            <TextInput
              style={S.input}
              value={fromText}
              onChangeText={t => { setFromText(t); setFromStop(null); setActiveField("from") }}
              onFocus={() => setActiveField("from")}
              placeholder="From stop…"
              placeholderTextColor={COLORS.dim}
            />
            {fromText.length > 0 && (
              <TouchableOpacity onPress={() => { setFromText(""); setFromStop(null) }}>
                <Ionicons name="close-circle" size={16} color={COLORS.dim} />
              </TouchableOpacity>
            )}
          </View>
          {/* To */}
          <View style={S.inputRow}>
            <View style={[S.dot, { backgroundColor: COLORS.teal }]} />
            <TextInput
              style={S.input}
              value={toText}
              onChangeText={t => { setToText(t); setToStop(null); setActiveField("to") }}
              onFocus={() => setActiveField("to")}
              placeholder="To stop…"
              placeholderTextColor={COLORS.dim}
            />
            <TouchableOpacity style={S.swapBtn} onPress={swap}>
              <Ionicons name="swap-vertical" size={18} color={COLORS.sub} />
            </TouchableOpacity>
          </View>
          {/* Search button */}
          <TouchableOpacity style={S.searchBtn} onPress={search} disabled={loading}>
            {loading
              ? <ActivityIndicator color="#fff" size="small" />
              : <>
                  <Ionicons name="navigate" size={16} color="#fff" />
                  <Text style={S.searchText}>Find route</Text>
                </>
            }
          </TouchableOpacity>
        </View>

        {/* Dropdowns */}
        {activeField === "from" && filtered(fromText).length > 0 && (
          <View style={S.dropdown}>
            {filtered(fromText).map(s => (
              <TouchableOpacity key={s.stop_id} style={S.dropItem} onPress={() => pick(s, "from")}>
                <Text style={S.dropText}>{s.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        {activeField === "to" && filtered(toText).length > 0 && (
          <View style={S.dropdown}>
            {filtered(toText).map(s => (
              <TouchableOpacity key={s.stop_id} style={S.dropItem} onPress={() => pick(s, "to")}>
                <Text style={S.dropText}>{s.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Error */}
        {error ? (
          <Text style={{ color: COLORS.red, textAlign: "center", marginTop: 8, fontSize: 13 }}>
            {error}
          </Text>
        ) : null}

        {/* Result */}
        {result && (
          <View style={[S.resultCard, { marginTop: 12, marginBottom: 20 }]}>
            {/* Header */}
            <View style={S.resultHead}>
              <Text style={S.resultTitle} numberOfLines={1}>
                {result.from_stop} → {result.to_stop}
              </Text>
              <Text style={S.resultTime}>{result.total_minutes} min</Text>
            </View>

            {/* Meta */}
            <View style={S.metaRow}>
              <View style={S.metaPill}>
                <Text style={S.metaText}>{result.algorithm}</Text>
              </View>
              <View style={S.metaPill}>
                <Text style={S.metaText}>{result.transfers} transfer{result.transfers !== 1 ? "s" : ""}</Text>
              </View>
              {result.cached && (
                <View style={[S.metaPill, { borderColor: COLORS.teal }]}>
                  <Text style={[S.metaText, { color: COLORS.teal }]}>⚡ cached</Text>
                </View>
              )}
            </View>

            {/* Steps */}
            {result.directions?.map((step, i) => {
              const isWalk    = step.type === "walk"
              const iconName  = isWalk ? "walk" : "bus"
              const iconColor = isWalk ? COLORS.yellow : COLORS.brand
              const iconBg    = isWalk ? "#422006" : "#1e3a5f"
              return (
                <View key={i} style={S.step}>
                  <View style={[S.stepIcon, { backgroundColor: iconBg }]}>
                    <Ionicons name={iconName} size={14} color={iconColor} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={S.stepLabel}>
                      {isWalk ? "Walk" : `Route ${step.route}`}
                    </Text>
                    <Text style={S.stepSub}>
                      {step.from} → {step.to}
                    </Text>
                  </View>
                  <Text style={S.stepTime}>{step.minutes}m</Text>
                </View>
              )
            })}
          </View>
        )}
      </ScrollView>
    </View>
  )
}
