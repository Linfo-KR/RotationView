import { useEffect } from 'react';
import { Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { getOptimizedBounds } from './mapHelpers';

/**
 * 항만 마커 아이콘을 생성합니다.
 */
const createPortIcon = (portName, index, total, labelDir = 'bottom', labelDist = 20, isHovered = false) => {
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

  // 방향과 거리에 따른 편차 픽셀 계산
  let dx = 0;
  let dy = 0;
  const dist = labelDist;
  
  switch (labelDir) {
    case 'top': dx = 0; dy = -dist; break;
    case 'bottom': dx = 0; dy = dist; break;
    case 'right': dx = dist; dy = 0; break;
    case 'left': dx = -dist; dy = 0; break;
    case 'top-right': dx = Math.round(dist * 0.7); dy = -Math.round(dist * 0.7); break;
    case 'top-left': dx = -Math.round(dist * 0.7); dy = -Math.round(dist * 0.7); break;
    case 'bottom-right': dx = Math.round(dist * 0.7); dy = Math.round(dist * 0.7); break;
    case 'bottom-left': dx = -Math.round(dist * 0.7); dy = Math.round(dist * 0.7); break;
    default: dx = 0; dy = dist;
  }

  // 지시선(Leader Line) SVG 생성 - 이격거리가 25px를 초과할 경우에만 점선 노출
  const showLeaderLine = dist > 25;
  const leaderLineHtml = showLeaderLine ? `
    <svg class="leader-line-svg" style="position: absolute; top: 0; left: 0; width: 150px; height: 150px; pointer-events: none; overflow: visible; z-index: -1;">
      <line x1="12" y1="12" x2="${12 + dx}" y2="${12 + dy}" stroke="${isBusan ? '#00B050' : '#888888'}" stroke-width="0.8" stroke-dasharray="2,2" />
    </svg>
  ` : '';

  // 라벨 정렬용 CSS 보정 (라벨 박스의 물리적 부착 지점 조절)
  let labelAlignStyle = '';
  if (labelDir === 'left') {
    labelAlignStyle = 'transform: translate(-100%, -50%); margin-left: -4px;';
  } else if (labelDir === 'right') {
    labelAlignStyle = 'transform: translate(0, -50%); margin-left: 4px;';
  } else if (labelDir === 'top') {
    labelAlignStyle = 'transform: translate(-50%, -100%); margin-top: -4px;';
  } else if (labelDir === 'bottom') {
    labelAlignStyle = 'transform: translate(-50%, 0); margin-top: 4px;';
  } else if (labelDir === 'top-right') {
    labelAlignStyle = 'transform: translate(0, -100%); margin-left: 2px; margin-top: -2px;';
  } else if (labelDir === 'top-left') {
    labelAlignStyle = 'transform: translate(-100%, -100%); margin-left: -2px; margin-top: -2px;';
  } else if (labelDir === 'bottom-right') {
    labelAlignStyle = 'transform: translate(0, 0); margin-left: 2px; margin-top: 2px;';
  } else if (labelDir === 'bottom-left') {
    labelAlignStyle = 'transform: translate(-100%, 0); margin-left: -2px; margin-top: 2px;';
  }

  return L.divIcon({
    className: 'custom-div-icon',
    html: `
      <div class="port-marker ${markerClass}" style="position: relative; width: 24px; height: 24px; overflow: visible;">
        ${dotHtml}
        ${leaderLineHtml}
        <div class="port-label" style="position: absolute; left: ${12 + dx}px; top: ${12 + dy}px; white-space: nowrap; ${labelAlignStyle}">
          ${name}
        </div>
        ${index !== undefined ? `<div class="seq-badge" style="z-index: 10;">${index + 1}</div>` : ''}
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

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

    const getLabelBounds = (x, y, text, dir, dist) => {
      const textLen = text ? text.length : 10;
      const w = textLen * 6.0 + 8;
      const h = 14;
      
      let dx = 0;
      let dy = 0;
      switch (dir) {
        case 'top': dx = 0; dy = -dist; break;
        case 'bottom': dx = 0; dy = dist; break;
        case 'right': dx = dist; dy = 0; break;
        case 'left': dx = -dist; dy = 0; break;
        case 'top-right': dx = dist * 0.7; dy = -dist * 0.7; break;
        case 'top-left': dx = -dist * 0.7; dy = -dist * 0.7; break;
        case 'bottom-right': dx = dist * 0.7; dy = dist * 0.7; break;
        case 'bottom-left': dx = -dist * 0.7; dy = dist * 0.7; break;
      }

      const lx = x + dx;
      const ly = y + dy;
      
      let x1 = lx - w / 2, y1 = ly;
      if (dir === 'left') { x1 = lx - w; y1 = ly - h / 2; }
      else if (dir === 'right') { x1 = lx; y1 = ly - h / 2; }
      else if (dir === 'top') { x1 = lx - w / 2; y1 = ly - h; }
      else if (dir === 'bottom') { x1 = lx - w / 2; y1 = ly; }
      else if (dir === 'top-right') { x1 = lx; y1 = ly - h; }
      else if (dir === 'top-left') { x1 = lx - w; y1 = ly - h; }
      else if (dir === 'bottom-right') { x1 = lx; y1 = ly; }
      else if (dir === 'bottom-left') { x1 = lx - w; y1 = ly; }

      return { x1, y1, x2: x1 + w, y2: y1 + h };
    };

    const intersects = (box1, box2) => {
      return !(box1.x2 < box2.x1 || box1.x1 > box2.x2 || box1.y2 < box2.y1 || box1.y1 > box2.y2);
    };

    visiblePorts.forEach((port) => {
      const x = port.pixel.x;
      const y = port.pixel.y;
      const text = port.port_name;

      const candidates = ['bottom', 'top', 'right', 'left', 'top-right', 'top-left', 'bottom-right', 'bottom-left'];
      const distances = [20, 36, 52]; // 겹침 정도에 따라 이격거리 점진적 확대
      
      let bestDir = 'bottom';
      let bestDist = 20;
      let minOverlapArea = Infinity;
      let foundNoOverlap = false;

      for (const dist of distances) {
        for (const dir of candidates) {
          const box = getLabelBounds(x, y, text, dir, dist);
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
            bestDist = dist;
            foundNoOverlap = true;
            break;
          }

          if (overlapArea < minOverlapArea) {
            minOverlapArea = overlapArea;
            bestDir = dir;
            bestDist = dist;
          }
        }
        if (foundNoOverlap) {
          break;
        }
      }

      newDirections[port.port_code + '-' + port.idx] = { dir: bestDir, dist: bestDist };
      const finalBox = getLabelBounds(x, y, text, bestDir, bestDist);
      placedBoxes.push(finalBox);
    });

    setDirections(newDirections);
  }, [routePorts, zoom, map]);

  return (
    <>
      {routePorts.map((port, idx) => {
        const { dir, dist } = directions[port.port_code + '-' + idx] || { dir: 'bottom', dist: 20 };
        const isHovered = idx === hoveredPortIndex;
        return (
          <Marker
            key={`${port.port_code}-${idx}`}
            position={L.latLng(port.lat, port.lng, true)}
            icon={createPortIcon(port.port_name, idx, routePorts.length, dir, dist, isHovered)}
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
const MapUpdater = ({ coordinates, center, region }) => {
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
            // 단거리 리전 여부 감지
            const rName = (region || '').toLowerCase();
            const isShortRegion = rName.includes('japan') || rName.includes('korea') || rName.includes('china') || rName.includes('russia');
            
            const fitPadding = isShortRegion ? [100, 100] : [60, 60];
            const fitMaxZoom = isShortRegion ? 7 : 5;
            
            map.fitBounds(bounds, { padding: fitPadding, maxZoom: fitMaxZoom });
          }
        }
      }
    } catch (e) {
      console.warn('Invalid bounds', e);
    }
  }, [coordinates, center, region, map]);
  return null;
};

/**
 * FitBoundsControl: 경로 fit 버튼.
 */
const FitBoundsControl = ({ coordinates, region }) => {
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
                if (bounds.isValid()) {
                  const rName = (region || '').toLowerCase();
                  const isShortRegion = rName.includes('japan') || rName.includes('korea') || rName.includes('china') || rName.includes('russia');
                  
                  const fitPadding = isShortRegion ? [100, 100] : [60, 60];
                  const fitMaxZoom = isShortRegion ? 7 : 5;
                  
                  map.fitBounds(bounds, { padding: fitPadding, maxZoom: fitMaxZoom });
                }
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
