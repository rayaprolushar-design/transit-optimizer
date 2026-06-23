import React from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import RoutePlanner from './pages/RoutePlanner';
import DelayPredictor from './pages/DelayPredictor';
import Analytics from './pages/Analytics';
import LiveFeed from './pages/LiveFeed';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const { messages, status } = useWebSocket('/ws/live-feed');
  const location = useLocation();

  const getPageDetails = () => {
    switch (location.pathname) {
      case '/route-planner':
      case '/':
        return {
          title: 'Route Optimizer',
          description: 'Calculate fastest paths using Dijkstra or A* algorithms with multi-modal transfers.'
        };
      case '/delay-predictor':
        return {
          title: 'ML Delay Predictor',
          description: 'Predict exact arrival delays using our Gradient Boosting regression model.'
        };
      case '/analytics':
        return {
          title: 'System Analytics',
          description: 'Monitor transit network statistics, cache performance, and server metrics.'
        };
      case '/live-feed':
        return {
          title: 'Live Event Feed',
          description: 'Real-time monitoring of active delay prediction requests across the network.'
        };
      default:
        return { title: 'Transit Dashboard', description: '' };
    }
  };

  const { title, description } = getPageDetails();

  return (
    <div className="flex h-screen overflow-hidden bg-dark-900 text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar wsStatus={status} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header Bar */}
        <TopBar title={title} description={description} />

        {/* Content Viewport */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-gradient-to-br from-dark-900 to-dark-850">
          <Routes>
            <Route path="/" element={<Navigate to="/route-planner" replace />} />
            <Route path="/route-planner" element={<RoutePlanner />} />
            <Route path="/delay-predictor" element={<DelayPredictor />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/live-feed" element={<LiveFeed messages={messages} wsStatus={status} />} />
            <Route path="*" element={<Navigate to="/route-planner" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;
