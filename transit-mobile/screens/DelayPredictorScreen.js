import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, FlatList, ActivityIndicator } from 'react-native';
import Slider from '@react-native-community/slider';
import { Brain, CloudRain, Sun, AlertCircle } from 'lucide-react-native';
import { API_URL } from '../constants/config';

export default function DelayPredictorScreen() {
  const [stops, setStops] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStop, setSelectedStop] = useState(null);
  const [filteredStops, setFilteredStops] = useState([]);
  const [hour, setHour] = useState(8);
  const [isWeekend, setIsWeekend] = useState(0);
  const [priorDelay, setPriorDelay] = useState(2.0);
  const [weatherDeviation, setWeatherDeviation] = useState(0.0); // 0.0 for Sunny, 1.8 for Rainy
  
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);

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
        setSearchQuery(data[0].name);
      }
    } catch (err) {
      console.error('Error fetching stops:', err);
    }
  };

  const handleSearch = (text) => {
    setSearchQuery(text);
    setSelectedStop(null);
    if (text.trim() === '') {
      setFilteredStops([]);
    } else {
      const filtered = stops.filter(s => s.name.toLowerCase().includes(text.toLowerCase()));
      setFilteredStops(filtered);
    }
  };

  const selectStop = (stop) => {
    setSelectedStop(stop);
    setSearchQuery(stop.name);
    setFilteredStops([]);
    setShowDropdown(false);
  };

  const getPrediction = async () => {
    if (!selectedStop) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/predict-delay-ci`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stop_id: selectedStop.stop_id,
          hour: hour,
          is_weekend: isWeekend,
          prior_stop_delay: priorDelay,
          temp_deviation: weatherDeviation,
          stop_sequence_norm: 0.5,
          route_type: 3,
          n_stops_on_trip: 6
        })
      });
      const data = await res.json();
      setPrediction(data);
    } catch (err) {
      console.error('Prediction error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Trigger prediction on values change
  useEffect(() => {
    if (selectedStop) {
      getPrediction();
    }
  }, [selectedStop, hour, isWeekend, priorDelay, weatherDeviation]);

  const getConfidenceColor = (score) => {
    if (score >= 80) return '#10B981'; // green
    if (score >= 50) return '#F59E0B'; // orange
    return '#EF4444'; // red
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.cardHeader}>Prediction Inputs</Text>
        
        {/* Stop Selector */}
        <Text style={styles.label}>Select Stop</Text>
        <TouchableOpacity 
          style={styles.dropdownTrigger}
          onPress={() => setShowDropdown(!showDropdown)}
        >
          <Text style={styles.dropdownTriggerText}>
            {selectedStop ? selectedStop.name : 'Select a transit stop'}
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

        {/* Hour Slider */}
        <View style={styles.sliderHeader}>
          <Text style={styles.label}>Hour of Day</Text>
          <Text style={styles.valueText}>{hour}:00</Text>
        </View>
        <Slider
          style={styles.slider}
          minimumValue={0}
          maximumValue={23}
          step={1}
          value={hour}
          onValueChange={setHour}
          minimumTrackTintColor="#00E5FF"
          maximumTrackTintColor="#334155"
          thumbTintColor="#00E5FF"
        />

        {/* Prior Delay Slider */}
        <View style={styles.sliderHeader}>
          <Text style={styles.label}>Prior Stop Delay</Text>
          <Text style={styles.valueText}>{priorDelay.toFixed(1)} min</Text>
        </View>
        <Slider
          style={styles.slider}
          minimumValue={0.0}
          maximumValue={15.0}
          step={0.5}
          value={priorDelay}
          onValueChange={setPriorDelay}
          minimumTrackTintColor="#00E5FF"
          maximumTrackTintColor="#334155"
          thumbTintColor="#00E5FF"
        />

        {/* Weekend Selector */}
        <Text style={styles.label}>Day of Operation</Text>
        <View style={styles.buttonGroup}>
          <TouchableOpacity 
            style={[styles.groupButton, isWeekend === 0 && styles.activeGroupButton]}
            onPress={() => setIsWeekend(0)}
          >
            <Text style={[styles.groupButtonText, isWeekend === 0 && styles.activeGroupButtonText]}>Weekday</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.groupButton, isWeekend === 1 && styles.activeGroupButton]}
            onPress={() => setIsWeekend(1)}
          >
            <Text style={[styles.groupButtonText, isWeekend === 1 && styles.activeGroupButtonText]}>Weekend</Text>
          </TouchableOpacity>
        </View>

        {/* Weather Selector */}
        <Text style={styles.label}>Weather Conditions</Text>
        <View style={styles.buttonGroup}>
          <TouchableOpacity 
            style={[styles.groupButton, weatherDeviation === 0.0 && styles.activeGroupButton]}
            onPress={() => setWeatherDeviation(0.0)}
          >
            <Sun size={16} color={weatherDeviation === 0.0 ? '#0F172A' : '#94A3B8'} style={{ marginRight: 6 }} />
            <Text style={[styles.groupButtonText, weatherDeviation === 0.0 && styles.activeGroupButtonText]}>Normal / Clear</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.groupButton, weatherDeviation === 1.8 && styles.activeGroupButton]}
            onPress={() => setWeatherDeviation(1.8)}
          >
            <CloudRain size={16} color={weatherDeviation === 1.8 ? '#0F172A' : '#94A3B8'} style={{ marginRight: 6 }} />
            <Text style={[styles.groupButtonText, weatherDeviation === 1.8 && styles.activeGroupButtonText]}>Heavy Rain</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Prediction Output Card */}
      {loading && (
        <ActivityIndicator size="large" color="#00E5FF" style={{ marginTop: 20, marginBottom: 30 }} />
      )}

      {prediction && !loading && (
        <View style={styles.outputCard}>
          <View style={styles.outputHeaderRow}>
            <Text style={styles.outputTitle}>Confidence Interval (CI)</Text>
            <View style={[styles.scoreBadge, { backgroundColor: getConfidenceColor(prediction.confidence) + '20' }]}>
              <Text style={[styles.scoreText, { color: getConfidenceColor(prediction.confidence) }]}>
                {prediction.confidence}% Conf
              </Text>
            </View>
          </View>

          {/* Large delay display */}
          <View style={styles.medianContainer}>
            <Text style={styles.medianLabel}>Median Predicted Delay</Text>
            <Text style={styles.medianValue}>{prediction.p50} min</Text>
          </View>

          {/* CI visual interval gauge */}
          <View style={styles.gaugeContainer}>
            <View style={styles.gaugeHeader}>
              <Text style={styles.gaugeLabel}>p10 (Optimistic)</Text>
              <Text style={styles.gaugeLabel}>p90 (Pessimistic)</Text>
            </View>
            <View style={styles.gaugeTrack}>
              <View style={[styles.gaugeRange, { left: '15%', width: '70%' }]} />
              <View style={[styles.gaugeMarker, { left: '15%' }]} />
              <View style={[styles.gaugeMedianMarker, { left: '50%' }]} />
              <View style={[styles.gaugeMarker, { left: '85%' }]} />
            </View>
            <View style={styles.gaugeValues}>
              <Text style={styles.gaugeValue}>{prediction.p10} min</Text>
              <Text style={[styles.gaugeValue, { color: '#00E5FF', fontWeight: 'bold' }]}>{prediction.p50} min</Text>
              <Text style={styles.gaugeValue}>{prediction.p90} min</Text>
            </View>
          </View>

          {/* Reliability insight box */}
          <View style={styles.insightBox}>
            <AlertCircle size={18} color="#00E5FF" style={{ marginRight: 8, marginTop: 2 }} />
            <Text style={styles.insightText}>
              {prediction.interpretation} Interval width is {prediction.interval_width} min. Use p90 delay to guarantee catching connections.
            </Text>
          </View>
        </View>
      )}
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
    padding: 16,
  },
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  cardHeader: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 16,
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
    marginBottom: 14,
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
    overflow: 'scroll',
    marginBottom: 14,
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
  sliderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  valueText: {
    color: '#00E5FF',
    fontSize: 14,
    fontWeight: '700',
  },
  slider: {
    width: '100%',
    height: 40,
    marginBottom: 12,
  },
  buttonGroup: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  groupButton: {
    flex: 1,
    height: 40,
    borderRadius: 10,
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#334155',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 4,
  },
  activeGroupButton: {
    backgroundColor: '#00E5FF',
    borderColor: '#00E5FF',
  },
  groupButtonText: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: '600',
  },
  activeGroupButtonText: {
    color: '#0F172A',
    fontWeight: '700',
  },
  outputCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155',
    marginTop: 16,
  },
  outputHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  outputTitle: {
    color: '#F8FAFC',
    fontSize: 15,
    fontWeight: '700',
  },
  scoreBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  scoreText: {
    fontSize: 12,
    fontWeight: '700',
  },
  medianContainer: {
    alignItems: 'center',
    marginVertical: 10,
  },
  medianLabel: {
    color: '#94A3B8',
    fontSize: 12,
  },
  medianValue: {
    color: '#F8FAFC',
    fontSize: 32,
    fontWeight: '800',
    marginTop: 4,
  },
  gaugeContainer: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#334155',
    marginVertical: 14,
  },
  gaugeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  gaugeLabel: {
    color: '#64748B',
    fontSize: 10,
    textTransform: 'uppercase',
  },
  gaugeTrack: {
    height: 6,
    backgroundColor: '#334155',
    borderRadius: 3,
    marginVertical: 10,
    position: 'relative',
  },
  gaugeRange: {
    position: 'absolute',
    height: '100%',
    backgroundColor: '#00E5FF30',
    borderRadius: 3,
  },
  gaugeMarker: {
    position: 'absolute',
    top: -3,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#64748B',
  },
  gaugeMedianMarker: {
    position: 'absolute',
    top: -4,
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: '#00E5FF',
    borderWidth: 2,
    borderColor: '#0F172A',
  },
  gaugeValues: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  gaugeValue: {
    color: '#94A3B8',
    fontSize: 11,
  },
  insightBox: {
    flexDirection: 'row',
    backgroundColor: '#00E5FF08',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#00E5FF1A',
    marginTop: 10,
  },
  insightText: {
    flex: 1,
    color: '#E2E8F0',
    fontSize: 12,
    lineHeight: 18,
  },
});
