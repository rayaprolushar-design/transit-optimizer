import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Navigation, Brain, Radio, Clock } from 'lucide-react-native';

import RoutePlannerScreen from './screens/RoutePlannerScreen';
import DelayPredictorScreen from './screens/DelayPredictorScreen';
import LiveFeedScreen from './screens/LiveFeedScreen';
import BoardScreen from './screens/BoardScreen';

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <SafeAreaProvider>
      <View style={styles.container}>
        <StatusBar style="light" />
        <NavigationContainer>
          <Tab.Navigator
            screenOptions={({ route }) => ({
              tabBarIcon: ({ color, size }) => {
                if (route.name === 'Route Planner') {
                  return <Navigation size={size} color={color} />;
                } else if (route.name === 'Delay Predictor') {
                  return <Brain size={size} color={color} />;
                } else if (route.name === 'Live Feed') {
                  return <Radio size={size} color={color} />;
                } else if (route.name === 'Board') {
                  return <Clock size={size} color={color} />;
                }
              },
              tabBarActiveTintColor: '#00E5FF',
              tabBarInactiveTintColor: '#94A3B8',
              tabBarStyle: {
                backgroundColor: '#1E293B',
                borderTopColor: '#334155',
                height: 60,
                paddingBottom: 8,
                paddingTop: 8,
              },
              headerStyle: {
                backgroundColor: '#1E293B',
                borderBottomColor: '#334155',
                borderBottomWidth: 1,
              },
              headerTintColor: '#F8FAFC',
              headerTitleStyle: {
                fontWeight: '700',
                fontSize: 16,
              },
            })}
          >
            <Tab.Screen name="Route Planner" component={RoutePlannerScreen} />
            <Tab.Screen name="Delay Predictor" component={DelayPredictorScreen} />
            <Tab.Screen name="Live Feed" component={LiveFeedScreen} />
            <Tab.Screen name="Board" component={BoardScreen} />
          </Tab.Navigator>
        </NavigationContainer>
      </View>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
});
