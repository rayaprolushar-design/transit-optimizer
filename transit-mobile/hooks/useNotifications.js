/**
 * hooks/useNotifications.js
 * Requests push notification permission and sends local alerts
 * when a tracked bus delay exceeds 3 minutes.
 *
 * This is the killer feature for the Rapido/Zepto demo:
 * "My phone notified me that Route 5 is 4 minutes late
 *  before I even left the house."
 */
import { useState, useEffect, useRef } from "react"
import * as Notifications from "expo-notifications"

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge:  false,
  }),
})

export function useNotifications() {
  const [permissionGranted, setPermissionGranted] = useState(false)
  const notifiedRoutes = useRef(new Set())   // avoid duplicate alerts

  useEffect(() => {
    ;(async () => {
      const { status } = await Notifications.requestPermissionsAsync()
      setPermissionGranted(status === "granted")
    })()
  }, [])

  const notifyDelay = async (route, stop, delayMinutes) => {
    if (!permissionGranted) return
    const key = `${route}-${stop}`
    if (notifiedRoutes.current.has(key)) return
    notifiedRoutes.current.add(key)

    // Auto-clear after 5 minutes so alerts can fire again
    setTimeout(() => notifiedRoutes.current.delete(key), 5 * 60 * 1000)

    await Notifications.scheduleNotificationAsync({
      content: {
        title: `🚌 ${route} — Delayed ${delayMinutes} min`,
        body:  `Bus at ${stop} is running ${delayMinutes} minutes late.`,
        data:  { route, stop, delayMinutes },
      },
      trigger: null,   // fire immediately
    })
  }

  const notifyOnTime = async (route, stop) => {
    if (!permissionGranted) return
    await Notifications.scheduleNotificationAsync({
      content: {
        title: `✅ ${route} — On time`,
        body:  `Bus at ${stop} is running on schedule.`,
        data:  { route, stop },
      },
      trigger: null,
    })
  }

  return { permissionGranted, notifyDelay, notifyOnTime }
}
