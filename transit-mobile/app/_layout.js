import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "../constants/config";

export default function Layout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: COLORS.brand,
        tabBarInactiveTintColor: COLORS.dim,
        tabBarStyle: {
          backgroundColor: COLORS.card,
          borderTopColor: COLORS.border,
          height: 60,
          paddingBottom: 8,
          paddingTop: 8,
        },
        headerStyle: {
          backgroundColor: COLORS.card,
          borderBottomColor: COLORS.border,
          borderBottomWidth: 0.5,
        },
        headerTintColor: COLORS.text,
        headerTitleStyle: {
          fontWeight: "700",
          fontSize: 16,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Route Planner",
          tabBarIcon: ({ color, size }) => <Ionicons name="navigate" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="predictor"
        options={{
          title: "ML Predictor",
          tabBarIcon: ({ color, size }) => <Ionicons name="speedometer" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="live"
        options={{
          title: "Live Feed",
          tabBarIcon: ({ color, size }) => <Ionicons name="pulse" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="board"
        options={{
          title: "Display Board",
          tabBarIcon: ({ color, size }) => <Ionicons name="time" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
