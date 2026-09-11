/**
 * app/live.js — Live Feed (fixed)
 * - Caps delay at 60 minutes max
 * - Shows "45 min" or "1h 5m" format only
 * - Filters out unrealistic values (> 60 min shown as capped)
 * - Track route for push notifications
 */
import { useState, useEffect } from "react"
import {
  View, Text, StyleSheet, FlatList,
  TouchableOpacity, Switch,
} from "react-native"
import { Ionicons } from "@expo/vector-icons"
import { useWebSocket } from "../hooks/useWebSocket"
import { useNotifications } from "../hooks/useNotifications"
import { COLORS } from "../constants/config"

const MAX_DELAY = 60   // cap at 60 minutes — anything above is a data error

function formatDelay(raw) {
  const min = Math.min(Math.abs(raw ?? 0), MAX_DELAY)
  if (min < 1)  return "On time"
  if (min < 60) return `${Math.round(min)} min`
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function delayColor(raw) {
  const min = Math.min(Math.abs(raw ?? 0), MAX_DELAY)
  if (min > 10) return COLORS.red
  if (min > 3)  return COLORS.yellow
  return COLORS.teal
}

const S = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header:    { flexDirection:"row", alignItems:"center",
               justifyContent:"space-between", padding:14,
               borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  hTitle:    { color:COLORS.text, fontWeight:"600", fontSize:15 },
  wsBadge:   { flexDirection:"row", alignItems:"center", gap:5 },
  wsDot:     { width:8, height:8, borderRadius:4 },
  wsText:    { fontSize:12, fontWeight:"500" },
  notifBar:  { flexDirection:"row", alignItems:"center",
               justifyContent:"space-between",
               padding:12, paddingHorizontal:14,
               backgroundColor:COLORS.surface,
               borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  notifText: { color:COLORS.sub, fontSize:12 },
  empty:     { flex:1, alignItems:"center", justifyContent:"center", gap:10 },
  emptyText: { color:COLORS.dim, fontSize:14 },
  emptySub:  { color:COLORS.dim, fontSize:12 },
  item:      { flexDirection:"row", alignItems:"center", gap:12,
               paddingHorizontal:14, paddingVertical:12,
               borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  itemLeft:  { width:8, alignItems:"center" },
  itemDot:   { width:8, height:8, borderRadius:4 },
  itemBody:  { flex:1 },
  itemRoute: { color:COLORS.text, fontWeight:"600", fontSize:14 },
  itemStop:  { color:COLORS.sub, fontSize:12, marginTop:1 },
  itemRight: { alignItems:"flex-end", gap:3 },
  itemDelay: { fontWeight:"700", fontSize:15, fontVariant:["tabular-nums"] },
  itemTime:  { color:COLORS.dim, fontSize:11 },
  trackPill: { paddingHorizontal:8, paddingVertical:2,
               borderRadius:20, borderWidth:0.5, marginTop:3 },
  trackText: { fontSize:11, fontWeight:"500" },
})

export default function LiveFeed() {
  const { events, connected }            = useWebSocket()
  const { permissionGranted, notifyDelay } = useNotifications()
  const [notifOn,  setNotifOn]  = useState(true)
  const [tracked,  setTracked]  = useState(new Set())

  // Fire notification for tracked routes with real delay
  useEffect(() => {
    if (!notifOn || !permissionGranted || events.length === 0) return
    const ev = events[0]
    const delay = Math.min(Math.abs(ev.delay_minutes ?? 0), MAX_DELAY)
    if (tracked.has(ev.route) && delay > 3) {
      notifyDelay(ev.route, ev.stop, Math.round(delay))
    }
  }, [events])

  const toggleTrack = (route) => {
    setTracked(prev => {
      const next = new Set(prev)
      next.has(route) ? next.delete(route) : next.add(route)
      return next
    })
  }

  const renderItem = ({ item: ev }) => {
    // Filter out unrealistic delays silently — just cap and show
    const delay     = Math.min(Math.abs(ev.delay_minutes ?? 0), MAX_DELAY)
    const isTracked = tracked.has(ev.route)
    const color     = delayColor(delay)

    return (
      <View style={S.item}>
        <View style={S.itemLeft}>
          <View style={[S.itemDot, { backgroundColor: color }]} />
        </View>
        <View style={S.itemBody}>
          <Text style={S.itemRoute}>{ev.route ?? "Unknown"}</Text>
          <Text style={S.itemStop}>{ev.stop ?? ev.stop_name ?? "—"}</Text>
          <TouchableOpacity
            style={[S.trackPill, {
              backgroundColor: isTracked ? COLORS.brand+"22" : COLORS.card,
              borderColor:     isTracked ? COLORS.brand       : COLORS.border,
            }]}
            onPress={() => toggleTrack(ev.route)}
          >
            <Text style={[S.trackText, { color: isTracked ? COLORS.brand : COLORS.sub }]}>
              {isTracked ? "🔔 Tracking" : "Track"}
            </Text>
          </TouchableOpacity>
        </View>
        <View style={S.itemRight}>
          <Text style={[S.itemDelay, { color }]}>
            {delay > 0 ? `+${formatDelay(delay)}` : "On time"}
          </Text>
          <Text style={S.itemTime}>
            {ev.time ?? new Date().toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit" })}
          </Text>
        </View>
      </View>
    )
  }

  return (
    <View style={S.container}>
      {/* Header */}
      <View style={S.header}>
        <Text style={S.hTitle}>Live Delays</Text>
        <View style={S.wsBadge}>
          <View style={[S.wsDot, {
            backgroundColor: connected ? COLORS.teal : COLORS.dim,
          }]} />
          <Text style={[S.wsText, { color: connected ? COLORS.teal : COLORS.dim }]}>
            {connected ? "Live" : "Connecting…"}
          </Text>
        </View>
      </View>

      {/* Notification toggle */}
      <View style={S.notifBar}>
        <Text style={S.notifText}>Alert me when tracked route is delayed</Text>
        <Switch
          value={notifOn}
          onValueChange={setNotifOn}
          trackColor={{ false:COLORS.border, true:COLORS.brand }}
          thumbColor="#fff"
        />
      </View>

      {/* Events */}
      {events.length === 0 ? (
        <View style={S.empty}>
          <Ionicons name="radio-outline" size={48} color={COLORS.dim} />
          <Text style={S.emptyText}>
            {connected ? "Waiting for events…" : "Server not connected"}
          </Text>
          <Text style={S.emptySub}>Events arrive every 5 seconds</Text>
        </View>
      ) : (
        <FlatList
          data={events}
          keyExtractor={ev => String(ev.id ?? Math.random())}
          renderItem={renderItem}
        />
      )}
    </View>
  )
}
