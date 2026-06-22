import React from 'react';
import { AlertCircle, X } from 'lucide-react';

function ErrorBanner({ message, onDismiss }) {
  if (!message) return null;

  return (
    <div className="bg-rose-500/10 border border-rose-500/20 text-rose-200 p-4 rounded-xl flex items-start gap-3 shadow-lg fade-in-up">
      <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
      <div className="flex-1">
        <h4 className="font-semibold text-sm leading-tight text-rose-300">Application Alert</h4>
        <p className="text-xs text-rose-400/90 mt-1 font-medium leading-relaxed">{message}</p>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-rose-400 hover:text-rose-200 transition-colors p-0.5"
          aria-label="Dismiss error"
        >
          <X className="w-4.5 h-4.5" />
        </button>
      )}
    </div>
  );
}

export default ErrorBanner;
