import { useState, useEffect } from "react";
import { Vibration } from "react-native";
import * as Notifications from "expo-notifications";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export function useNotifications() {
  const [permissionGranted, setPermissionGranted] = useState(false);

  useEffect(() => {
    async function getPermission() {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      setPermissionGranted(finalStatus === 'granted');
    }
    getPermission().catch(() => {});
  }, []);

  const notifyDelay = async (route, stop, delayMinutes) => {
    if (!permissionGranted) return;
    
    Vibration.vibrate([0, 200, 200, 200]);
    await Notifications.scheduleNotificationAsync({
      content: {
        title: `⚠️ ${route} Delay Alert`,
        body: `Route ${route} at "${stop}" is delayed by ${delayMinutes.toFixed(1)} min.`,
        sound: true,
      },
      trigger: null,
    });
  };

  return { permissionGranted, notifyDelay };
}
