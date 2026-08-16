/**
 * app/_layout.js
 * Root layout — sets up tab navigation with 4 tabs.
 * Expo Router automatically creates routes from files in app/.
 */
import { Tabs } from "expo-router"
import { Ionicons } from "@expo/vector-icons"
import { COLORS } from "../constants/config"

export default function Layout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle:      { backgroundColor: COLORS.surface },
        headerTintColor:  COLORS.text,
        headerTitleStyle: { fontWeight: "600" },
        tabBarStyle: {
          backgroundColor: COLORS.surface,
          borderTopColor:  COLORS.border,
        },
        tabBarActiveTintColor:   COLORS.brand,
        tabBarInactiveTintColor: COLORS.dim,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title:    "Route Planner",
          tabBarIcon: ({ color, size }) =>
            <Ionicons name="navigate" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="predict"
        options={{
          title:    "Delay",
          tabBarIcon: ({ color, size }) =>
            <Ionicons name="time" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="live"
        options={{
          title:    "Live Feed",
          tabBarIcon: ({ color, size }) =>
            <Ionicons name="radio" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="board"
        options={{
          title:    "Board",
          tabBarIcon: ({ color, size }) =>
            <Ionicons name="bus" size={size} color={color} />,
        }}
      />
    </Tabs>
  )
}
