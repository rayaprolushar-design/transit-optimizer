import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Clock, RefreshCw, AlertTriangle } from 'lucide-react-native';
import { API_URL } from '../constants/config';

export default function BoardScreen() {
  const [stops, setStops] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [boardData, setBoardData] = useState(null);
  const [countdown, setCountdown] = useState(30);

  useEffect(() => {
    fetchStops();
  }, []);

  const fetchStops = async () => {
    try {
      const res = await fetch(`${API_URL}/stops?limit=100`);
      const data = await res.json();
      setStops(data);
      if (data.length > 0) {
        setSelectedStop(data[0]);
      }
    } catch (err) {
      console.error('Error fetching stops:', err);
    }
  };

  const fetchBoard = async () => {
    if (!selectedStop) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/board/${selectedStop.stop_id}`);
      const data = await res.json();
      setBoardData(data);
      setCountdown(30); // reset countdown
    } catch (err) {
      console.error('Error fetching board:', err);
    } finally {
      setLoading(false);
    }
  };

  // Refresh whenever selected stop changes
  useEffect(() => {
    if (selectedStop) {
      fetchBoard();
    }
  }, [selectedStop]);

  // Auto-refresh countdown loop
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          fetchBoard();
          return 30;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [selectedStop]);

  const selectStop = (stop) => {
    setSelectedStop(stop);
    setShowDropdown(false);
  };

  return (
    <View style={styles.container}>
      {/* Top selector */}
      <View style={styles.header}>
        <Text style={styles.label}>Select Station Board</Text>
        <TouchableOpacity 
          style={styles.dropdownTrigger}
          onPress={() => setShowDropdown(!showDropdown)}
        >
          <Text style={styles.dropdownTriggerText}>
            {selectedStop ? selectedStop.name : 'Select transit stop'}
          </Text>
        </TouchableOpacity>

        {showDropdown && (
          <View style={styles.dropdownList}>
            {stops.map(stop => (
              <TouchableOpacity 
                key={stop.stop_id} 
                style={styles.dropdownItem}
                onPress={() => selectStop(stop)}
              >
                <Text style={styles.dropdownItemText}>{stop.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <View style={styles.timerRow}>
          <Clock size={14} color="#94A3B8" />
          <Text style={styles.timerText}>Auto-refreshing in {countdown}s</Text>
          <TouchableOpacity onPress={fetchBoard} style={styles.refreshButton}>
            <RefreshCw size={14} color="#00E5FF" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Departures Grid */}
      <ScrollView style={styles.content}>
        {loading && !boardData && (
          <ActivityIndicator size="large" color="#00E5FF" style={{ marginTop: 40 }} />
        )}

        {boardData && (
          <View style={styles.boardCard}>
            <View style={styles.boardHeader}>
              <Text style={styles.boardTitle}>{boardData.stop_name} Departures</Text>
              {boardData.live_delay && (
                <Text style={styles.boardSubtitle}>
                  Current Live Delay: {Math.round(boardData.live_delay / 60)} min
                </Text>
              )}
            </View>

            {/* List Table Headers */}
            <View style={styles.tableHeader}>
              <Text style={[styles.tableLabel, { width: '15%' }]}>Route</Text>
              <Text style={[styles.tableLabel, { width: '35%' }]}>Destination</Text>
              <Text style={[styles.tableLabel, { width: '15%' }]}>Sched</Text>
              <Text style={[styles.tableLabel, { width: '15%' }]}>Pred</Text>
              <Text style={[styles.tableLabel, { width: '20%', textAlign: 'right' }]}>Status</Text>
            </View>

            {/* Table Rows */}
            {boardData.arrivals && boardData.arrivals.length === 0 ? (
              <View style={styles.noArrivals}>
                <AlertTriangle size={24} color="#475569" style={{ marginBottom: 8 }} />
                <Text style={styles.noArrivalsText}>No upcoming departures</Text>
              </View>
            ) : (
              boardData.arrivals && boardData.arrivals.map((arr, idx) => (
                <View key={idx} style={styles.tableRow}>
                  <Text style={[styles.routeValue, { width: '15%' }]}>{arr.route}</Text>
                  <Text style={[styles.textValue, { width: '35%' }]} numberOfLines={1}>
                    {arr.destination}
                  </Text>
                  <Text style={[styles.textValue, { width: '15%' }]}>{arr.scheduled_time}</Text>
                  <Text style={[styles.predValue, { width: '15%' }]}>{arr.predicted_time}</Text>
                  <Text style={[
                    styles.statusValue, 
                    { 
                      width: '20%', 
                      textAlign: 'right',
                      color: arr.delay_minutes > 5 ? '#FF6B6B' : (arr.delay_minutes > 0 ? '#F59E0B' : '#10B981')
                    }
                  ]}>
                    {arr.status || 'On Time'}
                  </Text>
                </View>
              ))
            )}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  header: {
    padding: 16,
    backgroundColor: '#1E293B',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  label: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  dropdownTrigger: {
    backgroundColor: '#0F172A',
    borderRadius: 10,
    height: 44,
    paddingHorizontal: 12,
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  dropdownTriggerText: {
    color: '#F8FAFC',
    fontSize: 14,
  },
  dropdownList: {
    backgroundColor: '#0F172A',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#334155',
    maxHeight: 180,
    marginTop: 4,
  },
  dropdownItem: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  dropdownItemText: {
    color: '#F8FAFC',
    fontSize: 14,
  },
  timerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
  },
  timerText: {
    color: '#64748B',
    fontSize: 12,
    marginLeft: 6,
    flex: 1,
  },
  refreshButton: {
    padding: 4,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  boardCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#334155',
    overflow: 'hidden',
  },
  boardHeader: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
    backgroundColor: '#1E293B',
  },
  boardTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
  },
  boardSubtitle: {
    color: '#00E5FF',
    fontSize: 12,
    fontWeight: '600',
    marginTop: 4,
  },
  tableHeader: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#0F172A',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  tableLabel: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  routeValue: {
    color: '#00E5FF',
    fontSize: 13,
    fontWeight: '700',
  },
  textValue: {
    color: '#F8FAFC',
    fontSize: 13,
  },
  predValue: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '700',
  },
  statusValue: {
    fontSize: 12,
    fontWeight: '600',
  },
  noArrivals: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  noArrivalsText: {
    color: '#475569',
    fontSize: 13,
  },
});
