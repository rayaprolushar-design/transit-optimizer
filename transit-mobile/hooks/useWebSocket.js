import { useState, useEffect, useRef } from "react";
import { WS_URL } from "../constants/config";

export function useWebSocket() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      
      const ws = new WebSocket(WS_URL);
      socketRef.current = ws;

      ws.onopen = () => {
        if (active) setConnected(true);
      };

      ws.onmessage = (e) => {
        if (!active) return;
        try {
          const data = JSON.parse(e.data);
          
          // Inject a unique ID if missing
          const eventItem = {
            id: Math.random().toString(36).substring(2, 9),
            ...data,
          };
          
          setEvents((prev) => [eventItem, ...prev].slice(0, 50));
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      ws.onclose = () => {
        if (active) {
          setConnected(false);
          // Auto-reconnect after 5 seconds
          setTimeout(connect, 5000);
        }
      };

      ws.onerror = () => {
        if (active) setConnected(false);
      };
    }

    connect();

    return () => {
      active = false;
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  return { events, connected };
}
