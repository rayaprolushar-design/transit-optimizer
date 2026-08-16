import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, TextInput, FlatList, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import { Navigation, AlertCircle, Compass, DollarSign, Clock, MapPin } from 'lucide-react-native';
import { API_URL } from '../constants/config';

export default function RoutePlannerScreen() {
  const [fromSearch, setFromSearch] = useState('');
  const [toSearch, setToSearch] = useState('');
  const [stops, setStops] = useState([]);
  const [filteredFromStops, setFilteredFromStops] = useState([]);
  const [filteredToStops, setFilteredToStops] = useState([]);
  const [selectedFrom, setSelectedFrom] = useState(null);
  const [selectedTo, setSelectedTo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [routeData, setRouteData] = useState(null);
  const [activeInput, setActiveInput] = useState(null); // 'from' | 'to' | null

  // Fetch stops list on mount
  useEffect(() => {
    fetchStops();
  }, []);

  const fetchStops = async () => {
    try {
      const res = await fetch(`${API_URL}/stops?limit=100`);
      const data = await res.json();
      setStops(data);
    } catch (err) {
      console.error('Error fetching stops:', err);
    }
  };

  const handleSearch = (text, type) => {
    if (type === 'from') {
      setFromSearch(text);
      setSelectedFrom(null);
      if (text.trim() === '') {
        setFilteredFromStops([]);
      } else {
        const filtered = stops.filter(s => s.name.toLowerCase().includes(text.toLowerCase()));
        setFilteredFromStops(filtered);
      }
    } else {
      setToSearch(text);
      setSelectedTo(null);
      if (text.trim() === '') {
        setFilteredToStops([]);
      } else {
        const filtered = stops.filter(s => s.name.toLowerCase().includes(text.toLowerCase()));
        setFilteredToStops(filtered);
      }
    }
  };

  const selectStop = (stop, type) => {
    if (type === 'from') {
      setSelectedFrom(stop);
      setFromSearch(stop.name);
      setFilteredFromStops([]);
    } else {
      setSelectedTo(stop);
      setToSearch(stop.name);
      setFilteredToStops([]);
    }
    setActiveInput(null);
  };

  const findRoute = async () => {
    if (!selectedFrom || !selectedTo) return;
    setLoading(true);
    setRouteData(null);
    try {
      const res = await fetch(`${API_URL}/route?from=${encodeURIComponent(selectedFrom.name)}&to=${encodeURIComponent(selectedTo.name)}&algorithm=astar`);
      const data = await res.json();
      setRouteData(data);
    } catch (err) {
      console.error('Error finding route:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* Search Header */}
      <View style={styles.searchBox}>
        <View style={styles.inputContainer}>
          <MapPin size={18} color="#A0AEC0" style={styles.icon} />
          <TextInput
            style={styles.input}
            placeholder="From: e.g. MG Road"
            placeholderTextColor="#718096"
            value={fromSearch}
            onChangeText={(text) => handleSearch(text, 'from')}
            onFocus={() => setActiveInput('from')}
          />
        </View>
        
        {activeInput === 'from' && filteredFromStops.length > 0 && (
          <FlatList
            style={styles.autocomplete}
            data={filteredFromStops}
            keyExtractor={(item) => item.stop_id}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.autocompleteItem} onPress={() => selectStop(item, 'from')}>
                <Text style={styles.autocompleteText}>{item.name}</Text>
              </TouchableOpacity>
            )}
          />
        )}

        <View style={[styles.inputContainer, { marginTop: 10 }]}>
          <MapPin size={18} color="#FF6B6B" style={styles.icon} />
          <TextInput
            style={styles.input}
            placeholder="To: e.g. HSR Layout"
            placeholderTextColor="#718096"
            value={toSearch}
            onChangeText={(text) => handleSearch(text, 'to')}
            onFocus={() => setActiveInput('to')}
          />
        </View>

        {activeInput === 'to' && filteredToStops.length > 0 && (
          <FlatList
            style={styles.autocomplete}
            data={filteredToStops}
            keyExtractor={(item) => item.stop_id}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.autocompleteItem} onPress={() => selectStop(item, 'to')}>
                <Text style={styles.autocompleteText}>{item.name}</Text>
              </TouchableOpacity>
            )}
          />
        )}

        <TouchableOpacity 
          style={[styles.button, (!selectedFrom || !selectedTo) && styles.disabledButton]} 
          onPress={findRoute}
          disabled={!selectedFrom || !selectedTo}
        >
          <Text style={styles.buttonText}>Find Fastest Route</Text>
        </TouchableOpacity>
      </View>

      {/* Main viewport */}
      <ScrollView style={styles.content}>
        {loading && (
          <ActivityIndicator size="large" color="#00E5FF" style={{ marginTop: 40 }} />
        )}

        {/* Route Details Card */}
        {routeData && (
          <View style={styles.routeCard}>
            <Text style={styles.routeHeader}>Optimal Route Details</Text>
            
            {/* Quick Metrics */}
            <View style={styles.metricsGrid}>
              <View style={styles.metricCard}>
                <Clock size={16} color="#00E5FF" />
                <Text style={styles.metricLabel}>Duration</Text>
                <Text style={styles.metricValue}>{Math.round(routeData.total_duration_min)} min</Text>
              </View>
              <View style={styles.metricCard}>
                <Compass size={16} color="#00E5FF" />
                <Text style={styles.metricLabel}>Distance</Text>
                <Text style={styles.metricValue}>{routeData.total_distance_km.toFixed(1)} km</Text>
              </View>
              <View style={styles.metricCard}>
                <DollarSign size={16} color="#00E5FF" />
                <Text style={styles.metricLabel}>Est. Cost</Text>
                <Text style={styles.metricValue}>₹{Math.round(routeData.total_cost || 30)}</Text>
              </View>
            </View>

            {/* Styled Map Polyline fallback */}
            <View style={styles.mockMapContainer}>
              <View style={styles.mockMapBorder}>
                <Text style={styles.mockMapLabel}>Transit Route Visualization</Text>
                <View style={styles.mockMapPolyline}>
                  <View style={styles.mockMapStartPoint} />
                  <View style={styles.mockMapLine} />
                  <View style={styles.mockMapEndPoint} />
                </View>
                <Text style={styles.mockMapStartText}>{selectedFrom?.name}</Text>
                <Text style={styles.mockMapEndText}>{selectedTo?.name}</Text>
              </View>
            </View>

            {/* Route Instructions */}
            <Text style={styles.sectionTitle}>Directions</Text>
            {routeData.instructions && routeData.instructions.map((inst, index) => (
              <View key={index} style={styles.stepRow}>
                <View style={styles.stepIndexContainer}>
                  <Text style={styles.stepIndex}>{index + 1}</Text>
                </View>
                <View style={styles.stepInfo}>
                  <Text style={styles.stepText}>{inst.instruction}</Text>
                  <Text style={styles.stepDetails}>
                    {inst.duration_min} min · {inst.distance_km.toFixed(1)} km
                  </Text>
                </View>
              </View>
            ))}
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
  searchBox: {
    padding: 16,
    backgroundColor: '#1E293B',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0F172A',
    borderRadius: 10,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  icon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    height: 44,
    color: '#F8FAFC',
    fontSize: 15,
  },
  autocomplete: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    maxHeight: 150,
    borderRadius: 8,
    marginTop: 4,
  },
  autocompleteItem: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  autocompleteText: {
    color: '#F8FAFC',
    fontSize: 14,
  },
  button: {
    backgroundColor: '#00E5FF',
    borderRadius: 10,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 14,
  },
  disabledButton: {
    backgroundColor: '#475569',
  },
  buttonText: {
    color: '#0F172A',
    fontWeight: '700',
    fontSize: 16,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  routeCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 30,
  },
  routeHeader: {
    color: '#F8FAFC',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 14,
  },
  metricsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  metricCard: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    width: '31%',
    borderWidth: 1,
    borderColor: '#334155',
  },
  metricLabel: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 4,
    marginBottom: 2,
  },
  metricValue: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '700',
  },
  mockMapContainer: {
    height: 140,
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 20,
    justifyContent: 'center',
  },
  mockMapBorder: {
    alignItems: 'center',
  },
  mockMapLabel: {
    color: '#64748B',
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 16,
  },
  mockMapPolyline: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '75%',
  },
  mockMapStartPoint: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#00E5FF',
  },
  mockMapLine: {
    flex: 1,
    height: 3,
    backgroundColor: '#00E5FF',
    opacity: 0.8,
  },
  mockMapEndPoint: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#FF6B6B',
  },
  mockMapStartText: {
    color: '#94A3B8',
    fontSize: 12,
    position: 'absolute',
    left: '10%',
    top: 36,
  },
  mockMapEndText: {
    color: '#94A3B8',
    fontSize: 12,
    position: 'absolute',
    right: '10%',
    top: 36,
  },
  sectionTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
    paddingBottom: 6,
  },
  stepRow: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  stepIndexContainer: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#00E5FF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    marginTop: 2,
  },
  stepIndex: {
    color: '#00E5FF',
    fontWeight: '700',
    fontSize: 12,
  },
  stepInfo: {
    flex: 1,
  },
  stepText: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '500',
    lineHeight: 20,
  },
  stepDetails: {
    color: '#94A3B8',
    fontSize: 12,
    marginTop: 4,
  },
});
