/**
 * TransitMap.jsx — Week 19
 * Leaflet map showing all stops as clickable markers.
 * When a route result exists, draws the path as a green polyline.
 *
 * Props:
 *   stops        — array of {stop_id, name, lat, lon}
 *   route        — result from useRoute() (can be null)
 *   onStopClick  — called with stop.name when user clicks a marker
 *   fromStop     — currently selected origin stop name (highlighted blue)
 *   toStop       — currently selected destination stop name (highlighted green)
 *
 * React-Leaflet concepts used:
 *   MapContainer   — creates the Leaflet map instance
 *   TileLayer      — loads OpenStreetMap tiles
 *   CircleMarker   — lightweight stop dot (no custom icon needed)
 *   Polyline       — draws the route path
 *   Tooltip        — hover label on each stop
 *   Popup          — click-to-select on each stop
 *   useMap         — imperative access to the Leaflet map instance
 */
import { useEffect } from 'react'
import {
  MapContainer, TileLayer, CircleMarker,
  Polyline, Tooltip, Popup, useMap,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

// ── Tile layer ────────────────────────────────────────────────────────────────
// CartoDB dark matter tiles — dark aesthetic, no API key needed.
const TILE_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const TILE_ATT = '© <a href="https://www.openstreetmap.org/copyright">OSM</a> © <a href="https://carto.com">CARTO</a>'

// ── Bengaluru city centre ─────────────────────────────────────────────────────
const BENGALURU_CENTER = [12.9716, 77.5946]
const DEFAULT_ZOOM     = 12

// ── Marker styles ─────────────────────────────────────────────────────────────
const markerStyle = (isFrom, isTo, isOnRoute) => ({
  radius:      isFrom || isTo ? 9 : isOnRoute ? 7 : 5,
  fillColor:   isFrom  ? '#378ADD'
             : isTo    ? '#1D9E75'
             : isOnRoute ? '#EF9F27'
             : '#4B5563',
  color:       isFrom || isTo || isOnRoute ? '#fff' : '#374151',
  weight:      isFrom || isTo ? 2 : 1,
  opacity:     1,
  fillOpacity: isFrom || isTo ? 1 : isOnRoute ? 0.9 : 0.7,
})

// ── FitBounds helper ──────────────────────────────────────────────────────────
// When a route is found, pan + zoom the map to fit the path.
function FitRoute({ positions }) {
  const map = useMap()
  useEffect(() => {
    if (positions && positions.length >= 2) {
      map.fitBounds(positions, { padding: [40, 40], maxZoom: 14 })
    }
  }, [positions, map])
  return null
}

// ── Main component ────────────────────────────────────────────────────────────
export default function TransitMap({ stops = [], route = null, onStopClick, fromStop, toStop }) {

  // Build a set of stop IDs that are on the current route
  const routeStopIds = new Set(route?.directions?.flatMap(d => {
    // Match stop names → stop IDs for highlighting
    const fromMatch = stops.find(s => s.name === d.from)
    const toMatch   = stops.find(s => s.name === d.to)
    return [fromMatch?.stop_id, toMatch?.stop_id].filter(Boolean)
  }) ?? [])

  // Build polyline positions from route directions
  const routePositions = route?.directions?.reduce((acc, step) => {
    const fromStop_ = stops.find(s => s.name === step.from)
    const toStop_   = stops.find(s => s.name === step.to)
    if (fromStop_) acc.push([parseFloat(fromStop_.lat), parseFloat(fromStop_.lon)])
    if (toStop_)   acc.push([parseFloat(toStop_.lat),   parseFloat(toStop_.lon)])
    return acc
  }, []) ?? []

  // Deduplicate consecutive identical positions
  const dedupedPositions = routePositions.filter(
    (pos, i, arr) => i === 0 ||
      pos[0] !== arr[i-1][0] || pos[1] !== arr[i-1][1]
  )

  return (
    <MapContainer
      center={BENGALURU_CENTER}
      zoom={DEFAULT_ZOOM}
      className="w-full h-full rounded-xl"
      zoomControl={true}
      scrollWheelZoom={true}
    >
      <TileLayer url={TILE_URL} attribution={TILE_ATT} />

      {/* ── Fit map to route when route changes ── */}
      {dedupedPositions.length >= 2 && (
        <FitRoute positions={dedupedPositions} />
      )}

      {/* ── Route polyline ── */}
      {dedupedPositions.length >= 2 && (
        <Polyline
          positions={dedupedPositions}
          pathOptions={{
            color:     '#1D9E75',
            weight:    4,
            opacity:   0.85,
            dashArray: null,
            lineCap:   'round',
            lineJoin:  'round',
          }}
        />
      )}

      {/* ── Walk segment polylines (dashed amber) ── */}
      {route?.directions
        ?.filter(d => d.type === 'walk')
        .map((step, i) => {
          const a = stops.find(s => s.name === step.from)
          const b = stops.find(s => s.name === step.to)
          if (!a || !b) return null
          return (
            <Polyline
              key={`walk-${i}`}
              positions={[
                [parseFloat(a.lat), parseFloat(a.lon)],
                [parseFloat(b.lat), parseFloat(b.lon)],
              ]}
              pathOptions={{
                color:     '#EF9F27',
                weight:    2.5,
                opacity:   0.7,
                dashArray: '6 4',
              }}
            />
          )
        })
      }

      {/* ── Stop markers ── */}
      {stops.map(stop => {
        const isFrom    = stop.name === fromStop
        const isTo      = stop.name === toStop
        const isOnRoute = routeStopIds.has(stop.stop_id)
        const style     = markerStyle(isFrom, isTo, isOnRoute)

        return (
          <CircleMarker
            key={stop.stop_id}
            center={[parseFloat(stop.lat), parseFloat(stop.lon)]}
            {...style}
            eventHandlers={{
              click: () => onStopClick?.(stop.name),
            }}
          >
            {/* Hover tooltip */}
            <Tooltip
              direction="top"
              offset={[0, -8]}
              opacity={0.95}
              className="!bg-gray-800 !text-gray-100 !border-gray-700 !text-xs !rounded-lg !px-2 !py-1"
            >
              <span className="font-medium">{stop.name}</span>
              <span className="text-gray-400 ml-1.5 font-mono text-[10px]">
                {stop.stop_id}
              </span>
            </Tooltip>

            {/* Click popup */}
            <Popup className="!bg-gray-800 !rounded-xl !border-gray-700">
              <div className="p-1 min-w-[140px]">
                <p className="font-medium text-gray-100 text-sm mb-2">{stop.name}</p>
                <p className="text-xs text-gray-400 font-mono mb-3">
                  {parseFloat(stop.lat).toFixed(4)}, {parseFloat(stop.lon).toFixed(4)}
                </p>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => onStopClick?.(stop.name, 'from')}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white
                               text-xs py-1 px-2 rounded-lg transition-colors"
                  >
                    Set as From
                  </button>
                  <button
                    onClick={() => onStopClick?.(stop.name, 'to')}
                    className="flex-1 bg-teal-600 hover:bg-teal-700 text-white
                               text-xs py-1 px-2 rounded-lg transition-colors"
                  >
                    Set as To
                  </button>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}
