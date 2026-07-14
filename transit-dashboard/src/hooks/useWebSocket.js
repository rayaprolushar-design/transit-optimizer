import { useState, useEffect, useRef, useCallback } from 'react';

export const useWebSocket = (urlPath = '/ws') => {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState('connecting'); // 'connecting' | 'connected' | 'disconnected'
  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(1000); // Start with 1s delay

  const connect = useCallback(() => {
    let wsUrl = import.meta.env.VITE_WS_URL;
    if (wsUrl) {
      if (!wsUrl.includes('/ws/')) {
        const base = wsUrl.replace(/\/$/, '');
        wsUrl = `${base}${urlPath}`;
      }
    } else {
      if (import.meta.env.DEV) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        wsUrl = `${protocol}//${host}${urlPath}`;
      } else {
        wsUrl = `wss://transit-optimizer-production-cea3.up.railway.app${urlPath}`;
      }
    }

    setStatus('connecting');
    
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setStatus('connected');
      reconnectDelayRef.current = 1000; // Reset reconnection delay
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Keep last 100 updates
        setMessages((prev) => [data, ...prev].slice(0, 100));
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
      }
    };

    socket.onclose = () => {
      setStatus('disconnected');
      
      // Exponential backoff
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(delay * 2, 30000); // Cap at 30 seconds
      
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      // Let onclose handle reconnection
    };
  }, [urlPath]);

  useEffect(() => {
    connect();

    return () => {
      if (socketRef.current) {
        socketRef.current.onclose = null; // Prevent reconnect on cleanup
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  const send = useCallback((msg) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { messages, status, send };
};
export default useWebSocket;
