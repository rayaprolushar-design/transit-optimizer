/**
 * app/index.js — Route Planner (Home tab)
 * Search stops, find fastest route, view step-by-step directions.
 * Calls GET /route on your Railway FastAPI backend.
 */
import { useState, useEffect } from "react"
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, ScrollView, ActivityIndicator, Alert,
} from "react-native"
import MapView, { Marker, Polyline } from "react-native-maps"
import { Ionicons } from "@expo/vector-icons"
import { api } from "../api/client"
import { COLORS, BENGALURU } from "../constants/config"

const S = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  map:       { height: 240 },
  body:      { flex: 1, padding: 14 },
  label:     { color: COLORS.sub, fontSize: 11, marginBottom: 4, marginTop: 10,
               textTransform: "uppercase", letterSpacing: 0.5 },
  input:     {
    backgroundColor: COLORS.card, borderWidth: 0.5, borderColor: COLORS.border,
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10,
    color: COLORS.text, fontSize: 14,
  },
  dropdown:  {
    backgroundColor: COLORS.surface, borderWidth: 0.5, borderColor: COLORS.border,
    borderRadius: 10, marginTop: 2, maxHeight: 180,
  },
  dropItem:  { paddingHorizontal: 14, paddingVertical: 10,
               borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  dropText:  { color: COLORS.text, fontSize: 13 },
  dropSub:   { color: COLORS.dim, fontSize: 11, marginTop: 1 },
  btn:       {
    backgroundColor: COLORS.brand, borderRadius: 10, paddingVertical: 12,
    alignItems: "center", marginTop: 14, flexDirection: "row",
    justifyContent: "center", gap: 8,
  },
  btnText:   { color: "#fff", fontWeight: "600", fontSize: 14 },
  card:      { backgroundColor: COLORS.card, borderRadius: 10, padding: 12,
               marginTop: 12, borderWidth: 0.5, borderColor: COLORS.border },
  cardRow:   { flexDirection: "row", justifyContent: "space-between",
               alignItems: "center", marginBottom: 8 },
  cardTitle: { color: COLORS.text, fontWeight: "600", fontSize: 15 },
  cardTime:  { color: COLORS.teal, fontWeight: "700", fontSize: 18 },
  badge:     { flexDirection: "row", gap: 6, flexWrap: "wrap", marginBottom: 10 },
  pill:      { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20,
               borderWidth: 0.5 },
  pillText:  { fontSize: 11, fontWeight: "500" },
  step:      { borderRadius: 8, padding: 10, marginBottom: 6 },
  stepText:  { fontSize: 13 },
  stepTime:  { fontSize: 11, marginTop: 2 },
})

const MODE_ICON = { transit: "bus", walk: "walk" }

export default function RoutePlanner() {
  const [stops,     setStops]     = useState([])
  const [fromQuery, setFromQuery] = useState("")
  const [toQuery,   setToQuery]   = useState("")
  const [fromStop,  setFromStop]  = useState(null)
  const [toStop,    setToStop]    = useState(null)
  const [focusField,setFocusField]= useState(null)  // "from" | "to"
  const [loading,   setLoading]   = useState(false)
  const [result,    setResult]    = useState(null)
  const [algo,      setAlgo]      = useState("astar")

  useEffect(() => {
    api.getStops().then(setStops).catch(() => {})
  }, [])

  const filtered = (query) =>
    stops.filter(s => s.name.toLowerCase().includes(query.toLowerCase())).slice(0, 6)

  const selectStop = (stop, field) => {
    if (field === "from") { setFromStop(stop); setFromQuery(stop.name) }
    else                  { setToStop(stop);   setToQuery(stop.name)   }
    setFocusField(null)
  }

  const search = async () => {
    if (!fromStop || !toStop) { Alert.alert("Select both stops first"); return }
    setLoading(true); setResult(null)
    try {
      const data = await api.getRoute(fromStop.name, toStop.name, algo)
      setResult(data)
    } catch (e) {
      Alert.alert("Error", e.message)
    } finally {
      setLoading(false)
    }
  }

  // Build polyline from route directions + stops
  const routeCoords = result?.directions?.flatMap(d => {
    const a = stops.find(s => s.name === d.from)
    const b = stops.find(s => s.name === d.to)
    return [a,b].filter(Boolean).map(s => ({
      latitude:  parseFloat(s.lat),
      longitude: parseFloat(s.lon),
    }))
  }) ?? []

  return (
    <View style={S.container}>
      {/* Map */}
      <MapView
        style={S.map}
        initialRegion={BENGALURU}
        userInterfaceStyle="dark"
      >
        {stops.map(s => (
          <Marker
            key={s.stop_id}
            coordinate={{ latitude: parseFloat(s.lat), longitude: parseFloat(s.lon) }}
            title={s.name}
            pinColor={
              s.stop_id === fromStop?.stop_id ? COLORS.brand :
              s.stop_id === toStop?.stop_id   ? COLORS.teal  : COLORS.dim
            }
          />
        ))}
        {routeCoords.length > 1 && (
          <Polyline
            coordinates={routeCoords}
            strokeColor={COLORS.teal}
            strokeWidth={3}
          />
        )}
      </MapView>

      <ScrollView style={S.body} keyboardShouldPersistTaps="handled">

        {/* From */}
        <Text style={S.label}>From</Text>
        <TextInput
          style={S.input}
          value={fromQuery}
          onChangeText={t => { setFromQuery(t); setFocusField("from"); setFromStop(null) }}
          onFocus={() => setFocusField("from")}
          placeholder="Search stop..."
          placeholderTextColor={COLORS.dim}
        />
        {focusField === "from" && fromQuery.length > 0 && (
          <View style={S.dropdown}>
            {filtered(fromQuery).map(s => (
              <TouchableOpacity key={s.stop_id} style={S.dropItem} onPress={() => selectStop(s, "from")}>
                <Text style={S.dropText}>{s.name}</Text>
                <Text style={S.dropSub}>{s.stop_id}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* To */}
        <Text style={S.label}>To</Text>
        <TextInput
          style={S.input}
          value={toQuery}
          onChangeText={t => { setToQuery(t); setFocusField("to"); setToStop(null) }}
          onFocus={() => setFocusField("to")}
          placeholder="Search stop..."
          placeholderTextColor={COLORS.dim}
        />
        {focusField === "to" && toQuery.length > 0 && (
          <View style={S.dropdown}>
            {filtered(toQuery).map(s => (
              <TouchableOpacity key={s.stop_id} style={S.dropItem} onPress={() => selectStop(s, "to")}>
                <Text style={S.dropText}>{s.name}</Text>
                <Text style={S.dropSub}>{s.stop_id}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Algorithm toggle */}
        <View style={{ flexDirection:"row", gap:8, marginTop:12 }}>
          {["astar","dijkstra"].map(a => (
            <TouchableOpacity
              key={a}
              onPress={() => setAlgo(a)}
              style={[S.pill, {
                backgroundColor: algo===a ? COLORS.brand+"33" : COLORS.card,
                borderColor:     algo===a ? COLORS.brand       : COLORS.border,
              }]}
            >
              <Text style={[S.pillText, { color: algo===a ? COLORS.brand : COLORS.sub }]}>
                {a === "astar" ? "A* (faster)" : "Dijkstra"}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Search button */}
        <TouchableOpacity style={S.btn} onPress={search} disabled={loading}>
          {loading
            ? <ActivityIndicator color="#fff" />
            : <><Ionicons name="navigate" size={16} color="#fff" />
               <Text style={S.btnText}>Find fastest route</Text></>
          }
        </TouchableOpacity>

        {/* Result */}
        {result && (
          <View style={S.card}>
            <View style={S.cardRow}>
              <Text style={S.cardTitle} numberOfLines={1}>
                {result.from_stop} → {result.to_stop}
              </Text>
              <Text style={S.cardTime}>{result.total_minutes} min</Text>
            </View>

            <View style={S.badge}>
              <View style={[S.pill, { backgroundColor:"#1e3a5f", borderColor:COLORS.brand }]}>
                <Text style={[S.pillText, { color:COLORS.brand }]}>{result.algorithm}</Text>
              </View>
              <View style={[S.pill, { backgroundColor:COLORS.card, borderColor:COLORS.border }]}>
                <Text style={[S.pillText, { color:COLORS.sub }]}>
                  {result.nodes_visited} nodes · {result.elapsed_ms}ms
                </Text>
              </View>
              {result.cached && (
                <View style={[S.pill, { backgroundColor:"#052e16", borderColor:COLORS.teal }]}>
                  <Text style={[S.pillText, { color:COLORS.teal }]}>⚡ cached</Text>
                </View>
              )}
            </View>

            {result.directions?.map((step, i) => (
              <View key={i} style={[S.step, {
                backgroundColor: step.type === "walk" ? "#422006" : "#1e3a5f",
              }]}>
                <Text style={[S.stepText, {
                  color: step.type === "walk" ? COLORS.yellow : COLORS.brand,
                }]}>
                  {step.type === "walk" ? "🚶 Walk" : `🚌 Route ${step.route}`}
                  {"  "}{step.from} → {step.to}
                </Text>
                <Text style={[S.stepTime, { color: COLORS.sub }]}>
                  {step.minutes} min
                  {step.dist_km ? `  ·  ${Math.round(step.dist_km*1000)}m` : ""}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  )
}
