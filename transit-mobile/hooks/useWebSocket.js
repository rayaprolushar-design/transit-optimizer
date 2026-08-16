/**
 * hooks/useWebSocket.js
 * Connects to the FastAPI WebSocket live feed.
 * Auto-reconnects with exponential backoff.
 * Identical logic to the web dashboard version.
 */
import { useState, useEffect, useRef, useCallback } from "react"
import { WS_URL } from "../constants/config"

export function useWebSocket() {
  const [events,    setEvents]    = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef    = useRef(null)
  const retryRef = useRef(0)
  const timerRef = useRef(null)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        retryRef.current = 0
      }

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          setEvents(prev => [
            { ...event, id: Date.now() + Math.random() },
            ...prev.slice(0, 19),
          ])
        } catch (_) {}
      }

      ws.onclose = () => {
        setConnected(false)
        if (retryRef.current < 6) {
          const delay = Math.min(1000 * 2 ** retryRef.current, 30000)
          retryRef.current++
          timerRef.current = setTimeout(connect, delay)
        }
      }

      ws.onerror = () => ws.close()
    } catch (_) {
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { events, connected }
}
