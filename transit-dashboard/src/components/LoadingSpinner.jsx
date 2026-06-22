import React from 'react';
import { Loader2 } from 'lucide-react';

function LoadingSpinner({ message = 'Loading details...' }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center bg-dark-850/50 rounded-xl border border-dark-800/80 glass-panel min-h-[200px] fade-in-up">
      <div className="relative flex items-center justify-center">
        {/* Outer glowing pulsing ring */}
        <div className="absolute w-12 h-12 rounded-full border border-brand-primary/20 animate-ping" />
        {/* Main rotating loading spinner */}
        <Loader2 className="w-8 h-8 text-brand-neonBlue animate-spin" />
      </div>
      <p className="text-xs font-semibold text-slate-400 mt-4 tracking-wider uppercase">
        {message}
      </p>
    </div>
  );
}

export default LoadingSpinner;
