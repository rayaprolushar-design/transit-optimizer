import React, { useState, useEffect } from 'react';
import { useStops } from '../hooks/useStops';
import { useRoute } from '../hooks/useRoute';
import StopSearch from '../components/StopSearch';
import ErrorBanner from '../components/ErrorBanner';
import LoadingSpinner from '../components/LoadingSpinner';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Navigation, Compass, Map, Clock, RefreshCw, Cpu, Award } from 'lucide-react';

// Custom Map Fit Bounds component
function MapFocus({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points && points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [points, map]);
  return null;
}

// Custom DivIcons for styling
const originIcon = L.divIcon({
  html: `<div class="flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500 border-2 border-white shadow-[0_0_10px_rgba(16,185,129,0.6)]">
           <div class="w-2.5 h-2.5 bg-white rounded-full"></div>
         </div>`,
  className: 'custom-leaflet-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12]
});

const destIcon = L.divIcon({
  html: `<div class="flex items-center justify-center w-6 h-6 rounded-full bg-rose-500 border-2 border-white shadow-[0_0_10px_rgba(244,63,94,0.6)]">
           <div class="w-2.5 h-2.5 bg-white rounded-full"></div>
         </div>`,
  className: 'custom-leaflet-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12]
});

const stopIcon = L.divIcon({
  html: `<div class="flex items-center justify-center w-4 h-4 rounded-full bg-blue-500 border border-white shadow-[0_0_5px_rgba(59,130,246,0.5)]">
           <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
         </div>`,
  className: 'custom-leaflet-icon',
  iconSize: [16, 16],
  iconAnchor: [8, 8]
});

function RoutePlanner() {
  const { stops, loading: stopsLoading, error: stopsError } = useStops();
  const { route, loading: routeLoading, error: routeError, calculateRoute, clearRoute } = useRoute();

  const [fromStop, setFromStop] = useState(null);
  const [toStop, setToStop] = useState(null);
  const [algorithm, setAlgorithm] = useState('astar');
  const [transfers, setTransfers] = useState(true);

  // Map of stop ID -> stop details
  const stopMap = React.useMemo(() => {
    const map = {};
    stops.forEach(s => {
      map[s.stop_id] = s;
      map[s.name] = s;
    });
    return map;
  }, [stops]);

  // Coordinates of sequential stops along the calculated path
  const pathCoordinates = React.useMemo(() => {
    if (!route) return [];
    
    // Attempt using the explicit path stop IDs if provided by modified backend
    if (route.path && route.path.length > 0) {
      return route.path
        .map(id => {
          const s = stopMap[id];
          return s ? [s.lat, s.lon] : null;
        })
        .filter(Boolean);
    }
    
    // Fallback: build from direction segments
    const coords = [];
    route.directions.forEach(d => {
      const fromS = stopMap[d.from];
      const toS = stopMap[d.to];
      if (fromS) coords.push([fromS.lat, fromS.lon]);
      if (toS) coords.push([toS.lat, toS.lon]);
    });
    return coords;
  }, [route, stopMap]);

  // Unique list of stops on the path (excluding origin & destination duplicates) for markers
  const pathStopMarkers = React.useMemo(() => {
    if (!route || !route.path) return [];
    if (route.path.length <= 2) return [];
    
    // Return intermediate stops
    return route.path.slice(1, -1).map(id => stopMap[id]).filter(Boolean);
  }, [route, stopMap]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!fromStop || !toStop) return;
    calculateRoute(fromStop.name, toStop.name, algorithm, transfers);
  };

  const handleSwap = () => {
    const temp = fromStop;
    setFromStop(toStop);
    setToStop(temp);
    clearRoute();
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 md:gap-8 h-full max-w-[1600px] mx-auto fade-in-up">
      {/* Search Controls Panel */}
      <div className="xl:col-span-5 flex flex-col gap-6 overflow-y-auto max-h-[85vh] pr-2">
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel">
          <h3 className="font-display font-bold text-lg text-slate-100 mb-5 flex items-center gap-2">
            <Compass className="w-5 h-5 text-brand-neonBlue" />
            Route Settings
          </h3>

          {stopsError && <div className="mb-4"><ErrorBanner message={stopsError} /></div>}
          {routeError && <div className="mb-4"><ErrorBanner message={routeError} /></div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-3">
              <StopSearch
                id="origin-stop"
                stops={stops}
                selectedStop={fromStop}
                onChange={setFromStop}
                placeholder="Type to search origin..."
                label="Origin Stop"
              />

              {/* Swap Button */}
              <div className="flex justify-center -my-2">
                <button
                  type="button"
                  onClick={handleSwap}
                  className="bg-dark-800 hover:bg-dark-700 text-brand-neonBlue border border-dark-700/60 p-2 rounded-xl transition-all duration-200 shadow-md hover:scale-105 active:scale-95"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>

              <StopSearch
                id="destination-stop"
                stops={stops}
                selectedStop={toStop}
                onChange={setToStop}
                placeholder="Type to search destination..."
                label="Destination Stop"
              />
            </div>

            {/* Path Options */}
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div>
                <label className="text-[10px] font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Algorithm
                </label>
                <div className="flex bg-dark-900 p-1 rounded-xl border border-dark-800">
                  <button
                    type="button"
                    onClick={() => setAlgorithm('astar')}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                      algorithm === 'astar'
                        ? 'bg-brand-primary text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    A* Search
                  </button>
                  <button
                    type="button"
                    onClick={() => setAlgorithm('dijkstra')}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                      algorithm === 'dijkstra'
                        ? 'bg-brand-primary text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Dijkstra
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[10px] font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Transfers
                </label>
                <button
                  type="button"
                  onClick={() => setTransfers(prev => !prev)}
                  className={`w-full py-2.5 text-xs font-semibold rounded-xl border transition-all ${
                    transfers
                      ? 'bg-gradient-to-r from-emerald-500/10 to-emerald-400/5 border-emerald-500/20 text-emerald-400'
                      : 'bg-dark-900 border-dark-800 text-slate-400 hover:text-slate-300'
                  }`}
                >
                  {transfers ? 'Multi-Modal: ON' : 'Direct Routes Only'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={stopsLoading || routeLoading || !fromStop || !toStop}
              className="w-full bg-gradient-to-r from-brand-primary to-brand-neonBlue text-slate-900 font-bold py-3.5 rounded-xl transition-all duration-300 shadow-neon-blue hover:brightness-110 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none text-sm flex items-center justify-center gap-2"
            >
              <Navigation className="w-4.5 h-4.5 fill-current" />
              Calculate Route
            </button>
          </form>
        </div>

        {/* Route Loading state */}
        {routeLoading && <LoadingSpinner message="Optimizing shortest route..." />}

        {/* Route Results details */}
        {route && !routeLoading && (
          <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel space-y-5 fade-in-up">
            <h4 className="font-display font-bold text-slate-100 flex items-center gap-2 text-base">
              <Map className="w-5 h-5 text-brand-neonBlue" />
              Route Telemetry
            </h4>

            {/* Summary stat cards */}
            <div className="grid grid-cols-2 gap-3.5">
              <div className="bg-dark-900/60 border border-dark-800/80 rounded-xl p-3.5 flex items-center gap-3">
                <Clock className="w-8 h-8 text-brand-neonBlue shrink-0" />
                <div>
                  <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider block">Est. Time</span>
                  <span className="text-lg font-bold text-slate-100">{route.total_minutes} <span className="text-xs font-semibold">min</span></span>
                </div>
              </div>

              <div className="bg-dark-900/60 border border-dark-800/80 rounded-xl p-3.5 flex items-center gap-3">
                <Cpu className="w-8 h-8 text-brand-neonPurple shrink-0" />
                <div>
                  <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider block">Compute</span>
                  <span className="text-lg font-bold text-slate-100">{route.elapsed_ms.toFixed(2)} <span className="text-xs font-semibold">ms</span></span>
                </div>
              </div>
            </div>

            <div className="border-t border-dark-800/60 pt-4 space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-400">Pathfinding Algorithm</span>
                <span className="text-slate-200 font-bold">{route.algorithm}</span>
              </div>
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-400">Graph Nodes Visited</span>
                <span className="text-slate-200 font-bold">{route.nodes_visited}</span>
              </div>
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-400">Total Route Transfers</span>
                <span className="text-slate-200 font-bold">{route.transfers}</span>
              </div>
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-400">Response Cache State</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  route.cached 
                    ? 'bg-brand-neonBlue/10 text-brand-neonBlue border border-brand-neonBlue/20' 
                    : 'bg-slate-800 text-slate-400 border border-dark-700'
                }`}>
                  {route.cached ? 'CACHE HIT' : 'API QUERY'}
                </span>
              </div>
            </div>

            {/* Directions sequence */}
            <div className="border-t border-dark-800/60 pt-4">
              <h5 className="text-xs font-semibold text-slate-400 mb-3.5 uppercase tracking-wider">
                Travel Directions
              </h5>
              <div className="space-y-4">
                {route.directions.map((dir, idx) => (
                  <div key={idx} className="relative flex gap-3.5 group">
                    {/* Stepper Line */}
                    {idx < route.directions.length - 1 && (
                      <div className="absolute top-6 bottom-[-20px] left-[15px] w-0.5 bg-dark-800" />
                    )}

                    {/* Step Icon */}
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-sm border ${
                      dir.type === 'walk'
                        ? 'bg-dark-900 border-dark-800 text-slate-400'
                        : 'bg-brand-primary/10 border-brand-primary/20 text-brand-neonBlue'
                    }`}>
                      {dir.type === 'walk' ? (
                        <Award className="w-4 h-4" />
                      ) : (
                        <Compass className="w-4 h-4" />
                      )}
                    </div>

                    {/* Step Instructions */}
                    <div className="flex-1">
                      <div className="flex justify-between items-baseline gap-2">
                        <span className="text-xs font-bold text-slate-200">
                          {dir.type === 'walk' ? 'Walk to next stop' : `Board Transit (${dir.route})`}
                        </span>
                        <span className="text-xs text-slate-400 font-semibold shrink-0">
                          {dir.minutes} mins
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        From <span className="font-semibold text-slate-300">{dir.from}</span> to <span className="font-semibold text-slate-300">{dir.to}</span>
                      </p>
                      {dir.type === 'walk' && dir.dist_km > 0 && (
                        <span className="text-[10px] text-slate-500 font-medium mt-0.5 block">
                          Distance: {dir.dist_km.toFixed(2)} km
                        </span>
                      )}
                      {dir.type === 'transit' && dir.stops > 0 && (
                        <span className="text-[10px] text-slate-500 font-medium mt-0.5 block">
                          Ride through {dir.stops} {dir.stops === 1 ? 'stop' : 'stops'}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Map Panel */}
      <div className="xl:col-span-7 h-[50vh] xl:h-[80vh] bg-dark-850 rounded-2xl border border-dark-800 shadow-glass overflow-hidden relative">
        <MapContainer
          center={[12.9716, 77.5946]} // Default Bangalore center coordinate
          zoom={12}
          scrollWheelZoom={true}
          className="h-full w-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* Render Route Polyline */}
          {pathCoordinates.length > 0 && (
            <Polyline
              positions={pathCoordinates}
              pathOptions={{
                color: '#3B82F6',
                weight: 4,
                opacity: 0.8,
                dashArray: 'none',
                shadowColor: 'rgba(59,130,246,0.5)',
                shadowBlur: 10
              }}
            />
          )}

          {/* Render Start Marker */}
          {fromStop && (
            <Marker position={[fromStop.lat, fromStop.lon]} icon={originIcon}>
              <Popup>
                <div className="text-xs">
                  <p className="font-bold text-emerald-500">Origin Stop</p>
                  <p className="font-semibold text-slate-900 mt-0.5">{fromStop.name}</p>
                </div>
              </Popup>
            </Marker>
          )}

          {/* Render End Marker */}
          {toStop && (
            <Marker position={[toStop.lat, toStop.lon]} icon={destIcon}>
              <Popup>
                <div className="text-xs">
                  <p className="font-bold text-rose-500">Destination Stop</p>
                  <p className="font-semibold text-slate-900 mt-0.5">{toStop.name}</p>
                </div>
              </Popup>
            </Marker>
          )}

          {/* Render Intermediate Stops along the path */}
          {pathStopMarkers.map((stop, idx) => (
            <Marker key={idx} position={[stop.lat, stop.lon]} icon={stopIcon}>
              <Popup>
                <div className="text-xs text-slate-950">
                  <p className="font-bold text-brand-primary">{stop.stop_id}</p>
                  <p className="font-semibold mt-0.5">{stop.name}</p>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Automatically adjust zoom bounds */}
          {pathCoordinates.length > 0 && <MapFocus points={pathCoordinates} />}
        </MapContainer>

        {/* Empty placeholder text on map cover if no route is loaded */}
        {!route && (
          <div className="absolute inset-0 bg-dark-900/60 backdrop-blur-[2px] flex items-center justify-center p-6 text-center pointer-events-none">
            <div className="bg-dark-850 border border-dark-800 p-6 rounded-2xl max-w-sm glass-panel shadow-2xl">
              <Compass className="w-10 h-10 text-brand-neonBlue mx-auto mb-3 animate-pulse" />
              <h4 className="font-display font-bold text-slate-200">Interactive Map View</h4>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Select your origin and destination stops in the settings panel to calculate and view your path routing.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default RoutePlanner;
