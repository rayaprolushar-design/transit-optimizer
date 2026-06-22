import React from 'react';
import { Radio, ShieldAlert, Clock, RefreshCw, Sparkles, TrendingUp } from 'lucide-react';

function LiveFeed({ messages, wsStatus }) {
  // Compute session telemetry from the stream
  const stats = React.useMemo(() => {
    if (messages.length === 0) return { count: 0, avgDelay: 0, hitRate: 0 };
    
    const count = messages.length;
    const totalDelay = messages.reduce((acc, m) => acc + m.predicted_delay, 0);
    const cachedCount = messages.filter(m => m.cached).length;

    return {
      count,
      avgDelay: parseFloat((totalDelay / count).toFixed(2)),
      hitRate: parseFloat(((cachedCount / count) * 100).toFixed(1))
    };
  }, [messages]);

  const getStatusBanner = () => {
    switch (wsStatus) {
      case 'connected':
        return 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';
      case 'connecting':
        return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
      case 'disconnected':
      default:
        return 'bg-rose-500/10 border-rose-500/20 text-rose-400';
    }
  };

  const getConfidenceBadge = (confidence) => {
    switch (confidence) {
      case 'high':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      case 'medium':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      case 'low':
      default:
        return 'bg-rose-500/10 text-rose-400 border border-rose-500/20';
    }
  };

  return (
    <div className="space-y-6 md:space-y-8 max-w-[1200px] mx-auto fade-in-up">
      {/* Websocket State Banner */}
      <div className={`p-4 rounded-xl border flex items-center justify-between shadow-sm ${getStatusBanner()}`}>
        <div className="flex items-center gap-3">
          <div className="relative">
            {wsStatus === 'connected' && (
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
            )}
            <Radio className={`w-5 h-5 ${wsStatus === 'connected' ? 'text-emerald-400' : 'text-slate-400'}`} />
          </div>
          <div className="text-xs">
            <span className="font-bold uppercase tracking-wider block">
              WebSocket Telemetry Status: {wsStatus.toUpperCase()}
            </span>
            <span className="text-[10px] opacity-80 mt-0.5 block font-medium">
              {wsStatus === 'connected' 
                ? 'Telemetry channel listening. Real-time predictions broadcast immediately.'
                : 'Attempting connection backoff loop...'
              }
            </span>
          </div>
        </div>
      </div>

      {/* Stream Metrics cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Session Events</span>
            <span className="text-2xl font-bold text-slate-200 mt-1 block">{stats.count}</span>
          </div>
          <Sparkles className="w-8 h-8 text-brand-neonBlue opacity-60" />
        </div>

        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Average Delay</span>
            <span className="text-2xl font-bold text-slate-200 mt-1 block">{stats.avgDelay} <span className="text-xs text-slate-400 font-medium">min</span></span>
          </div>
          <Clock className="w-8 h-8 text-brand-neonPurple opacity-60" />
        </div>

        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Session Cache Rate</span>
            <span className="text-2xl font-bold text-slate-200 mt-1 block">{stats.hitRate}%</span>
          </div>
          <TrendingUp className="w-8 h-8 text-brand-neonPink opacity-60" />
        </div>
      </div>

      {/* Live Event Stream Logs */}
      <div className="space-y-4">
        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
          Event Log Stream
        </h4>

        {messages.length === 0 ? (
          <div className="bg-dark-850 border border-dark-800 rounded-2xl p-10 text-center glass-panel flex flex-col items-center justify-center space-y-4 min-h-[300px]">
            <div className="relative">
              <div className="absolute inset-0 bg-brand-primary/10 rounded-full blur-xl animate-pulse" />
              <RefreshCw className="w-10 h-10 text-brand-primary animate-spin" style={{ animationDuration: '4s' }} />
            </div>
            <div>
              <h5 className="font-display font-bold text-slate-200">Awaiting Telemetry Feed</h5>
              <p className="text-xs text-slate-400 max-w-sm mx-auto mt-2 leading-relaxed font-medium">
                Keep this browser window active and run delay predictions in the <strong className="text-brand-neonPurple">ML Predictor</strong> tab. Predictions will route to the websocket pipeline and display here instantly.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3.5">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className="bg-dark-850 border border-dark-800 hover:border-dark-700/60 p-4 rounded-xl flex items-center justify-between gap-4 glass-panel transition-all hover:scale-[1.005] duration-200 shadow-sm fade-in-up relative overflow-hidden"
              >
                {/* Visual pulse for the newest event */}
                {idx === 0 && (
                  <div className="absolute inset-y-0 left-0 w-1 bg-brand-neonBlue shadow-[0_0_10px_#00E5FF]" />
                )}

                <div className="flex items-center gap-4 min-w-0">
                  {/* Timestamp & Type badge */}
                  <div className="text-center shrink-0">
                    <span className="text-[10px] text-slate-500 font-bold block">{msg.timestamp}</span>
                    <span className={`px-2 py-0.5 rounded text-[8px] font-bold mt-1.5 block tracking-wider ${
                      msg.route_type === 'Metro' 
                        ? 'bg-brand-neonBlue/10 text-brand-neonBlue border border-brand-neonBlue/20' 
                        : 'bg-brand-neonPurple/10 text-brand-neonPurple border border-brand-neonPurple/20'
                    }`}>
                      {msg.route_type.toUpperCase()}
                    </span>
                  </div>

                  {/* Stop Information */}
                  <div className="min-w-0">
                    <h5 className="font-bold text-slate-200 text-sm truncate">{msg.stop_name}</h5>
                    <p className="text-[10px] text-slate-500 font-semibold mt-0.5 uppercase tracking-wide">
                      ID: {msg.stop_id} &bull; Hour: {msg.hour}:00 &bull; {msg.is_weekend ? 'Weekend' : 'Weekday'}
                    </p>
                  </div>
                </div>

                {/* Delay & details */}
                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right">
                    <span className="text-xl font-display font-extrabold text-white block">
                      +{msg.predicted_delay.toFixed(1)} <span className="text-[10px] font-medium text-slate-400">min</span>
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-semibold mt-1 inline-block uppercase tracking-wider ${
                      msg.cached 
                        ? 'bg-slate-800 text-slate-400 border border-dark-700' 
                        : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    }`}>
                      {msg.cached ? 'CACHED' : 'EVALUATED'}
                    </span>
                  </div>

                  <span className={`px-2.5 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider shrink-0 ${getConfidenceBadge(msg.confidence)}`}>
                    {msg.confidence}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default LiveFeed;
