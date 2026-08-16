import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, FlatList, TouchableOpacity, Switch, Vibration } from 'react-native';
import * as Notifications from 'expo-notifications';
import { Radio, Bell, BellOff, AlertTriangle, RefreshCw } from 'lucide-react-native';
import { WS_URL } from '../constants/config';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export default function LiveFeedScreen() {
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTrackEnabled, setIsTrackEnabled] = useState(false);
  const socketRef = useRef(null);

  // Request notifications permissions
  useEffect(() => {
    async function requestPermissions() {
      const { status } = await Notifications.requestPermissionsAsync();
      if (status !== 'granted') {
        console.log('Notification permissions not granted');
      }
    }
    requestPermissions();
  }, []);

  // Connect to live WebSocket feed
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    if (socketRef.current) {
      socketRef.current.close();
    }

    const ws = new WebSocket(WS_URL);
    socketRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('Live Telemetry socket open');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Add log with timestamp
        const newLog = {
          id: Math.random().toString(),
          timestamp: new Date().toLocaleTimeString(),
          stop_name: data.stop_name || 'MG Road',
          predicted_delay: data.predicted_delay !== undefined ? data.predicted_delay : (Math.random() * 8),
          actual_delay: data.actual_delay !== undefined ? data.actual_delay : (Math.random() * 8),
          drift_severity: data.drift_severity || 'none',
        };

        setLogs((prev) => [newLog, ...prev].slice(0, 100));

        // Check if delay > 3 min and tracking is enabled
        if (isTrackEnabled && newLog.predicted_delay > 3.0) {
          triggerNotification(newLog.stop_name, newLog.predicted_delay);
        }
      } catch (err) {
        console.error('Error parsing live socket event:', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('Live Telemetry socket closed');
      // Attempt reconnect after 5s
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = (err) => {
      console.error('Socket error:', err);
    };
  };

  const triggerNotification = async (stopName, delayMin) => {
    Vibration.vibrate([0, 250, 250, 250]); // vibrate alert
    await Notifications.scheduleNotificationAsync({
      content: {
        title: '⚠️ Delay Alert: Transit Route Tracker',
        body: `Severe delay detected at "${stopName}" | Delayed by ${delayMin.toFixed(1)} mins.`,
        sound: true,
      },
      trigger: null,
    });
  };

  // Mock a delay event for the demo
  const mockDelayEvent = () => {
    const stopsList = ['MG Road', 'Indiranagar', 'Koramangala', 'HSR Layout', 'Whitefield'];
    const randomStop = stopsList[Math.floor(Math.random() * stopsList.length)];
    const randomDelay = 3.5 + Math.random() * 6; // delay > 3 min
    
    const newLog = {
      id: Math.random().toString(),
      timestamp: new Date().toLocaleTimeString(),
      stop_name: randomStop,
      predicted_delay: randomDelay,
      actual_delay: randomDelay + (Math.random() - 0.5),
      drift_severity: Math.random() > 0.6 ? 'warning' : 'none',
    };

    setLogs((prev) => [newLog, ...prev].slice(0, 100));

    if (isTrackEnabled) {
      triggerNotification(randomStop, randomDelay);
    }
  };

  return (
    <View style={styles.container}>
      {/* Header controls */}
      <View style={styles.controlHeader}>
        <View style={styles.statusRow}>
          <Radio size={20} color={isConnected ? '#10B981' : '#EF4444'} />
          <Text style={[styles.statusText, { color: isConnected ? '#10B981' : '#EF4444' }]}>
            {isConnected ? 'Telemetry Channel Connected' : 'Telemetry Channel Offline'}
          </Text>
        </View>

        {/* Route Tracking config */}
        <View style={styles.trackRow}>
          <View style={styles.trackInfo}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              {isTrackEnabled ? <Bell size={18} color="#00E5FF" /> : <BellOff size={18} color="#94A3B8" />}
              <Text style={styles.trackTitle}>Track Active Routes</Text>
            </View>
            <Text style={styles.trackDesc}>Push alert when delay exceeds 3 mins</Text>
          </View>
          <Switch
            value={isTrackEnabled}
            onValueChange={setIsTrackEnabled}
            trackColor={{ false: '#334155', true: '#00E5FF40' }}
            thumbColor={isTrackEnabled ? '#00E5FF' : '#94A3B8'}
          />
        </View>
      </View>

      {/* Main scrolling logs */}
      <View style={styles.listContainer}>
        <View style={styles.listHeaderRow}>
          <Text style={styles.listTitle}>Live Stream Logs</Text>
          <TouchableOpacity style={styles.mockButton} onPress={mockDelayEvent}>
            <RefreshCw size={14} color="#00E5FF" style={{ marginRight: 4 }} />
            <Text style={styles.mockButtonText}>Simulate Delay</Text>
          </TouchableOpacity>
        </View>

        {logs.length === 0 ? (
          <View style={styles.emptyContainer}>
            <AlertTriangle size={32} color="#475569" style={{ marginBottom: 10 }} />
            <Text style={styles.emptyText}>Awaiting logs from live server...</Text>
          </View>
        ) : (
          <FlatList
            data={logs}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => (
              <View style={styles.logCard}>
                <View style={styles.logTopRow}>
                  <Text style={styles.logStopName}>{item.stop_name}</Text>
                  <Text style={styles.logTime}>{item.timestamp}</Text>
                </View>
                <View style={styles.logBottomRow}>
                  <Text style={styles.logDelayText}>
                    Predicted Delay:{' '}
                    <Text style={{ color: item.predicted_delay > 3 ? '#FF6B6B' : '#00E5FF', fontWeight: 'bold' }}>
                      {item.predicted_delay.toFixed(1)}m
                    </Text>
                  </Text>
                  {item.drift_severity !== 'none' && (
                    <View style={styles.alertBadge}>
                      <Text style={styles.alertBadgeText}>{item.drift_severity.toUpperCase()}</Text>
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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  controlHeader: {
    padding: 16,
    backgroundColor: '#1E293B',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  statusText: {
    marginLeft: 8,
    fontWeight: '700',
    fontSize: 14,
  },
  trackRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  trackInfo: {
    flex: 1,
  },
  trackTitle: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '700',
    marginLeft: 6,
  },
  trackDesc: {
    color: '#64748B',
    fontSize: 11,
    marginTop: 4,
  },
  listContainer: {
    flex: 1,
    padding: 16,
  },
  listHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  listTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
  },
  mockButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#00E5FF10',
    borderWidth: 1,
    borderColor: '#00E5FF20',
  },
  mockButtonText: {
    color: '#00E5FF',
    fontSize: 12,
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 60,
  },
  emptyText: {
    color: '#475569',
    fontSize: 14,
  },
  logCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 10,
  },
  logTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  logStopName: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '700',
  },
  logTime: {
    color: '#64748B',
    fontSize: 11,
  },
  logBottomRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logDelayText: {
    color: '#94A3B8',
    fontSize: 13,
  },
  alertBadge: {
    backgroundColor: '#EF444420',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderWidth: 1,
    borderColor: '#EF444440',
  },
  alertBadgeText: {
    color: '#EF4444',
    fontSize: 10,
    fontWeight: '700',
  },
});
