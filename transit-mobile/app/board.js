import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../api/client';
import { COLORS } from '../constants/config';

const S = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: { padding: 14, backgroundColor: COLORS.card, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  label:     { color: COLORS.sub, fontSize: 11, marginBottom: 4, marginTop: 10,
               textTransform: "uppercase", letterSpacing: 0.5 },
  dropdownTrigger: {
    backgroundColor: COLORS.surface, borderRadius: 10, height: 44,
    paddingHorizontal: 12, justifyContent: 'center', borderWidth: 0.5, borderColor: COLORS.border,
  },
  dropdownTriggerText: { color: COLORS.text, fontSize: 14 },
  dropdownList: {
    backgroundColor: COLORS.surface, borderRadius: 10, borderWidth: 0.5,
    borderColor: COLORS.border, maxHeight: 180, marginTop: 4,
  },
  dropdownItem: { padding: 12, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  dropdownItemText: { color: COLORS.text, fontSize: 13 },
  timerRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  timerText: { color: COLORS.dim, fontSize: 12, marginLeft: 6, flex: 1 },
  refreshButton: { padding: 4 },
  
  content: { flex: 1, padding: 14 },
  boardCard: { backgroundColor: COLORS.card, borderRadius: 10, borderWidth: 0.5, borderColor: COLORS.border, overflow: 'hidden' },
  boardHeader: { padding: 12, borderBottomWidth: 0.5, borderBottomColor: COLORS.border, backgroundColor: COLORS.card },
  boardTitle: { color: COLORS.text, fontSize: 14, fontWeight: '700' },
  boardSubtitle: { color: COLORS.brand, fontSize: 11, fontWeight: '600', marginTop: 2 },
  
  tableHeader: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 8, backgroundColor: COLORS.surface, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  tableLabel: { color: COLORS.dim, fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  tableRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  routeValue: { color: COLORS.brand, fontSize: 13, fontWeight: '700' },
  textValue: { color: COLORS.text, fontSize: 13 },
  predValue: { color: COLORS.text, fontSize: 13, fontWeight: '700' },
  statusValue: { fontSize: 12, fontWeight: '600' },
  noArrivals: { alignItems: 'center', paddingVertical: 32 },
  noArrivalsText: { color: COLORS.dim, fontSize: 13 },
});

export default function Board() {
  const [stops, setStops] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [boardData, setBoardData] = useState(null);
  const [countdown, setCountdown] = useState(30);

  useEffect(() => {
    api.getStops().then(data => {
      setStops(data);
      if (data.length > 0) setSelectedStop(data[0]);
    }).catch(() => {});
  }, []);

  const fetchBoard = async () => {
    if (!selectedStop) return;
    setLoading(true);
    try {
      const data = await api.getBoard(selectedStop.stop_id);
      setBoardData(data);
      setCountdown(30);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBoard();
  }, [selectedStop]);

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

  return (
    <View style={S.container}>
      <View style={S.header}>
        <Text style={S.label}>Select Station Board</Text>
        <TouchableOpacity style={S.dropdownTrigger} onPress={() => setShowDropdown(!showDropdown)}>
          <Text style={S.dropdownTriggerText}>
            {selectedStop ? selectedStop.name : 'Select stop...'}
          </Text>
        </TouchableOpacity>
        {showDropdown && (
          <View style={S.dropdownList}>
            {stops.map(s => (
              <TouchableOpacity key={s.stop_id} style={S.dropdownItem} onPress={() => { setSelectedStop(s); setShowDropdown(false) }}>
                <Text style={S.dropdownItemText}>{s.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <View style={S.timerRow}>
          <Ionicons name="time-outline" size={14} color={COLORS.dim} />
          <Text style={S.timerText}>Auto-refresh in {countdown}s</Text>
          <TouchableOpacity onPress={fetchBoard} style={S.refreshButton}>
            <Ionicons name="refresh" size={14} color={COLORS.brand} />
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView style={S.content}>
        {loading && !boardData && <ActivityIndicator color={COLORS.brand} style={{ marginTop: 32 }} />}

        {boardData && (
          <View style={S.boardCard}>
            <View style={S.boardHeader}>
              <Text style={S.boardTitle}>{boardData.stop_name} departures</Text>
              {boardData.live_delay && (
                <Text style={S.boardSubtitle}>
                  Current Live Delay: {Math.round(boardData.live_delay / 60)} min
                </Text>
              )}
            </View>

            <View style={S.tableHeader}>
              <Text style={[S.tableLabel, { width: '15%' }]}>Route</Text>
              <Text style={[S.tableLabel, { width: '35%' }]}>Destination</Text>
              <Text style={[S.tableLabel, { width: '15%' }]}>Sched</Text>
              <Text style={[S.tableLabel, { width: '15%' }]}>Pred</Text>
              <Text style={[S.tableLabel, { width: '20%', textAlign: 'right' }]}>Status</Text>
            </View>

            {boardData.arrivals && boardData.arrivals.length === 0 ? (
              <View style={S.noArrivals}>
                <Ionicons name="alert-circle" size={24} color={COLORS.dim} style={{ marginBottom: 8 }} />
                <Text style={S.noArrivalsText}>No upcoming departures</Text>
              </View>
            ) : (
              boardData.arrivals && boardData.arrivals.map((arr, idx) => (
                <View key={idx} style={S.tableRow}>
                  <Text style={[S.routeValue, { width: '15%' }]}>{arr.route}</Text>
                  <Text style={[S.textValue, { width: '35%' }]} numberOfLines={1}>{arr.destination}</Text>
                  <Text style={[S.textValue, { width: '15%' }]}>{arr.scheduled_time}</Text>
                  <Text style={[S.predValue, { width: '15%' }]}>{arr.predicted_time}</Text>
                  <Text style={[
                    S.statusValue, 
                    { 
                      width: '20%', 
                      textAlign: 'right',
                      color: arr.delay_minutes > 5 ? '#FF6B6B' : (arr.delay_minutes > 0 ? COLORS.yellow : COLORS.teal)
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
