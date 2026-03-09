import { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { routeService } from '../services/api';

// Fix Leaflet default icon issue
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Custom Marker Generator
const createPortIcon = (portName, index, total) => {
  const name = portName || '';
  const isBusan = name.toLowerCase().includes("busan");
  const isStart = index === 0;
  const isEnd = index === total - 1;
  let markerClass = "";
  if (isBusan) markerClass = "port-highlight";
  else if (isStart || isEnd) markerClass = "port-start-end";

  return L.divIcon({
    className: 'custom-div-icon',
    html: `
        <div class="port-marker ${markerClass}">
          <div class="port-dot"></div>
          <div class="port-label">${name}</div>
          ${index !== undefined ? `<div class="seq-badge">${index + 1}</div>` : ''}
        </div>
      `,
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });
};

const ZoomHandler = () => {
  const map = useMap();
  useMapEvents({
    zoomend: () => {
      const z = map.getZoom();
      const container = map.getContainer();
      container.classList.remove('zoom-low', 'zoom-mid', 'zoom-high');
      if (z < 3) container.classList.add('zoom-low');
      else if (z < 6) container.classList.add('zoom-mid');
      else container.classList.add('zoom-high');
    }
  });
  return null;
};

const MapUpdater = ({ coordinates }) => {
  const map = useMap();
  useEffect(() => {
    if (coordinates && coordinates.length > 0) {
      try {
        const bounds = L.latLngBounds(coordinates);
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [50, 50], maxZoom: 5 });
        }
      } catch (e) {
        console.warn("Invalid bounds", e);
      }
    }
  }, [coordinates, map]);
  return null;
};

// --- Fix Mismatch Modal Component ---
const FixMismatchModal = ({ isOpen, onClose, unmatchedPorts, allPorts, routeIdx, onFixed }) => {
  const [selectedBad, setSelectedBad] = useState('');
  const [selectedGood, setSelectedGood] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [filterText, setFilterText] = useState('');

  useEffect(() => {
    if (unmatchedPorts.length > 0) setSelectedBad(unmatchedPorts[0]);
  }, [unmatchedPorts]);

  if (!isOpen) return null;

  const filteredPorts = allPorts.filter(p =>
    p.port_name.toLowerCase().includes(filterText.toLowerCase()) ||
    p.port_code.toLowerCase().includes(filterText.toLowerCase())
  ).slice(0, 50); // Limit results

  const handleFix = async () => {
    if (!selectedBad || !selectedGood) return;
    setIsSubmitting(true);
    try {
      await routeService.fixPortMismatch(routeIdx, selectedBad, selectedGood);
      // alert(`Successfully mapped '${selectedBad}' to port '${selectedGood}'`); // Optional: simplify UX
      onFixed(); // Trigger parent refresh
      // Don't close modal, allow fixing next item
    } catch (e) {
      alert('Failed to fix mismatch: ' + e.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-96 max-w-full">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-[#003399]">Fix Port Mismatch</h3>
          <div className="text-xs text-gray-500 font-normal">
            {unmatchedPorts.length} issue(s) remaining
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-bold text-gray-700 mb-1">Unmatched Port Name (Typo)</label>
          <select
            className="w-full border border-gray-300 rounded p-2 text-sm"
            value={selectedBad}
            onChange={(e) => setSelectedBad(e.target.value)}
          >
            {unmatchedPorts.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        <div className="mb-6">
          <label className="block text-xs font-bold text-gray-700 mb-1">Map to Correct Port</label>
          <input
            type="text"
            placeholder="Search port..."
            className="w-full border border-gray-300 rounded p-1 text-xs mb-1"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
          />
          <select
            className="w-full border border-gray-300 rounded p-2 text-sm"
            value={selectedGood}
            onChange={(e) => setSelectedGood(e.target.value)}
            size={5}
          >
            {filteredPorts.map(p => (
              <option key={p.port_code} value={p.port_code}>
                {p.port_name} ({p.nation_name})
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded text-sm"
          >
            Close
          </button>
          <button
            onClick={handleFix}
            disabled={isSubmitting || !selectedGood}
            className="px-4 py-2 bg-[#003399] text-white rounded hover:bg-blue-800 text-sm disabled:opacity-50"
          >
            {isSubmitting ? 'Saving...' : 'Save & Fix'}
          </button>
        </div>
      </div>
    </div>
  );
};


const MapVisualizer = ({ selectedRoute, allPorts, onRouteUpdated }) => {
  const [routePorts, setRoutePorts] = useState([]);
  const [unmatchedPorts, setUnmatchedPorts] = useState([]);
  const [matchStatus, setMatchStatus] = useState({ total: 0, matched: 0 });

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Apply visual offset to prevent overlapping lines (Spiral effect)
  const processGeometry = (geometry) => {
    if (!geometry) return [];
    return geometry.map((coord, idx) => {
      // coord is [lat, lng]
      // Increased offset factor to 0.003 for better visibility separation
      const offset = idx * 0.003;
      return [coord[0] + offset, coord[1]];
    });
  };

  const lineGeometry = processGeometry(selectedRoute?.line_geometry);

  useEffect(() => {
    if (!selectedRoute || !allPorts || allPorts.length === 0) {
      setRoutePorts([]);
      setUnmatchedPorts([]);
      setMatchStatus({ total: 0, matched: 0 });
      return;
    }

    const rawNames = selectedRoute.port_rotation ? selectedRoute.port_rotation.split(/[,\->]+/) : [];
    const portNames = rawNames.map(name => name.trim()).filter(name => name.length > 0);

    let currentRoutePorts = [];
    let unmatched = [];
    let matchCount = 0;

    portNames.forEach(name => {
      const cleanName = name.split('(')[0].trim().toLowerCase();

      const port = allPorts.find(p => {
        const pName = p.port_name ? p.port_name.toLowerCase() : '';
        if (pName === cleanName) return true;
        if (Array.isArray(p.aliases)) {
          return p.aliases.some(a => a.toLowerCase() === cleanName);
        }
        return false;
      });

      if (port) {
        const lat = parseFloat(port.lat);
        const lng = parseFloat(port.lng);
        if (!isNaN(lat) && !isNaN(lng)) {
          currentRoutePorts.push({ ...port, lat, lng, originalName: name });
          matchCount++;
        }
      } else {
        unmatched.push(name);
      }
    });

    setRoutePorts(currentRoutePorts);
    setUnmatchedPorts(unmatched);
    setMatchStatus({ total: portNames.length, matched: matchCount });

  }, [selectedRoute, allPorts]);

  return (
    <div className="h-full w-full rounded-lg overflow-hidden shadow border border-gray-200 relative">
      {/* Status Panel - Moved to Bottom Center */}
      <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 z-[1000] flex flex-col items-center gap-2">
        <div className="bg-white bg-opacity-90 px-4 py-2 rounded-full shadow-lg text-xs font-mono border border-gray-300 flex items-center gap-3">
          {selectedRoute ? (
            <>
              <span className={matchStatus.matched === matchStatus.total ? "text-green-600 font-bold" : "text-red-600 font-bold"}>
                Status: {matchStatus.matched}/{matchStatus.total} Ports
              </span>
              {unmatchedPorts.length > 0 && (
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded-full text-[10px] font-bold shadow-sm animate-pulse"
                >
                  Fix {unmatchedPorts.length} Issues
                </button>
              )}
            </>
          ) : (
            <span className="text-gray-500">Select a route to visualize</span>
          )}
        </div>
      </div>

      <FixMismatchModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        unmatchedPorts={unmatchedPorts}
        allPorts={allPorts}
        routeIdx={selectedRoute?.route_idx}
        onFixed={() => {
          if (onRouteUpdated) onRouteUpdated(); // Trigger parent refresh
        }}
      />

      <MapContainer
        center={[20, 0]}
        zoom={2}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
        worldCopyJump={false}
        minZoom={2}
      >
        <ZoomHandler />
        <TileLayer
          attribution='&copy; CARTO'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png"
          noWrap={false}
        />

        {/* Draw Path using processed (offset) geometry */}
        {lineGeometry && lineGeometry.length > 1 && (
          <Polyline
            positions={lineGeometry}
            pathOptions={{
              color: '#003399',
              weight: 4,
              opacity: 0.8,
              lineJoin: 'round',
              lineCap: 'round'
            }}
            smoothFactor={0.5}
          />
        )}

        {/* Draw Markers */}
        {routePorts.map((port, idx) => (
          <Marker
            key={`${port.port_code}-${idx}`}
            position={[port.lat, port.lng]}
            icon={createPortIcon(port.port_name, idx, routePorts.length)}
          >
            <Popup>
              <div className="text-center min-w-[120px]">
                <h3 className="font-bold text-base text-[#002060]">{port.port_name}</h3>
                <div className="text-xs text-gray-500">{port.nation_name}</div>
                <div className="mt-1 text-xs bg-gray-100 rounded px-1 py-0.5 inline-block">
                  Seq: {idx + 1}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        <MapUpdater coordinates={lineGeometry} />
      </MapContainer>
    </div>
  );
};

export default MapVisualizer;