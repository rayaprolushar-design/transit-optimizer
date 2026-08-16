/**
 * app/board.js — Display Board tab
 * Shows next arrivals at a selected stop.
 * Polls GET /board/{stop_id} every 30 seconds.
 * Same data as the Raspberry Pi display board — on your phone.
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
  container:  { flex: 1, backgroundColor: COLORS.bg },
  stopBar:    { flexDirection:"row", flexWrap:"wrap", gap:6, padding:12,
                borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  stopChip:   { paddingHorizontal:10, paddingVertical:5, borderRadius:20,
                borderWidth:0.5 },
  stopText:   { fontSize:12, fontWeight:"500" },
  body:       { flex:1 },
  heroCard:   { margin:14, backgroundColor:COLORS.card, borderRadius:14,
                padding:16, borderWidth:0.5, borderColor:COLORS.border },
  heroName:   { color:COLORS.text, fontSize:20, fontWeight:"700", marginBottom:4 },
  heroRow:    { flexDirection:"row", alignItems:"center", gap:8 },
  heroDelay:  { fontSize:13, fontWeight:"600" },
  heroDot:    { width:8, height:8, borderRadius:4 },
  sectionTitle:{ color:COLORS.sub, fontSize:11, fontWeight:"500",
                 textTransform:"uppercase", letterSpacing:0.5,
                 marginHorizontal:14, marginBottom:8 },
  arrivalCard:{ marginHorizontal:14, marginBottom:8, backgroundColor:COLORS.card,
                borderRadius:12, padding:12, borderWidth:0.5,
                borderColor:COLORS.border },
  arrRow:     { flexDirection:"row", alignItems:"center", justifyContent:"space-between" },
  routeBadge: { backgroundColor:COLORS.brand+"22", paddingHorizontal:10,
                paddingVertical:4, borderRadius:8, borderWidth:0.5,
                borderColor:COLORS.brand },
  routeText:  { color:COLORS.brand, fontWeight:"700", fontSize:14 },
  destText:   { color:COLORS.text, fontSize:14, flex:1, marginLeft:10 },
  timeBlock:  { alignItems:"flex-end" },
  predTime:   { fontSize:15, fontWeight:"600", fontVariant:["tabular-nums"] },
  schedTime:  { fontSize:11, color:COLORS.dim, marginTop:2, fontVariant:["tabular-nums"] },
  statusPill: { marginTop:6, alignSelf:"flex-start", paddingHorizontal:8,
                paddingVertical:2, borderRadius:20, borderWidth:0.5 },
  statusText: { fontSize:11, fontWeight:"500" },
  confDot:    { width:7, height:7, borderRadius:3.5, position:"absolute",
                top:6, right:6 },
  empty:      { alignItems:"center", padding:40 },
  emptyText:  { color:COLORS.dim, fontSize:14, marginTop:8 },
  ticker:     { padding:10, borderTopWidth:0.5, borderTopColor:COLORS.border,
                flexDirection:"row", justifyContent:"space-between" },
  tickerText: { color:COLORS.dim, fontSize:11 },
})

const QUICK_STOPS = [
  { stop_id:"S001", name:"MG Road" },
  { stop_id:"S004", name:"Indiranagar" },
  { stop_id:"S006", name:"Koramangala" },
  { stop_id:"S007", name:"BTM Layout" },
  { stop_id:"S017", name:"HSR Layout" },
  { stop_id:"S020", name:"Silk Board" },
]

const statusStyle = (delay) => {
  if (delay > 3) return { bg:"#450a0a", border:COLORS.red,    text:COLORS.red }
  if (delay > 1) return { bg:"#422006", border:COLORS.yellow, text:COLORS.yellow }
  return              { bg:"#052e16", border:COLORS.teal,   text:COLORS.teal }
}

const confColor = (conf) =>
  conf === "high" ? COLORS.teal : conf === "medium" ? COLORS.yellow : COLORS.red

export default function BoardScreen() {
  const [selectedStop, setSelectedStop] = useState(QUICK_STOPS[0])
  const [board,        setBoard]        = useState(null)
  const [loading,      setLoading]      = useState(false)
  const [refreshing,   setRefreshing]   = useState(false)
  const [lastUpdated,  setLastUpdated]  = useState(null)

  const fetchBoard = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else           setLoading(true)
    try {
      const data = await api.boardData(selectedStop.stop_id)
      setBoard(data)
      setLastUpdated(new Date().toLocaleTimeString("en-IN"))
    } catch (_) {}
    finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [selectedStop])

  // Fetch on mount and every 30s
  useEffect(() => {
    fetchBoard()
    const interval = setInterval(() => fetchBoard(), 30000)
    return () => clearInterval(interval)
  }, [fetchBoard])

  const liveDelay = board?.live_delay ?? 0
  const delayColor = liveDelay > 3 ? COLORS.red :
                     liveDelay > 1 ? COLORS.yellow : COLORS.teal

  return (
    <View style={S.container}>

      {/* Quick stop selector */}
      <ScrollView
        horizontal showsHorizontalScrollIndicator={false}
        style={S.stopBar}
        contentContainerStyle={{ gap: 6, paddingRight: 14 }}
      >
        {QUICK_STOPS.map(s => {
          const active = s.stop_id === selectedStop.stop_id
          return (
            <TouchableOpacity
              key={s.stop_id}
              style={[S.stopChip, {
                backgroundColor: active ? COLORS.brand+"22" : COLORS.card,
                borderColor:     active ? COLORS.brand       : COLORS.border,
              }]}
              onPress={() => setSelectedStop(s)}
            >
              <Text style={[S.stopText, { color: active ? COLORS.brand : COLORS.sub }]}>
                {s.name}
              </Text>
            </TouchableOpacity>
          )
        })}
      </ScrollView>

      {loading && !board ? (
        <View style={{ flex:1, alignItems:"center", justifyContent:"center" }}>
          <ActivityIndicator color={COLORS.brand} size="large" />
        </View>
      ) : (
        <ScrollView
          style={S.body}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchBoard(true)}
              tintColor={COLORS.brand}
            />
          }
        >
          {/* Hero card */}
          {board && (
            <View style={S.heroCard}>
              <Text style={S.heroName}>{board.stop_name}</Text>
              <View style={S.heroRow}>
                <View style={[S.heroDot, { backgroundColor: delayColor }]} />
                <Text style={[S.heroDelay, { color: delayColor }]}>
                  {liveDelay > 0
                    ? `Live GPS delay: +${liveDelay.toFixed(1)} min`
                    : "Running on schedule"}
                </Text>
              </View>
              <Text style={{ color:COLORS.dim, fontSize:11, marginTop:6 }}>
                {board.has_gps ? "● Live GPS" : "◌ Simulated"} · {board.arrivals?.length ?? 0} arrivals
              </Text>
            </View>
          )}

          {/* Arrivals */}
          <Text style={S.sectionTitle}>Next arrivals</Text>

          {board?.arrivals?.length === 0 && (
            <View style={S.empty}>
              <Ionicons name="bus-outline" size={40} color={COLORS.dim} />
              <Text style={S.emptyText}>No upcoming arrivals</Text>
            </View>
          )}

          {board?.arrivals?.map((arr, i) => {
            const delay = arr.delay_minutes ?? 0
            const st    = statusStyle(delay)
            return (
              <View key={i} style={S.arrivalCard}>
                <View style={S.arrRow}>
                  <View style={S.routeBadge}>
                    <Text style={S.routeText}>{arr.route}</Text>
                  </View>
                  <Text style={S.destText} numberOfLines={1}>
                    {arr.destination}
                  </Text>
                  <View style={S.timeBlock}>
                    <Text style={[S.predTime, { color:
                      delay > 3 ? COLORS.red :
                      delay > 1 ? COLORS.yellow : COLORS.text }]}>
                      {arr.predicted_time}
                    </Text>
                    <Text style={S.schedTime}>Sched: {arr.scheduled_time}</Text>
                  </View>
                </View>

                <View style={{ flexDirection:"row", alignItems:"center", gap:8, marginTop:8 }}>
                  <View style={[S.statusPill, { backgroundColor:st.bg, borderColor:st.border }]}>
                    <Text style={[S.statusText, { color:st.text }]}>{arr.status}</Text>
                  </View>
                  <View style={[S.statusPill, {
                    backgroundColor: COLORS.card, borderColor: COLORS.border,
                  }]}>
                    <Text style={[S.statusText, { color: confColor(arr.confidence) }]}>
                      {arr.confidence} conf
                    </Text>
                  </View>
                </View>
              </View>
            )
          })}

          <View style={{ height: 20 }} />
        </ScrollView>
      )}

      {/* Footer ticker */}
      <View style={S.ticker}>
        <Text style={S.tickerText}>
          Auto-refresh every 30s · Pull to refresh
        </Text>
        {lastUpdated && (
          <Text style={S.tickerText}>Updated: {lastUpdated}</Text>
        )}
      </View>
    </View>
  )
}
