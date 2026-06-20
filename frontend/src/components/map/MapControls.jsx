import { useEffect } from 'react';
import { Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { getOptimizedBounds } from './mapHelpers';

/**
 * 항만 마커 아이콘을 생성합니다.
 */
const createPortIcon = (portName, index, total, labelDir = 'bottom', isHovered = false) => {
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

  if (isHovered) {
    markerClass += ' port-hovered';
  }

  const dirClass = `label-dir-${labelDir}`;

  return L.divIcon({
    className: 'custom-div-icon',
    html: `
      <div class="port-marker ${markerClass}">
        ${dotHtml}
        <div class="port-label ${dirClass}">${name}</div>
        ${index !== undefined ? `<div class="seq-badge">${index + 1}</div>` : ''}
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

/**
 * 기항지 마커를 렌더링하는 컴포넌트.
 * 실시간 픽셀 좌표 충돌 검사를 통해 라벨을 8방향으로 스마트 재배치합니다.
 */
import { useState } from 'react';

const PortMarkers = ({ routePorts, hoveredPortIndex, setHoveredPortIndex }) => {
  const map = useMap();
  const [directions, setDirections] = useState({});
  const [zoom, setZoom] = useState(map.getZoom());

  useEffect(() => {
    const handleMapChange = () => {
      setZoom(map.getZoom());
    };
    map.on('zoomend moveend', handleMapChange);
    return () => {
      map.off('zoomend moveend', handleMapChange);
    };
  }, [map]);

  useEffect(() => {
    if (routePorts.length === 0) return;

    const visiblePorts = routePorts.map((port, idx) => {
      const name = port.port_name || '';
      const isBusan = name.toLowerCase().includes('busan');
      const isStart = idx === 0;
      const isEnd = idx === routePorts.length - 1;
      const isChokepoint = 
        name.toLowerCase().includes('panama') ||
        name.toLowerCase().includes('suez') ||
        name.toLowerCase().includes('gibraltar') ||
        name.toLowerCase().includes('malacca') ||
        name.toLowerCase().includes('singapore');

      const isImportant = isBusan || isStart || isEnd || isChokepoint;
      const isVisible = zoom >= 3 || isImportant;

      let pixel = { x: 0, y: 0 };
      try {
        pixel = map.latLngToContainerPoint([port.lat, port.lng]);
      } catch (e) {
        // map context 에러 방지
      }

      return {
        ...port,
        idx,
        isImportant,
        isVisible,
        pixel,
      };
    }).filter(p => p.isVisible);

    // 중요 포트 우선순위 부여
    visiblePorts.sort((a, b) => {
      if (a.isImportant && !b.isImportant) return -1;
      if (!a.isImportant && b.isImportant) return 1;
      return a.idx - b.idx;
    });

    const newDirections = {};
    const placedBoxes = [];

    const getLabelBounds = (x, y, text, dir) => {
      const textLen = text ? text.length : 10;
      const w = textLen * 6.0 + 8;
      const h = 14;
      
      switch (dir) {
        case 'top':
          return { x1: x - w / 2, y1: y - 22, x2: x + w / 2, y2: y - 8 };
        case 'right':
          return { x1: x + 12, y1: y - h / 2, x2: x + 12 + w, y2: y + h / 2 };
        case 'left':
          return { x1: x - 12 - w, y1: y - h / 2, x2: x - 12, y2: y + h / 2 };
        case 'top-right':
          return { x1: x + 10, y1: y - 18, x2: x + 10 + w, y2: y - 4 };
        case 'top-left':
          return { x1: x - 10 - w, y1: y - 18, x2: x - 10, y2: y - 4 };
        case 'bottom-right':
          return { x1: x + 10, y1: y + 8, x2: x + 10 + w, y2: y + 22 };
        case 'bottom-left':
          return { x1: x - 10 - w, y1: y + 8, x2: x - 10, y2: y + 22 };
        case 'bottom':
        default:
          return { x1: x - w / 2, y1: y + 6, x2: x + w / 2, y2: y + 20 };
      }
    };

    const intersects = (box1, box2) => {
      return !(box1.x2 < box2.x1 || box1.x1 > box2.x2 || box1.y2 < box2.y1 || box1.y1 > box2.y2);
    };

    visiblePorts.forEach((port) => {
      const x = port.pixel.x;
      const y = port.pixel.y;
      const text = port.port_name;

      const candidates = ['bottom', 'top', 'right', 'left', 'top-right', 'top-left', 'bottom-right', 'bottom-left'];
      let bestDir = 'bottom';
      let minOverlapArea = Infinity;

      for (const dir of candidates) {
        const box = getLabelBounds(x, y, text, dir);
        let overlapArea = 0;

        for (const placed of placedBoxes) {
          if (intersects(box, placed)) {
            const ix1 = Math.max(box.x1, placed.x1);
            const iy1 = Math.max(box.y1, placed.y1);
            const ix2 = Math.min(box.x2, placed.x2);
            const iy2 = Math.min(box.y2, placed.y2);
            overlapArea += (ix2 - ix1) * (iy2 - iy1);
          }
        }

        if (overlapArea === 0) {
          bestDir = dir;
          break;
        }

        if (overlapArea < minOverlapArea) {
          minOverlapArea = overlapArea;
          bestDir = dir;
        }
      }

      newDirections[port.port_code + '-' + port.idx] = bestDir;
      const finalBox = getLabelBounds(x, y, text, bestDir);
      placedBoxes.push(finalBox);
    });

    setDirections(newDirections);
  }, [routePorts, zoom, map]);

  return (
    <>
      {routePorts.map((port, idx) => {
        const dir = directions[port.port_code + '-' + idx] || 'bottom';
        const isHovered = idx === hoveredPortIndex;
        return (
          <Marker
            key={`${port.port_code}-${idx}`}
            position={L.latLng(port.lat, port.lng, true)}
            icon={createPortIcon(port.port_name, idx, routePorts.length, dir, isHovered)}
            eventHandlers={{
              mouseover: () => setHoveredPortIndex(idx),
              mouseout: () => setHoveredPortIndex(null),
            }}
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
        );
      })}
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
const MapUpdater = ({ coordinates, center }) => {
  const map = useMap();
  
  useEffect(() => {
    window.leafletMap = map;
    return () => {
      window.leafletMap = null;
    };
  }, [map]);

  useEffect(() => {
    if (!coordinates) {
      if (center) {
        map.setView(center, map.getZoom() || 3);
      }
      return;
    }
    try {
      let allPoints = [];
      if (Array.isArray(coordinates)) {
        allPoints = coordinates;
      } else {
        if (coordinates.outbound) coordinates.outbound.forEach(line => allPoints.push(...line));
        if (coordinates.inbound) coordinates.inbound.forEach(line => allPoints.push(...line));
      }
      if (allPoints.length > 0) {
        const boundsData = getOptimizedBounds(allPoints);
        if (boundsData) {
          const bounds = L.latLngBounds(boundsData);
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [60, 60], maxZoom: 5 });
          }
        }
      }
    } catch (e) {
      console.warn('Invalid bounds', e);
    }
  }, [coordinates, center, map]);
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
              const boundsData = getOptimizedBounds(allPoints);
              if (boundsData) {
                const bounds = L.latLngBounds(boundsData);
                if (bounds.isValid()) map.fitBounds(bounds, { padding: [60, 60], maxZoom: 5 });
              }
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
