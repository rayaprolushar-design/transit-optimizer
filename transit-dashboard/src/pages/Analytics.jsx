import React, { useState, useEffect } from 'react';
import { getStats } from '../api/client';
import ErrorBanner from '../components/ErrorBanner';
import LoadingSpinner from '../components/LoadingSpinner';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { Activity, Server, Database, TrendingUp, RefreshCw } from 'lucide-react';

function Analytics() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchTelemetry = async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);
    
    setError(null);
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to retrieve telemetry stats');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    // Auto-update every 10 seconds
    const interval = setInterval(() => {
      fetchTelemetry(true);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <LoadingSpinner message="Querying system telemetry stats..." />;
  if (error) return <div className="max-w-2xl mx-auto"><ErrorBanner message={error} onDismiss={() => fetchTelemetry()} /></div>;

  // Process data for charts
  const graphData = [
    { name: 'Transit Lines', value: stats.graph.transit_edges, color: '#00E5FF' },
    { name: 'Walk Paths', value: stats.graph.walk_edges, color: '#A855F7' }
  ];

  const calculateHitRate = (cache) => {
    const total = cache.hits + cache.misses;
    return total > 0 ? parseFloat(((cache.hits / total) * 100).toFixed(1)) : 0;
  };

  const routeHitRate = calculateHitRate(stats.cache.route_cache);
  const predHitRate = calculateHitRate(stats.cache.prediction_cache);

  const cacheData = [
    {
      name: 'Route Cache',
      Hits: stats.cache.route_cache.hits,
      Misses: stats.cache.route_cache.misses,
      HitRate: routeHitRate
    },
    {
      name: 'Prediction Cache',
      Hits: stats.cache.prediction_cache.hits,
      Misses: stats.cache.prediction_cache.misses,
      HitRate: predHitRate
    }
  ];

  const formatUptime = (seconds) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hrs}h ${mins}m ${secs}s`;
  };

  return (
    <div className="space-y-6 md:space-y-8 max-w-[1600px] mx-auto fade-in-up">
      {/* Header Controls */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
            Telemetry Operations
          </h3>
        </div>
        <button
          onClick={() => fetchTelemetry(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-dark-850 hover:bg-dark-800 text-brand-neonBlue border border-dark-800 rounded-xl text-xs font-bold transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh Metrics'}
        </button>
      </div>

      {/* Numerical Stats overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Requests */}
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-brand-primary/10 flex items-center justify-center text-brand-primary shadow-inner">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Total Requests</span>
            <span className="text-2xl font-bold text-slate-100">{stats.server.requests_served}</span>
          </div>
        </div>

        {/* Uptime */}
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-brand-neonBlue/10 flex items-center justify-center text-brand-neonBlue shadow-inner">
            <Server className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Server Uptime</span>
            <span className="text-base font-bold text-slate-100 block mt-1">{formatUptime(stats.server.uptime_s)}</span>
          </div>
        </div>

        {/* Stops In Graph */}
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-brand-neonPurple/10 flex items-center justify-center text-brand-neonPurple shadow-inner">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Network Nodes</span>
            <span className="text-2xl font-bold text-slate-100">{stats.graph.stops} <span className="text-xs text-slate-500 font-medium">stops</span></span>
          </div>
        </div>

        {/* Cache Hit Average */}
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-brand-neonPink/10 flex items-center justify-center text-brand-neonPink shadow-inner">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Avg Cache Hit</span>
            <span className="text-2xl font-bold text-slate-100">
              {stats.cache.route_cache.hits + stats.cache.prediction_cache.hits > 0
                ? `${(( (stats.cache.route_cache.hits + stats.cache.prediction_cache.hits) / 
                        (stats.cache.route_cache.hits + stats.cache.route_cache.misses + stats.cache.prediction_cache.hits + stats.cache.prediction_cache.misses)
                     ) * 100).toFixed(1)}%`
                : '0.0%'
              }
            </span>
          </div>
        </div>
      </div>

      {/* Visual Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 md:gap-8">
        {/* Graph Edges distribution */}
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel space-y-4">
          <h4 className="font-display font-bold text-slate-200 text-sm flex items-center gap-2">
            <Database className="w-4 h-4 text-brand-neonBlue" />
            Network Edges Distribution
          </h4>
          <div className="h-[250px] flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={graphData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={85}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {graphData.map((entry, idx) => (
                    <Cell key={`cell-${idx}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#151D30', borderColor: '#1E293B', borderRadius: '12px' }}
                  itemStyle={{ color: '#F8FAFC' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          {/* Legend indicators */}
          <div className="flex justify-center gap-6 text-xs font-semibold">
            {graphData.map((entry, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
                <span className="text-slate-400">{entry.name}:</span>
                <span className="text-slate-200">{entry.value.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Cache performance chart */}
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel space-y-4">
          <h4 className="font-display font-bold text-slate-200 text-sm flex items-center gap-2">
            <Database className="w-4 h-4 text-brand-neonPurple" />
            Cache Read Operations (Hits vs Misses)
          </h4>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={cacheData}
                margin={{ top: 20, right: 10, left: -10, bottom: 5 }}
              >
                <XAxis dataKey="name" stroke="#475569" fontSize={11} fontWeight={600} tickLine={false} />
                <YAxis stroke="#475569" fontSize={11} fontWeight={600} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#151D30', borderColor: '#1E293B', borderRadius: '12px' }}
                  itemStyle={{ color: '#F8FAFC' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', fontWeight: 600, paddingTop: '10px' }} />
                <Bar dataKey="Hits" fill="#00E5FF" radius={[6, 6, 0, 0]} barSize={35} />
                <Bar dataKey="Misses" fill="#EC4899" radius={[6, 6, 0, 0]} barSize={35} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Cache Status Details list */}
      <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel space-y-4">
        <h4 className="font-display font-bold text-slate-200 text-sm flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-brand-neonPink" />
          LRU Cache Metadata
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Route cache info */}
          <div className="bg-dark-900/40 border border-dark-800 p-5 rounded-2xl space-y-3">
            <div className="flex justify-between items-center">
              <span className="font-semibold text-slate-200 text-sm">Pathfinding Cache</span>
              <span className="text-[10px] font-bold text-brand-neonBlue bg-brand-neonBlue/10 border border-brand-neonBlue/20 px-2 py-0.5 rounded">
                HIT RATE: {routeHitRate}%
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="bg-dark-850 p-2.5 rounded-xl border border-dark-800/60">
                <span className="text-[10px] text-slate-500 block">SIZE</span>
                <span className="text-slate-200 font-bold">{stats.cache.route_cache.size}</span>
              </div>
              <div className="bg-dark-850 p-2.5 rounded-xl border border-dark-800/60">
                <span className="text-[10px] text-slate-500 block">CAPACITY</span>
                <span className="text-slate-200 font-bold">{stats.cache.route_cache.capacity || 512}</span>
              </div>
              <div className="bg-dark-850 p-2.5 rounded-xl border border-dark-800/60">
                <span className="text-[10px] text-slate-500 block">QUERIES</span>
                <span className="text-slate-200 font-bold">{stats.cache.route_cache.hits + stats.cache.route_cache.misses}</span>
              </div>
            </div>
          </div>

          {/* Prediction cache info */}
          <div className="bg-dark-900/40 border border-dark-800 p-5 rounded-2xl space-y-3">
            <div className="flex justify-between items-center">
              <span className="font-semibold text-slate-200 text-sm">Delay Prediction Cache</span>
              <span className="text-[10px] font-bold text-brand-neonPurple bg-brand-neonPurple/10 border border-brand-neonPurple/20 px-2 py-0.5 rounded">
                HIT RATE: {predHitRate}%
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="bg-dark-850 p-2.5 rounded-xl border border-dark-800/60">
                <span className="text-[10px] text-slate-500 block">SIZE</span>
                <span className="text-slate-200 font-bold">{stats.cache.prediction_cache.size}</span>
              </div>
              <div className="bg-dark-850 p-2.5 rounded-xl border border-dark-800/60">
                <span className="text-[10px] text-slate-500 block">CAPACITY</span>
                <span className="text-slate-200 font-bold">{stats.cache.prediction_cache.capacity || 256}</span>
              </div>
              <div className="bg-dark-850 p-2.5 rounded-xl border border-dark-800/60">
                <span className="text-[10px] text-slate-500 block">QUERIES</span>
                <span className="text-slate-200 font-bold">{stats.cache.prediction_cache.hits + stats.cache.prediction_cache.misses}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Analytics;
