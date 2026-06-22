import React from 'react';
import { NavLink } from 'react-router-dom';
import { Navigation, Brain, BarChart2, Radio, Zap } from 'lucide-react';

function Sidebar({ wsStatus }) {
  const navItems = [
    { to: '/route-planner', label: 'Route Planner', icon: Navigation, desc: 'Find fastest paths' },
    { to: '/delay-predictor', label: 'ML Predictor', icon: Brain, desc: 'Predict arrival delays' },
    { to: '/analytics', label: 'Analytics', icon: BarChart2, desc: 'View server performance' },
    { to: '/live-feed', label: 'Live Event Feed', icon: Radio, desc: 'Real-time telemetry' },
  ];

  const getStatusColor = () => {
    switch (wsStatus) {
      case 'connected':
        return 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]';
      case 'connecting':
        return 'bg-amber-500 animate-pulse shadow-[0_0_10px_rgba(245,158,11,0.5)]';
      case 'disconnected':
      default:
        return 'bg-rose-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]';
    }
  };

  const getStatusText = () => {
    switch (wsStatus) {
      case 'connected':
        return 'Live System Connected';
      case 'connecting':
        return 'Connecting Telemetry...';
      case 'disconnected':
      default:
        return 'Telemetry Offline';
    }
  };

  return (
    <aside className="w-64 md:w-72 bg-dark-850 border-r border-dark-800 flex flex-col justify-between h-screen shrink-0 z-20">
      {/* Brand Header */}
      <div>
        <div className="p-6 border-b border-dark-800 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-primary to-brand-neonBlue flex items-center justify-center text-dark-900 font-bold shadow-neon-blue">
            <Zap className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-display font-bold text-lg leading-tight tracking-wider bg-gradient-to-r from-white via-slate-100 to-brand-neonBlue bg-clip-text text-transparent">
              TRANSIT
            </h1>
            <span className="text-xs text-slate-400 font-medium tracking-widest block uppercase">
              Optimizer v2.0
            </span>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-4 px-4 py-3.5 rounded-xl transition-all duration-200 group ${
                    isActive
                      ? 'bg-gradient-to-r from-brand-primary/10 to-brand-neonBlue/5 border border-brand-primary/20 text-brand-neonBlue shadow-[inset_0_1px_1px_rgba(255,255,255,0.05)]'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800/50 border border-transparent'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`w-5.5 h-5.5 shrink-0 transition-transform duration-200 group-hover:scale-105 ${
                        isActive ? 'text-brand-neonBlue' : 'text-slate-400 group-hover:text-slate-200'
                      }`}
                    />
                    <div className="flex flex-col">
                      <span className="font-semibold text-sm leading-none">{item.label}</span>
                      <span className="text-[10px] text-slate-500 font-medium mt-1 leading-none">
                        {item.desc}
                      </span>
                    </div>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Real-time Status Card */}
      <div className="p-4 border-t border-dark-800 bg-dark-900/30">
        <div className="flex items-center gap-3.5 px-4 py-3 rounded-xl border border-dark-800 bg-dark-850/50 glass-panel">
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${getStatusColor()}`} />
          <div className="flex flex-col overflow-hidden">
            <span className="text-xs font-semibold text-slate-300 truncate leading-none">
              {getStatusText()}
            </span>
            <span className="text-[9px] text-slate-500 font-medium mt-1">
              {wsStatus === 'connected' ? 'Streaming live logs' : 'Attempting auto-reconnect'}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
