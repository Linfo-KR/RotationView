import { useEffect } from 'react';
import { Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

/**
 * 항만 마커 아이콘을 생성합니다.
 */
const createPortIcon = (portName, index, total) => {
  const name = portName || '';
  const isBusan = name.toLowerCase().includes('busan');
  const isStart = index === 0;
  const isEnd = index === total - 1;
  const isChokepoint = 
    name.toLowerCase().includes('panama') ||
    name.toLowerCase().includes('suez') ||
    name.toLowerCase().includes('gibraltar') ||
    name.toLowerCase().includes('malacca') ||
    name.toLowerCase().includes('singapore');

  let markerClass = '';
  let dotHtml = '<div class="port-dot"></div>';

  if (isBusan) {
    markerClass = 'port-highlight';
  } else if (isChokepoint) {
    markerClass = 'port-chokepoint';
    dotHtml = `
      <div class="chokepoint-icon-wrapper animate-pulse">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffcc00" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="chokepoint-svg">
          <circle cx="12" cy="5" r="3" />
          <line x1="12" y1="8" x2="12" y2="22" />
          <line x1="5" y1="12" x2="19" y2="12" />
          <path d="M12 22a7 7 0 0 0 7-7" />
          <path d="M12 22a7 7 0 0 1-7-7" />
        </svg>
      </div>
    `;
  } else if (isStart || isEnd) {
    markerClass = 'port-start-end';
  }

  return L.divIcon({
    className: 'custom-div-icon',
    html: `
      <div class="port-marker ${markerClass}">
        ${dotHtml}
        <div class="port-label">${name}</div>
        ${index !== undefined ? `<div class="seq-badge">${index + 1}</div>` : ''}
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

/**
 * 기항지 마커를 렌더링하는 컴포넌트.
 */
const PortMarkers = ({ routePorts }) => {
  return (
    <>
      {routePorts.map((port, idx) => (
        <Marker
          key={`${port.port_code}-${idx}`}
          position={L.latLng(port.lat, port.lng, true)}
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
    </>
  );
};

/**
 * ZoomHandler: 줌 레벨에 따라 CSS 클래스를 토글합니다.
 */
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
    },
  });
  return null;
};

/**
 * MapUpdater: 경로 좌표에 맞게 지도 범위를 자동 조정합니다.
 */
const MapUpdater = ({ coordinates }) => {
  const map = useMap();
  useEffect(() => {
    if (!coordinates) return;
    try {
      let allPoints = [];
      if (Array.isArray(coordinates)) {
        allPoints = coordinates;
      } else {
        if (coordinates.outbound) coordinates.outbound.forEach(line => allPoints.push(...line));
        if (coordinates.inbound) coordinates.inbound.forEach(line => allPoints.push(...line));
      }
      if (allPoints.length > 0) {
        const latLngs = allPoints.map(p => L.latLng(p[0], p[1], true));
        const bounds = L.latLngBounds(latLngs);
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [60, 60], maxZoom: 5 });
        }
      }
    } catch (e) {
      console.warn('Invalid bounds', e);
    }
  }, [coordinates, map]);
  return null;
};

/**
 * FitBoundsControl: 경로 fit 버튼.
 */
const FitBoundsControl = ({ coordinates }) => {
  const map = useMap();
  return (
    <div className="leaflet-bottom leaflet-right">
      <div className="leaflet-control mb-8 mr-2 pointer-events-auto">
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (!coordinates) return;
            let allPoints = [];
            if (Array.isArray(coordinates)) {
              allPoints = coordinates;
            } else {
              if (coordinates.outbound) coordinates.outbound.forEach(line => allPoints.push(...line));
              if (coordinates.inbound) coordinates.inbound.forEach(line => allPoints.push(...line));
            }
            if (allPoints.length > 0) {
              const latLngs = allPoints.map(p => L.latLng(p[0], p[1], true));
              const bounds = L.latLngBounds(latLngs);
              if (bounds.isValid()) map.fitBounds(bounds, { padding: [60, 60], maxZoom: 5 });
            }
          }}
          className="bg-white hover:bg-gray-100 text-[#003399] font-bold p-2 text-sm rounded shadow-md border border-gray-300 flex items-center justify-center cursor-pointer transition-colors"
          title="Fit Route to Screen"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l3.293 3.293a1 1 0 11-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 110-2h4a1 1 0 011 1v4a1 1 0 11-2 0V6.414l-3.293 3.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 112 0v1.586l3.293-3.293a1 1 0 111.414 1.414L6.414 15H8a1 1 0 110 2H4a1 1 0 01-1-1v-4zm13-1a1 1 0 112 0v4a1 1 0 01-1 1h-4a1 1 0 110-2h1.586l-3.293-3.293a1 1 0 111.414-1.414L15 13.586V12z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export { PortMarkers, ZoomHandler, MapUpdater, FitBoundsControl };
