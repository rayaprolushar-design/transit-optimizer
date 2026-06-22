import React from 'react';
import { Calendar, Cpu } from 'lucide-react';

function TopBar({ title, description }) {
  const formattedDate = new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });

  return (
    <header className="h-20 bg-dark-850/80 backdrop-blur-md border-b border-dark-800 px-6 md:px-8 flex items-center justify-between shrink-0 z-10">
      <div className="flex flex-col">
        <h2 className="font-display font-bold text-xl md:text-2xl text-slate-100 tracking-tight">
          {title}
        </h2>
        {description && (
          <p className="text-xs text-slate-400 font-medium mt-0.5 hidden sm:block">
            {description}
          </p>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Date Display */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-dark-800 bg-dark-900/30 text-xs text-slate-300 font-semibold">
          <Calendar className="w-3.5 h-3.5 text-brand-neonBlue" />
          <span>{formattedDate}</span>
        </div>

        {/* Server Environment */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-dark-800 bg-dark-900/30 text-xs text-slate-300 font-semibold">
          <Cpu className="w-3.5 h-3.5 text-brand-neonPurple animate-pulse" />
          <span>API Status: Online</span>
        </div>
      </div>
    </header>
  );
}

export default TopBar;
