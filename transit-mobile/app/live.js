import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, FlatList, TouchableOpacity, Switch, Vibration } from 'react-native';
import * as Notifications from 'expo-notifications';
import { Ionicons } from '@expo/vector-icons';
import { WS_URL, COLORS } from '../constants/config';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

const S = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  controlHeader: { padding: 14, backgroundColor: COLORS.card, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  statusRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  statusText: { marginLeft: 8, fontWeight: '700', fontSize: 13 },
  trackRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: COLORS.surface, borderRadius: 10, padding: 12,
    borderWidth: 0.5, borderColor: COLORS.border,
  },
  trackInfo: { flex: 1 },
  trackTitle: { color: COLORS.text, fontSize: 13, fontWeight: '700', marginLeft: 4 },
  trackDesc: { color: COLORS.dim, fontSize: 11, marginTop: 2 },
  listContainer: { flex: 1, padding: 14 },
  listHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  listTitle: { color: COLORS.text, fontSize: 15, fontWeight: '700' },
  mockButton: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: 6, backgroundColor: COLORS.brand + '1A', borderWidth: 0.5, borderColor: COLORS.brand + '20',
  },
  mockButtonText: { color: COLORS.brand, fontSize: 12, fontWeight: '600' },
  emptyContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', marginTop: 40 },
  emptyText: { color: COLORS.dim, fontSize: 13 },
  logCard: {
    backgroundColor: COLORS.card, borderRadius: 10, padding: 12,
    borderWidth: 0.5, borderColor: COLORS.border, marginBottom: 8,
  },
  logTopRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  logStopName: { color: COLORS.text, fontSize: 13, fontWeight: '700' },
  logTime: { color: COLORS.dim, fontSize: 11 },
  logBottomRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  logDelayText: { color: COLORS.sub, fontSize: 12 },
  alertBadge: {
    backgroundColor: '#EF444420', borderRadius: 4, paddingHorizontal: 6,
    paddingVertical: 2, borderWidth: 0.5, borderColor: '#EF444440',
  },
  alertBadgeText: { color: '#EF4444', fontSize: 10, fontWeight: '700' },
});

export default function LiveFeed() {
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTrackEnabled, setIsTrackEnabled] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    Notifications.requestPermissionsAsync().catch(() => {});
    connectWebSocket();
    return () => {
      if (socketRef.current) socketRef.current.close();
    };
  }, []);

  const connectWebSocket = () => {
    if (socketRef.current) socketRef.current.close();
    const ws = new WebSocket(WS_URL);
    socketRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const newLog = {
          id: Math.random().toString(),
          timestamp: new Date().toLocaleTimeString(),
          stop_name: data.stop_name || 'MG Road',
          predicted_delay: data.predicted_delay !== undefined ? data.predicted_delay : (Math.random() * 8),
          actual_delay: data.actual_delay !== undefined ? data.actual_delay : (Math.random() * 8),
          drift_severity: data.drift_severity || 'none',
        };
        setLogs((prev) => [newLog, ...prev].slice(0, 50));

        if (isTrackEnabled && newLog.predicted_delay > 3.0) {
          triggerNotification(newLog.stop_name, newLog.predicted_delay);
        }
      } catch (err) {
        console.error(err);
      }
    };
    ws.onclose = () => {
      setIsConnected(false);
      setTimeout(connectWebSocket, 5000);
    };
  };

  const triggerNotification = async (stopName, delayMin) => {
    Vibration.vibrate([0, 200, 200, 200]);
    await Notifications.scheduleNotificationAsync({
      content: {
        title: '⚠️ Delay Alert: Route Tracker',
        body: `Delay detected at "${stopName}" | Delayed by ${delayMin.toFixed(1)} mins.`,
        sound: true,
      },
      trigger: null,
    });
  };

  const mockEvent = () => {
    const stops = ['MG Road', 'Indiranagar', 'Koramangala', 'HSR Layout', 'Whitefield'];
    const stop = stops[Math.floor(Math.random() * stops.length)];
    const delay = 3.2 + Math.random() * 5;
    
    const newLog = {
      id: Math.random().toString(),
      timestamp: new Date().toLocaleTimeString(),
      stop_name: stop,
      predicted_delay: delay,
      actual_delay: delay + (Math.random() - 0.5),
      drift_severity: Math.random() > 0.7 ? 'warning' : 'none',
    };
    setLogs((prev) => [newLog, ...prev].slice(0, 50));

    if (isTrackEnabled) {
      triggerNotification(stop, delay);
    }
  };

  return (
    <View style={S.container}>
      <View style={S.controlHeader}>
        <View style={S.statusRow}>
          <Ionicons name="radio" size={18} color={isConnected ? COLORS.teal : '#EF4444'} />
          <Text style={[S.statusText, { color: isConnected ? COLORS.teal : '#EF4444' }]}>
            {isConnected ? 'Telemetry Channel Online' : 'Telemetry Channel Offline'}
          </Text>
        </View>

        <View style={S.trackRow}>
          <View style={S.trackInfo}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Ionicons name={isTrackEnabled ? "notifications" : "notifications-off"} size={16} color={isTrackEnabled ? COLORS.brand : COLORS.dim} />
              <Text style={S.trackTitle}>Track Active Routes</Text>
            </View>
            <Text style={S.trackDesc}>Notification alerts when delay exceeds 3 min</Text>
          </View>
          <Switch
            value={isTrackEnabled}
            onValueChange={setIsTrackEnabled}
            trackColor={{ false: COLORS.border, true: COLORS.brand + '40' }}
            thumbColor={isTrackEnabled ? COLORS.brand : COLORS.dim}
          />
        </View>
      </View>

      <View style={S.listContainer}>
        <View style={S.listHeaderRow}>
          <Text style={S.listTitle}>Live Stream Logs</Text>
          <TouchableOpacity style={S.mockButton} onPress={mockEvent}>
            <Ionicons name="flash" size={12} color={COLORS.brand} style={{ marginRight: 4 }} />
            <Text style={S.mockButtonText}>Mock Delay</Text>
          </TouchableOpacity>
        </View>

        {logs.length === 0 ? (
          <View style={S.emptyContainer}>
            <Ionicons name="alert-circle-outline" size={28} color={COLORS.dim} style={{ marginBottom: 8 }} />
            <Text style={S.emptyText}>Awaiting logs from WebSocket stream...</Text>
          </View>
        ) : (
          <FlatList
            data={logs}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => (
              <View style={S.logCard}>
                <View style={S.logTopRow}>
                  <Text style={S.logStopName}>{item.stop_name}</Text>
                  <Text style={S.logTime}>{item.timestamp}</Text>
                </View>
                <View style={S.logBottomRow}>
                  <Text style={S.logDelayText}>
                    Predicted delay:{' '}
                    <Text style={{ color: item.predicted_delay > 3 ? '#FF6B6B' : COLORS.brand, fontWeight: 'bold' }}>
                      {item.predicted_delay.toFixed(1)}m
                    </Text>
                  </Text>
                  {item.drift_severity !== 'none' && (
                    <View style={S.alertBadge}>
                      <Text style={S.alertBadgeText}>{item.drift_severity.toUpperCase()}</Text>
                    </View>
                  )}
                </View>
              </View>
            )}
          />
        )}
      </View>
    </View>
  );
}
