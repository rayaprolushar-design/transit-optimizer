import React, { useState, useEffect, useRef } from 'react';
import { MapPin, X } from 'lucide-react';

function StopSearch({ stops = [], selectedStop, value, onChange, placeholder = 'Search stops...', label, id, icon }) {
  const initialValue = value !== undefined ? value : (selectedStop !== undefined ? selectedStop : '');
  const initialString = typeof initialValue === 'object' && initialValue !== null ? initialValue.name : initialValue;

  const [query, setQuery] = useState(initialString || '');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    const val = value !== undefined ? value : (selectedStop !== undefined ? selectedStop : '');
    setQuery(typeof val === 'object' && val !== null ? val.name : val || '');
  }, [value, selectedStop]);

  // Autocomplete matching (fuzzy search: match by name or ID)
  const filteredStops = query.trim() === ''
    ? stops.slice(0, 10) // Show first 10 stops by default
    : stops.filter(stop =>
        stop.name.toLowerCase().includes(query.toLowerCase()) ||
        stop.stop_id.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 15); // Show top 15 results

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
        const val = value !== undefined ? value : (selectedStop !== undefined ? selectedStop : '');
        setQuery(typeof val === 'object' && val !== null ? val.name : val || '');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [value, selectedStop]);

  const handleSelect = (stop) => {
    // Determine whether the parent component expects a string (name) or the full stop object.
    // If value is provided (as in RoutePlanner.jsx), we pass stop.name (string).
    // If selectedStop is provided (as in DelayPredictor.jsx), we pass the stop object.
    if (value !== undefined) {
      onChange?.(stop.name);
    } else {
      onChange?.(stop);
    }
    setQuery(stop.name);
    setIsOpen(false);
  };

  const handleClear = () => {
    if (value !== undefined) {
      onChange?.('');
    } else {
      onChange?.(null);
    }
    setQuery('');
    setIsOpen(true);
  };

  return (
    <div className="flex flex-col relative w-full" ref={containerRef}>
      {label && (
        <label htmlFor={id} className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
          {label}
        </label>
      )}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
          <MapPin className="w-4 h-4 text-brand-primary" />
        </div>
        <input
          id={id}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          placeholder={placeholder}
          className="w-full bg-dark-900 border border-dark-800 rounded-xl py-3 pl-10 pr-10 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-primary/50 focus:ring-1 focus:ring-brand-primary/50 transition-all duration-200 shadow-[inset_0_1px_2px_rgba(0,0,0,0.2)]"
        />
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X className="w-4.5 h-4.5" />
          </button>
        )}
      </div>

      {isOpen && filteredStops.length > 0 && (
        <ul className="absolute z-50 w-full mt-1.5 bg-dark-850 border border-dark-800 rounded-xl shadow-lg max-h-60 overflow-y-auto glass-panel py-1">
          {filteredStops.map((stop) => (
            <li
              key={stop.stop_id}
              onClick={() => handleSelect(stop)}
              className="px-4 py-2.5 hover:bg-dark-800/80 cursor-pointer flex flex-col transition-colors border-b border-dark-800/30 last:border-0"
            >
              <span className="text-sm font-semibold text-slate-200">{stop.name}</span>
              <span className="text-[10px] text-slate-500 font-semibold mt-0.5 uppercase tracking-wider">
                {stop.stop_id} &bull; Lat: {parseFloat(stop.lat).toFixed(4)}, Lon: {parseFloat(stop.lon).toFixed(4)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {isOpen && query.trim() !== '' && filteredStops.length === 0 && (
        <div className="absolute z-50 w-full mt-1.5 bg-dark-850 border border-dark-800 rounded-xl shadow-lg p-4 text-center text-xs text-slate-500 font-medium glass-panel">
          No stops matching "{query}"
        </div>
      )}
    </div>
  );
}

export default StopSearch;
