/**
 * MapVisualizer - 해상 노선 지도 시각화 메인 컴포넌트.
 *
 * 주요 기능:
 * - Outbound/Inbound 경로를 Chaikin 스무딩으로 부드럽게 렌더링
 * - 노선 경도 분석 기반 동적 center 계산 (지도 복제 방지)
 * - Leg 중간점 고정 화살표 배치
 * - 라이트/다크 테마 전환 + 범례
 * - 항만 매칭 오류 수정 모달
 */
import { useEffect, useState, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

import RouteLayer, { RouteLegend } from './map/RouteLayer';
import { PortMarkers, ZoomHandler, MapUpdater, FitBoundsControl } from './map/MapControls';
import FixMismatchModal from './map/FixMismatchModal';
import { calcOptimalCenter, normalizeLngPacific } from './map/mapHelpers';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

const TILE_LAYERS = {
  light: {
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    bg: '#f4f6f8',
  },
  dark: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    bg: '#1a1a2e',
  },
};

/**
 * ThemeApplier: 다크테마일 때 Leaflet 컨테이너에 .dark-theme 클래스를 적용합니다.
 */
const ThemeApplier = ({ theme }) => {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    if (theme === 'dark') {
      container.classList.add('dark-theme');
    } else {
      container.classList.remove('dark-theme');
    }
  }, [theme, map]);
  return null;
};

const MapResizer = ({ isTimelineOpen }) => {
  const map = useMap();
  useEffect(() => {
    // 타임라인 패널 트랜지션 애니메이션과 매끄러운 싱크를 위해 여러 번 순차 리사이즈 처리
    const timer1 = setTimeout(() => map.invalidateSize({ animate: true }), 100);
    const timer2 = setTimeout(() => map.invalidateSize({ animate: true }), 250);
    const timer3 = setTimeout(() => map.invalidateSize({ animate: true }), 400);
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
    };
  }, [isTimelineOpen, map]);
  return null;
};

const MapVisualizer = ({ selectedRoute, allPorts, isTimelineOpen, onRouteUpdated, hoveredPortIndex, setHoveredPortIndex }) => {
  const [routePorts, setRoutePorts] = useState([]);
  const [unmatchedPorts, setUnmatchedPorts] = useState([]);
  const [matchStatus, setMatchStatus] = useState({ total: 0, matched: 0 });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [theme, setTheme] = useState('light');
  const [isSingleColor, setIsSingleColor] = useState(false);

  const lineGeometry = selectedRoute?.line_geometry || null;
  const tileConfig = TILE_LAYERS[theme];

  // ── 기항지 매칭 ──
  useEffect(() => {
    if (!selectedRoute || !allPorts || allPorts.length === 0) {
      setRoutePorts([]);
      setUnmatchedPorts([]);
      setMatchStatus({ total: 0, matched: 0 });
      return;
    }

    const rawNames = selectedRoute.port_rotation
      ? selectedRoute.port_rotation.split(/[,\->]+/)
      : [];
    const portNames = rawNames.map((n) => n.trim()).filter((n) => n.length > 0);

    let currentRoutePorts = [];
    let unmatched = [];
    let matchCount = 0;

    portNames.forEach((name) => {
      const cleanName = name.split('(')[0].trim().toLowerCase();
      const port = allPorts.find((p) => {
        const pName = p.port_name ? p.port_name.toLowerCase() : '';
        if (pName === cleanName) return true;
        if (Array.isArray(p.aliases)) {
          return p.aliases.some((a) => a.toLowerCase() === cleanName);
        }
        return false;
      });

      if (port) {
        const lat = parseFloat(port.lat);
        let lng = parseFloat(port.lng);
        if (!isNaN(lat) && !isNaN(lng)) {
          // 태평양 중심 단일지도 [-30, 330] 범위 경도 정규화 적용
          lng = normalizeLngPacific(lng);

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

  // ── 동적 center 계산 ──
  const mapCenter = useMemo(() => {
    if (routePorts.length > 0) {
      const { lat, lng } = calcOptimalCenter(routePorts);
      return [lat, lng];
    }
    return [25, 140];
  }, [routePorts]);

  const isDark = theme === 'dark';

  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* ── 상단 컨트롤들 ── */}
      <div className="absolute top-3 right-4 z-[1000] flex items-center gap-2">
        {/* PPTX 스타일 (단일 계열) 모드 토글 */}
        <button
          onClick={() => setIsSingleColor(!isSingleColor)}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold shadow-lg border transition-all duration-300 backdrop-blur-sm ${
            isSingleColor
              ? (isDark ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400/50 hover:bg-cyan-500/30' : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100')
              : (isDark ? 'bg-gray-800/90 text-gray-400 border-gray-700 hover:bg-gray-700/90' : 'bg-white/90 text-gray-500 border-gray-200 hover:bg-gray-50/90')
          }`}
        >
          📊 PPTX Style
        </button>
        {/* 테마 전환 */}
        <button
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold shadow-lg border transition-all duration-300 backdrop-blur-sm ${isDark
              ? 'bg-gray-800/90 text-cyan-400 border-cyan-500/50 hover:bg-gray-700/90'
              : 'bg-white/90 text-gray-700 border-gray-200 hover:bg-gray-50/90'
            }`}
        >
          {isDark ? '🌙 Dark' : '☀️ Light'}
        </button>
      </div>

      {/* ── 부산항 터미널 & 입출항 스케줄 정보 카드 (Proforma Overlay Card) ── */}
      {selectedRoute && selectedRoute.proforma && selectedRoute.proforma.length > 0 && (
        <div className="absolute top-16 right-4 z-[1000] w-64 transition-all duration-300">
          <div
            className={`backdrop-blur-md rounded-xl shadow-2xl border overflow-hidden ${
              isDark ? 'bg-gray-900/90 border-gray-700/80 text-gray-100' : 'bg-white/95 border-gray-200/80 text-gray-800'
            }`}
          >
            <div className="px-4 py-2.5 bg-[#002060] text-white flex items-center justify-between shadow-sm">
              <span className="text-xs font-bold tracking-wide uppercase">Busan Port Proforma</span>
              <span className="px-1.5 py-0.5 rounded bg-white/20 text-[9px] font-mono">
                {selectedRoute.svc || 'SVC'}
              </span>
            </div>
            <div className="p-3 divide-y divide-gray-200/20 max-h-56 overflow-y-auto">
              {selectedRoute.proforma.map((prof, pIdx) => (
                <div key={prof.term_id || pIdx} className="py-2 first:pt-0 last:pb-0">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-bold text-[#3494BA] flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#00B050]" />
                      {prof.terminal_name}
                    </span>
                    {prof.wtp && (
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                        isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'
                      }`}>
                        {prof.wtp} TEU/w
                      </span>
                    )}
                  </div>
                  {prof.sch && (
                    <div className="text-[10px] opacity-75 font-mono flex items-center gap-1 mt-0.5">
                      📅 {prof.sch}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 범례 ── */}
      {lineGeometry && (
        <div className="absolute top-3 left-[340px] z-[1000]">
          <RouteLegend
            theme={theme}
            totalDistance={lineGeometry.total_distance_km || 0}
            isSingleColor={isSingleColor}
          />
        </div>
      )}

      {/* ── 하단 Status Bar ── */}
      <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 z-[1000]">
        <div
          className={`backdrop-blur-md px-5 py-2 rounded-full shadow-lg text-xs font-mono border flex items-center gap-3 ${isDark
              ? 'bg-gray-900/85 border-gray-600/50 text-gray-200'
              : 'bg-white/85 border-gray-200 text-gray-700'
            }`}
        >
          {selectedRoute ? (
            <>
              <span
                className={`font-bold ${matchStatus.matched === matchStatus.total
                    ? isDark ? 'text-green-400' : 'text-green-600'
                    : isDark ? 'text-red-400' : 'text-red-600'
                  }`}
              >
                ● {matchStatus.matched}/{matchStatus.total} Ports
              </span>
              {unmatchedPorts.length > 0 && (
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="bg-red-500 hover:bg-red-600 text-white px-3 py-0.5 rounded-full text-[10px] font-bold shadow-sm animate-pulse"
                >
                  Fix {unmatchedPorts.length}
                </button>
              )}
            </>
          ) : (
            <span className="opacity-60">Select a route to visualize</span>
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
          if (onRouteUpdated) onRouteUpdated();
        }}
      />

      <MapContainer
        key="main-map-container"
        center={mapCenter}
        zoom={3}
        minZoom={2}
        maxZoom={12}
        style={{
          height: '100%',
          width: '100%',
          backgroundColor: tileConfig.bg,
        }}
        scrollWheelZoom={true}
        worldCopyJump={false} // 가로 복제 점프 차단
        preferCanvas={true}
        maxBounds={[[-85, -30], [85, 330]]} // 태평양 중심 단일 세계 화면 영역 제한 (대서양 경계선 기준)
        maxBoundsViscosity={1.0}
      >
        <ThemeApplier theme={theme} />
        <MapResizer isTimelineOpen={isTimelineOpen} />
        <ZoomHandler />
        <TileLayer
          key={theme}
          attribution={tileConfig.attribution}
          url={tileConfig.url}
          noWrap={false} // maxBounds로 가둔 상태에서 180도 우측 복제 영역 타일을 채우기 위해 켬
        />

        <RouteLayer lineGeometry={lineGeometry} theme={theme} isSingleColor={isSingleColor} />
        <PortMarkers routePorts={routePorts} hoveredPortIndex={hoveredPortIndex} setHoveredPortIndex={setHoveredPortIndex} />
        <MapUpdater coordinates={lineGeometry} center={mapCenter} region={selectedRoute?.region} />
        <FitBoundsControl coordinates={lineGeometry} region={selectedRoute?.region} />
      </MapContainer>
    </div>
  );
};

export default MapVisualizer;