/**
 * app/live.js — Live Feed tab
 * WebSocket connection to FastAPI /ws/live-feed.
 * Sends push notification when delay > 3 min on tracked routes.
 */
import { useState, useEffect } from "react"
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  Switch, Alert,
} from "react-native"
import { Ionicons } from "@expo/vector-icons"
import { useWebSocket } from "../hooks/useWebSocket"
import { useNotifications } from "../hooks/useNotifications"
import { COLORS } from "../constants/config"

const S = StyleSheet.create({
  container:  { flex: 1, backgroundColor: COLORS.bg },
  header:     { flexDirection:"row", alignItems:"center", justifyContent:"space-between",
                padding:14, borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  headerTitle:{ color:COLORS.text, fontWeight:"600", fontSize:15 },
  wsStatus:   { flexDirection:"row", alignItems:"center", gap:6 },
  wsDot:      { width:8, height:8, borderRadius:4 },
  wsText:     { fontSize:12, fontWeight:"500" },
  notifRow:   { flexDirection:"row", alignItems:"center", justifyContent:"space-between",
                paddingHorizontal:14, paddingVertical:10,
                borderBottomWidth:0.5, borderBottomColor:COLORS.border,
                backgroundColor:COLORS.surface },
  notifText:  { color:COLORS.sub, fontSize:12 },
  empty:      { flex:1, alignItems:"center", justifyContent:"center" },
  emptyIcon:  { opacity:0.3 },
  emptyText:  { color:COLORS.dim, fontSize:14, marginTop:10 },
  emptySmall: { color:COLORS.dim, fontSize:12, marginTop:4 },
  item:       { flexDirection:"row", alignItems:"flex-start", gap:12,
                padding:14, borderBottomWidth:0.5, borderBottomColor:COLORS.border },
  dot:        { width:8, height:8, borderRadius:4, marginTop:5, flexShrink:0 },
  itemBody:   { flex:1 },
  itemRoute:  { color:COLORS.text, fontWeight:"600", fontSize:14 },
  itemStop:   { color:COLORS.sub, fontSize:12, marginTop:1 },
  itemRight:  { alignItems:"flex-end" },
  itemDelay:  { fontWeight:"600", fontSize:14, fontVariant:["tabular-nums"] },
  itemTime:   { color:COLORS.dim, fontSize:11, marginTop:2 },
  trackBtn:   { paddingHorizontal:8, paddingVertical:3, borderRadius:20,
                borderWidth:0.5, marginTop:4 },
  trackText:  { fontSize:11, fontWeight:"500" },
})

const delayColor = (d) =>
  d > 3 ? COLORS.red : d > 1 ? COLORS.yellow : COLORS.teal

export default function LiveFeed() {
  const { events, connected } = useWebSocket()
  const { permissionGranted, notifyDelay } = useNotifications()
  const [notifEnabled,  setNotifEnabled]  = useState(true)
  const [trackedRoutes, setTrackedRoutes] = useState(new Set())

  // Fire push notification for tracked routes with high delay
  useEffect(() => {
    if (!notifEnabled || !permissionGranted) return
    events.slice(0, 1).forEach(ev => {
      if (trackedRoutes.has(ev.route) && (ev.delay_minutes ?? 0) > 3) {
        notifyDelay(ev.route, ev.stop, ev.delay_minutes)
      }
    })
  }, [events])

  const toggleTrack = (route) => {
    setTrackedRoutes(prev => {
      const next = new Set(prev)
      if (next.has(route)) next.delete(route)
      else {
        next.add(route)
        Alert.alert(
          "Tracking " + route,
          "You'll get a push notification if this route is delayed more than 3 min.",
          [{ text: "OK" }]
        )
      }
      return next
    })
  }

  const renderItem = ({ item: ev }) => {
    const delay    = ev.delay_minutes ?? 0
    const isTracked = trackedRoutes.has(ev.route)
    return (
      <View style={S.item}>
        <View style={[S.dot, { backgroundColor: delayColor(delay) }]} />
        <View style={S.itemBody}>
          <Text style={S.itemRoute}>{ev.route}</Text>
          <Text style={S.itemStop}>{ev.stop}</Text>
          <TouchableOpacity
            style={[S.trackBtn, {
              backgroundColor: isTracked ? COLORS.brand+"22" : COLORS.surface,
              borderColor:     isTracked ? COLORS.brand       : COLORS.border,
            }]}
            onPress={() => toggleTrack(ev.route)}
          >
            <Text style={[S.trackText, { color: isTracked ? COLORS.brand : COLORS.sub }]}>
              {isTracked ? "🔔 Tracking" : "Track route"}
            </Text>
          </TouchableOpacity>
        </View>
        <View style={S.itemRight}>
          <Text style={[S.itemDelay, { color: delayColor(delay) }]}>
            {delay > 0 ? `+${delay}m` : "On time"}
          </Text>
          <Text style={S.itemTime}>{ev.time ?? "--:--"}</Text>
        </View>
      </View>
    )
  }

  return (
    <View style={S.container}>

      {/* Header */}
      <View style={S.header}>
        <Text style={S.headerTitle}>Live Delay Feed</Text>
        <View style={S.wsStatus}>
          <View style={[S.wsDot, {
            backgroundColor: connected ? COLORS.teal : COLORS.dim,
            opacity: connected ? 1 : 0.5,
          }]} />
          <Text style={[S.wsText, { color: connected ? COLORS.teal : COLORS.dim }]}>
            {connected ? "Live" : "Connecting…"}
          </Text>
        </View>
      </View>

      {/* Notification toggle */}
      <View style={S.notifRow}>
        <Text style={S.notifText}>
          Push alerts for tracked routes (delay > 3 min)
        </Text>
        <Switch
          value={notifEnabled}
          onValueChange={setNotifEnabled}
          trackColor={{ false: COLORS.border, true: COLORS.brand }}
          thumbColor="#fff"
        />
      </View>

      {/* Events list */}
      {events.length === 0 ? (
        <View style={S.empty}>
          <Ionicons name="radio-outline" size={48} color={COLORS.dim} style={S.emptyIcon} />
          <Text style={S.emptyText}>
            {connected ? "Waiting for events…" : "Not connected"}
          </Text>
          <Text style={S.emptySmall}>
            {connected
              ? "Events arrive every 5 seconds"
              : "Start the FastAPI server to see live data"}
          </Text>
        </View>
      ) : (
        <FlatList
          data={events}
          keyExtractor={ev => String(ev.id)}
          renderItem={renderItem}
        />
      )}
    </View>
  )
}
