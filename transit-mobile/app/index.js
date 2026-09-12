/**
 * app/index.js — Route Planner (fixed)
 * Key fixes:
 *  - fromStop/toStop stored as {stop_id, name, lat, lon}
 *  - Route search uses stop NAME (server does fuzzy match)
 *  - Map polyline built from stop coords in path
 *  - Clear validation before searching
 */
import { useState, useEffect, useRef } from "react"
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, ScrollView, ActivityIndicator,
  Keyboard,
} from "react-native"
import MapView, { Marker, Polyline } from "react-native-maps"
import { Ionicons } from "@expo/vector-icons"
import { api } from "../api/client"
import { COLORS, BENGALURU } from "../constants/config"

const S = StyleSheet.create({
  container:  { flex:1, backgroundColor:COLORS.bg },
  map:        { height:220 },
  searchWrap: { backgroundColor:COLORS.card, margin:12, borderRadius:14,
                borderWidth:0.5, borderColor:COLORS.border, overflow:"hidden" },
  row:        { flexDirection:"row", alignItems:"center",
                paddingHorizontal:12, paddingVertical:11,
                borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  dot:        { width:10, height:10, borderRadius:5, marginRight:10, flexShrink:0 },
  input:      { flex:1, color:COLORS.text, fontSize:14 },
  clearBtn:   { padding:4 },
  swapBtn:    { padding:8 },
  findBtn:    { flexDirection:"row", alignItems:"center", justifyContent:"center",
                gap:8, padding:13, backgroundColor:COLORS.brand },
  findText:   { color:"#fff", fontWeight:"700", fontSize:14 },
  drop:       { backgroundColor:COLORS.surface, borderWidth:0.5,
                borderColor:COLORS.border, borderRadius:10,
                marginHorizontal:12, marginTop:-6, maxHeight:180, zIndex:99 },
  dropItem:   { padding:13, borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  dropText:   { color:COLORS.text, fontSize:13 },
  errText:    { color:COLORS.red, textAlign:"center", marginTop:6, fontSize:13 },
  resultWrap: { marginHorizontal:12, marginTop:12, marginBottom:24,
                backgroundColor:COLORS.card, borderRadius:14,
                borderWidth:0.5, borderColor:COLORS.border, overflow:"hidden" },
  rHead:      { flexDirection:"row", justifyContent:"space-between",
                alignItems:"center", padding:14 },
  rTitle:     { color:COLORS.text, fontWeight:"700", fontSize:14, flex:1 },
  rTime:      { color:COLORS.teal, fontWeight:"800", fontSize:22 },
  rMeta:      { flexDirection:"row", gap:6, paddingHorizontal:14, paddingBottom:10 },
  rPill:      { paddingHorizontal:8, paddingVertical:3, borderRadius:20,
                backgroundColor:COLORS.surface, borderWidth:0.5,
                borderColor:COLORS.border },
  rPillText:  { color:COLORS.sub, fontSize:11 },
  step:       { flexDirection:"row", alignItems:"center", gap:10,
                padding:12, borderTopWidth:0.5, borderTopColor:COLORS.border },
  stepIcon:   { width:28, height:28, borderRadius:14, alignItems:"center",
                justifyContent:"center", flexShrink:0 },
  stepBody:   { flex:1 },
  stepLabel:  { color:COLORS.text, fontSize:13, fontWeight:"500" },
  stepSub:    { color:COLORS.sub, fontSize:11, marginTop:1 },
  stepTime:   { color:COLORS.sub, fontSize:12, fontVariant:["tabular-nums"] },
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
    api.getStops()
      .then(data => {
        // Handle both array and dict response formats
        if (Array.isArray(data)) setStops(data)
        else if (typeof data === "object") {
          setStops(Object.entries(data).map(([id, s]) => ({
            stop_id: id, name: s.name,
            lat: String(s.lat), lon: String(s.lon),
          })))
        }
      })
      .catch(() => {})
  }, [])

  const filtered = (q) => {
    if (!q || q.length < 1) return []
    return stops
      .filter(s => s.name.toLowerCase().includes(q.toLowerCase()))
      .slice(0, 7)
  }

  const pick = (stop, field) => {
    if (field === "from") {
      setFromStop({ ...stop })
      setFromText(stop.name)
    } else {
      setToStop({ ...stop })
      setToText(stop.name)
    }
    setActiveField(null)
    setError("")
    Keyboard.dismiss()
  }

  const swap = () => {
    const tmpStop = fromStop, tmpText = fromText
    setFromStop(toStop);   setFromText(toText)
    setToStop(tmpStop);    setToText(tmpText)
    setResult(null)
  }

  const search = async () => {
    if (!fromStop) { setError("Select a 'From' stop from the dropdown"); return }
    if (!toStop)   { setError("Select a 'To' stop from the dropdown"); return }
    if (fromStop.stop_id === toStop.stop_id) { setError("Pick two different stops"); return }

    setError(""); setLoading(true); setResult(null)
    Keyboard.dismiss()
    try {
      // Server uses stop NAME with fuzzy matching
      const data = await api.getRoute(fromStop.name, toStop.name, "astar")
      setResult(data)
    } catch (e) {
      setError(e.message ?? "No route found between these stops")
    } finally {
      setLoading(false)
    }
  }

  // Build polyline from result path using stop coords
  const polyline = (() => {
    if (!result?.path) return []
    return result.path
      .map(stopId => stops.find(s => s.stop_id === stopId))
      .filter(Boolean)
      .map(s => ({ latitude: parseFloat(s.lat), longitude: parseFloat(s.lon) }))
  })()

  // Auto-fit map to show both stops
  const mapRegion = (() => {
    const pts = [fromStop, toStop].filter(Boolean)
    if (pts.length < 2) return BENGALURU
    const lats = pts.map(p => parseFloat(p.lat))
    const lons = pts.map(p => parseFloat(p.lon))
    const minLat = Math.min(...lats), maxLat = Math.max(...lats)
    const minLon = Math.min(...lons), maxLon = Math.max(...lons)
    return {
      latitude:       (minLat + maxLat) / 2,
      longitude:      (minLon + maxLon) / 2,
      latitudeDelta:  Math.max(maxLat - minLat, 0.04) * 1.4,
      longitudeDelta: Math.max(maxLon - minLon, 0.04) * 1.4,
    }
  })()

  return (
    <View style={S.container}>
      <MapView style={S.map} region={mapRegion} userInterfaceStyle="dark">
        {fromStop && (
          <Marker
            coordinate={{ latitude:parseFloat(fromStop.lat), longitude:parseFloat(fromStop.lon) }}
            pinColor={COLORS.brand}
            title={fromStop.name}
          />
        )}
        {toStop && (
          <Marker
            coordinate={{ latitude:parseFloat(toStop.lat), longitude:parseFloat(toStop.lon) }}
            pinColor={COLORS.teal}
            title={toStop.name}
          />
        )}
        {polyline.length > 1 && (
          <Polyline
            coordinates={polyline}
            strokeColor={COLORS.teal}
            strokeWidth={4}
          />
        )}
      </MapView>

      <ScrollView keyboardShouldPersistTaps="always">
        {/* Search box */}
        <View style={S.searchWrap}>
          {/* From */}
          <View style={S.row}>
            <View style={[S.dot, { backgroundColor: COLORS.brand }]} />
            <TextInput
              style={S.input}
              value={fromText}
              onChangeText={t => {
                setFromText(t)
                setFromStop(null)
                setActiveField("from")
                setResult(null)
              }}
              onFocus={() => setActiveField("from")}
              placeholder="From — type stop name"
              placeholderTextColor={COLORS.dim}
            />
            {fromText.length > 0 && (
              <TouchableOpacity style={S.clearBtn}
                onPress={() => { setFromText(""); setFromStop(null); setActiveField("from") }}>
                <Ionicons name="close-circle" size={16} color={COLORS.dim} />
              </TouchableOpacity>
            )}
          </View>
          {/* To */}
          <View style={S.row}>
            <View style={[S.dot, { backgroundColor: COLORS.teal }]} />
            <TextInput
              style={S.input}
              value={toText}
              onChangeText={t => {
                setToText(t)
                setToStop(null)
                setActiveField("to")
                setResult(null)
              }}
              onFocus={() => setActiveField("to")}
              placeholder="To — type stop name"
              placeholderTextColor={COLORS.dim}
            />
            <TouchableOpacity style={S.swapBtn} onPress={swap}>
              <Ionicons name="swap-vertical" size={18} color={COLORS.sub} />
            </TouchableOpacity>
          </View>
          {/* Find button */}
          <TouchableOpacity style={S.findBtn} onPress={search} disabled={loading}>
            {loading
              ? <ActivityIndicator color="#fff" size="small" />
              : <>
                  <Ionicons name="navigate" size={16} color="#fff" />
                  <Text style={S.findText}>Find route</Text>
                </>
            }
          </TouchableOpacity>
        </View>

        {/* From dropdown */}
        {activeField === "from" && filtered(fromText).length > 0 && (
          <View style={S.drop}>
            {filtered(fromText).map(s => (
              <TouchableOpacity key={s.stop_id} style={S.dropItem}
                onPress={() => pick(s, "from")}>
                <Text style={S.dropText}>{s.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* To dropdown */}
        {activeField === "to" && filtered(toText).length > 0 && (
          <View style={S.drop}>
            {filtered(toText).map(s => (
              <TouchableOpacity key={s.stop_id} style={S.dropItem}
                onPress={() => pick(s, "to")}>
                <Text style={S.dropText}>{s.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Error */}
        {error ? <Text style={S.errText}>{error}</Text> : null}

        {/* Result card */}
        {result && (
          <View style={S.resultWrap}>
            <View style={S.rHead}>
              <Text style={S.rTitle} numberOfLines={1}>
                {result.from_stop} → {result.to_stop}
              </Text>
              <Text style={S.rTime}>{result.total_minutes} min</Text>
            </View>
            <View style={S.rMeta}>
              <View style={S.rPill}>
                <Text style={S.rPillText}>{result.algorithm?.toUpperCase()}</Text>
              </View>
              <View style={S.rPill}>
                <Text style={S.rPillText}>
                  {result.transfers} transfer{result.transfers !== 1 ? "s":""}</Text>
              </View>
              {result.cached && (
                <View style={[S.rPill, { borderColor:COLORS.teal }]}>
                  <Text style={[S.rPillText, { color:COLORS.teal }]}>⚡ cached</Text>
                </View>
              )}
            </View>

            {result.directions?.map((step, i) => {
              const isWalk = step.type === "walk" || step.route === "WALK"
              return (
                <View key={i} style={S.step}>
                  <View style={[S.stepIcon, {
                    backgroundColor: isWalk ? "#422006" : "#1e3a5f",
                  }]}>
                    <Ionicons
                      name={isWalk ? "walk" : "bus"}
                      size={14}
                      color={isWalk ? COLORS.yellow : COLORS.brand}
                    />
                  </View>
                  <View style={S.stepBody}>
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
