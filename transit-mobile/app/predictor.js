import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import Slider from '@react-native-community/slider';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../api/client';
import { COLORS } from '../constants/config';

const S = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg, padding: 14 },
  card:      { backgroundColor: COLORS.card, borderRadius: 10, padding: 14,
               borderWidth: 0.5, borderColor: COLORS.border },
  cardHeader: { color: COLORS.text, fontSize: 15, fontWeight: '700', marginBottom: 12 },
  label:     { color: COLORS.sub, fontSize: 11, marginBottom: 4, marginTop: 10,
               textTransform: "uppercase", letterSpacing: 0.5 },
  dropdownTrigger: {
    backgroundColor: COLORS.surface, borderRadius: 10, height: 44,
    paddingHorizontal: 12, justifyContent: 'center', borderWidth: 0.5,
    borderColor: COLORS.border, marginBottom: 12,
  },
  dropdownTriggerText: { color: COLORS.text, fontSize: 14 },
  dropdownList: {
    backgroundColor: COLORS.surface, borderRadius: 10, borderWidth: 0.5,
    borderColor: COLORS.border, maxHeight: 180, overflow: 'scroll', marginBottom: 12,
  },
  dropdownItem: { padding: 12, borderBottomWidth: 0.5, borderBottomColor: COLORS.border },
  dropdownItemText: { color: COLORS.text, fontSize: 13 },
  sliderHeader: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  valueText: { color: COLORS.brand, fontSize: 14, fontWeight: '700' },
  slider: { width: '100%', height: 40, marginBottom: 12 },
  buttonGroup: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 12 },
  groupButton: {
    flex: 1, height: 40, borderRadius: 10, backgroundColor: COLORS.surface,
    borderWidth: 0.5, borderColor: COLORS.border, flexDirection: 'row',
    alignItems: 'center', justifyContent: 'center', marginHorizontal: 4,
  },
  activeGroupButton: { backgroundColor: COLORS.brand + "33", borderColor: COLORS.brand },
  groupButtonText: { color: COLORS.sub, fontSize: 13, fontWeight: '600' },
  activeGroupButtonText: { color: COLORS.brand, fontWeight: '700' },
  
  outputCard: {
    backgroundColor: COLORS.card, borderRadius: 10, padding: 14,
    borderWidth: 0.5, borderColor: COLORS.border, marginTop: 14,
  },
  outputHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  outputTitle: { color: COLORS.text, fontSize: 14, fontWeight: '700' },
  scoreBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  scoreText: { fontSize: 12, fontWeight: '700' },
  medianContainer: { alignItems: 'center', marginVertical: 8 },
  medianLabel: { color: COLORS.sub, fontSize: 12 },
  medianValue: { color: COLORS.text, fontSize: 32, fontWeight: '800', marginTop: 4 },
  
  gaugeContainer: {
    backgroundColor: COLORS.surface, borderRadius: 10, padding: 12,
    borderWidth: 0.5, borderColor: COLORS.border, marginVertical: 12,
  },
  gaugeHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  gaugeLabel: { color: COLORS.dim, fontSize: 10, textTransform: 'uppercase' },
  gaugeTrack: { height: 6, backgroundColor: COLORS.border, borderRadius: 3, marginVertical: 8, position: 'relative' },
  gaugeRange: { position: 'absolute', height: '100%', backgroundColor: COLORS.brand + '20', borderRadius: 3 },
  gaugeMarker: { position: 'absolute', top: -3, width: 12, height: 12, borderRadius: 6, backgroundColor: COLORS.dim },
  gaugeMedianMarker: {
    position: 'absolute', top: -4, width: 14, height: 14, borderRadius: 7,
    backgroundColor: COLORS.brand, borderWidth: 2, borderColor: COLORS.surface,
  },
  gaugeValues: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  gaugeValue: { color: COLORS.sub, fontSize: 11 },
  insightBox: {
    flexDirection: 'row', backgroundColor: COLORS.brand + '08', borderRadius: 10,
    padding: 12, borderWidth: 0.5, borderColor: COLORS.brand + '20', marginTop: 8,
  },
  insightText: { flex: 1, color: COLORS.text, fontSize: 12, lineHeight: 18 },
});

export default function DelayPredictor() {
  const [stops, setStops] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [hour, setHour] = useState(8);
  const [isWeekend, setIsWeekend] = useState(0);
  const [priorDelay, setPriorDelay] = useState(2.0);
  const [weatherDeviation, setWeatherDeviation] = useState(0.0);
  
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState(null);

  useEffect(() => {
    api.getStops().then(data => {
      setStops(data);
      if (data.length > 0) setSelectedStop(data[0]);
    }).catch(() => {});
  }, []);

  const getPrediction = async () => {
    if (!selectedStop) return;
    setLoading(true);
    try {
      const data = await api.predictDelay({
        stop_id: selectedStop.stop_id,
        hour: hour,
        is_weekend: isWeekend,
        prior_stop_delay: priorDelay,
        temp_deviation: weatherDeviation,
        stop_sequence_norm: 0.5,
        route_type: 3,
        n_stops_on_trip: 6
      });
      setPrediction(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    getPrediction();
  }, [selectedStop, hour, isWeekend, priorDelay, weatherDeviation]);

  const getConfidenceColor = (score) => {
    if (score >= 80) return COLORS.teal;
    if (score >= 50) return COLORS.yellow;
    return '#EF4444';
  };

  return (
    <ScrollView style={S.container}>
      <View style={S.card}>
        <Text style={S.cardHeader}>Prediction Configurations</Text>
        
        {/* Stop Selector */}
        <Text style={S.label}>Stop Name</Text>
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

        {/* Hour Slider */}
        <View style={S.sliderHeader}>
          <Text style={S.label}>Hour</Text>
          <Text style={S.valueText}>{hour}:00</Text>
        </View>
        <Slider
          style={S.slider}
          minimumValue={0}
          maximumValue={23}
          step={1}
          value={hour}
          onValueChange={setHour}
          minimumTrackTintColor={COLORS.brand}
          maximumTrackTintColor={COLORS.border}
          thumbTintColor={COLORS.brand}
        />

        {/* Prior Delay Slider */}
        <View style={S.sliderHeader}>
          <Text style={S.label}>Prior Delay</Text>
          <Text style={S.valueText}>{priorDelay.toFixed(1)} min</Text>
        </View>
        <Slider
          style={S.slider}
          minimumValue={0.0}
          maximumValue={15.0}
          step={0.5}
          value={priorDelay}
          onValueChange={setPriorDelay}
          minimumTrackTintColor={COLORS.brand}
          maximumTrackTintColor={COLORS.border}
          thumbTintColor={COLORS.brand}
        />

        {/* Day Selector */}
        <Text style={S.label}>Day classification</Text>
        <View style={S.buttonGroup}>
          <TouchableOpacity style={[S.groupButton, isWeekend === 0 && S.activeGroupButton]} onPress={() => setIsWeekend(0)}>
            <Text style={[S.groupButtonText, isWeekend === 0 && S.activeGroupButtonText]}>Weekday</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[S.groupButton, isWeekend === 1 && S.activeGroupButton]} onPress={() => setIsWeekend(1)}>
            <Text style={[S.groupButtonText, isWeekend === 1 && S.activeGroupButtonText]}>Weekend</Text>
          </TouchableOpacity>
        </View>

        {/* Weather Selector */}
        <Text style={S.label}>Weather Conditions</Text>
        <View style={S.buttonGroup}>
          <TouchableOpacity style={[S.groupButton, weatherDeviation === 0.0 && S.activeGroupButton]} onPress={() => setWeatherDeviation(0.0)}>
            <Ionicons name="sunny" size={14} color={weatherDeviation === 0.0 ? COLORS.brand : COLORS.dim} style={{ marginRight: 6 }} />
            <Text style={[S.groupButtonText, weatherDeviation === 0.0 && S.activeGroupButtonText]}>Clear</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[S.groupButton, weatherDeviation === 1.8 && S.activeGroupButton]} onPress={() => setWeatherDeviation(1.8)}>
            <Ionicons name="rainy" size={14} color={weatherDeviation === 1.8 ? COLORS.brand : COLORS.dim} style={{ marginRight: 6 }} />
            <Text style={[S.groupButtonText, weatherDeviation === 1.8 && S.activeGroupButtonText]}>Rainy</Text>
          </TouchableOpacity>
        </View>
      </View>

      {loading && !prediction && <ActivityIndicator color={COLORS.brand} style={{ marginVertical: 20 }} />}

      {prediction && !loading && (
        <View style={S.outputCard}>
          <View style={S.outputHeaderRow}>
            <Text style={S.outputTitle}>Delay Bounds</Text>
            <View style={[S.scoreBadge, { backgroundColor: getConfidenceColor(prediction.confidence) + '20' }]}>
              <Text style={[S.scoreText, { color: getConfidenceColor(prediction.confidence) }]}>
                {prediction.confidence}% Conf
              </Text>
            </View>
          </View>

          <View style={S.medianContainer}>
            <Text style={S.medianLabel}>Median Predicted Delay</Text>
            <Text style={S.medianValue}>{prediction.p50} min</Text>
          </View>

          <View style={S.gaugeContainer}>
            <View style={S.gaugeHeader}>
              <Text style={S.gaugeLabel}>p10 (Optimistic)</Text>
              <Text style={S.gaugeLabel}>p90 (Pessimistic)</Text>
            </View>
            <View style={S.gaugeTrack}>
              <View style={[S.gaugeRange, { left: '15%', width: '70%' }]} />
              <View style={[S.gaugeMarker, { left: '15%' }]} />
              <View style={[S.gaugeMedianMarker, { left: '50%' }]} />
              <View style={[S.gaugeMarker, { left: '85%' }]} />
            </View>
            <View style={S.gaugeValues}>
              <Text style={S.gaugeValue}>{prediction.p10} min</Text>
              <Text style={[S.gaugeValue, { color: COLORS.brand, fontWeight: 'bold' }]}>{prediction.p50} min</Text>
              <Text style={S.gaugeValue}>{prediction.p90} min</Text>
            </View>
          </View>

          <View style={S.insightBox}>
            <Ionicons name="information-circle-outline" size={16} color={COLORS.brand} style={{ marginRight: 6, marginTop: 1 }} />
            <Text style={S.insightText}>
              {prediction.interpretation} Range spans {prediction.interval_width} min.
            </Text>
          </View>
        </View>
      )}
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}
