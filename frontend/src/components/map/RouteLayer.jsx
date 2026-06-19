import { useEffect, useRef, useState, useMemo } from 'react';
import { Polyline, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { makeBezierCurve, getEquidistantArrows, splitPolylineAtAntimeridian } from './mapHelpers';
import { MAP_SETTINGS } from '../../config/mapSettings';

// ── 테마별 색상 ──────────────────────────────

const THEME_COLORS = {
  light: {
    outColor: '#0066cc',
    outGlow: 'rgba(0, 102, 204, 0.25)',
    outArrow: '#004d99',
    inColor: '#cc2e2e',
    inGlow: 'rgba(204, 46, 46, 0.25)',
    inArrow: '#991f1f',
  },
  dark: {
    outColor: '#00ccff',
    outGlow: 'rgba(0, 204, 255, 0.28)',
    outArrow: '#00e5ff',
    inColor: '#ff4488',
    inGlow: 'rgba(255, 68, 136, 0.28)',
    inArrow: '#ff5599',
  },
};

// ── ArrowMarker ──────────────────────────────

/**
 * 지도의 줌 레벨과 세그먼트 거리에 맞춰 실시간 계산된 등간격 화살표들을 지도에 아름답게 렌더링합니다.
 */
const ArrowMarker = ({ arrows, color }) => {
  const map = useMap();
  const markersRef = useRef([]);

  useEffect(() => {
    // 이전 화살표 클린업
    markersRef.current.forEach((m) => map.removeLayer(m));
    markersRef.current = [];

    if (!arrows || arrows.length === 0) return;

    arrows.forEach((arrow) => {
      const icon = L.divIcon({
        className: 'arrow-marker-icon',
        html: `<svg width="20" height="20" viewBox="0 0 24 24" style="transform: rotate(${arrow.bearing}deg); filter: drop-shadow(0 1.5px 2.5px rgba(0,0,0,0.35));">
          <polygon points="4,4 20,12 4,20" fill="${color}" stroke="white" stroke-width="1.8" stroke-linejoin="round" />
        </svg>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      const marker = L.marker([arrow.lat, arrow.lng], {
        icon,
        interactive: false,
      }).addTo(map);
      markersRef.current.push(marker);
    });

    return () => {
      markersRef.current.forEach((m) => map.removeLayer(m));
      markersRef.current = [];
    };
  }, [map, arrows, color]);

  return null;
};

// ── Legend ────────────────────────────────────

export const RouteLegend = ({ theme, totalDistance }) => {
  const colors = THEME_COLORS[theme] || THEME_COLORS.light;
  const isDark = theme === 'dark';

  return (
    <div className={`route-legend ${isDark ? 'dark' : ''} transition-all duration-300`}>
      <div className="legend-item">
        <div className="legend-line ob-legend-line" style={{ backgroundColor: colors.outColor }} />
        <span className="font-semibold text-[11px]">Outbound</span>
      </div>
      <div className="legend-item">
        <div className="legend-line ib-legend-line" style={{ backgroundColor: colors.inColor }} />
        <span className="font-semibold text-[11px]">Inbound</span>
      </div>
      {totalDistance > 0 && (
        <div style={{ marginTop: '5px', fontSize: '10px', opacity: 0.8, borderTop: '1px solid rgba(128,128,128,0.25)', paddingTop: '5px' }}>
          🚢 Total: <strong className={isDark ? 'text-cyan-400' : 'text-blue-700'}>{Math.round(totalDistance).toLocaleString()} km</strong>
        </div>
      )}
    </div>
  );
};

// ── RouteLayer ────────────────────────────────

/**
 * RouteLayer: Outbound/Inbound 경로 렌더링 + 동적 실시간 화살표 + 흐름 애니메이션 오버레이.
 */
const RouteLayer = ({ lineGeometry, theme = 'light' }) => {
  if (!lineGeometry) return null;

  const colors = THEME_COLORS[theme] || THEME_COLORS.light;
  const isDark = theme === 'dark';

  const outboundLines = lineGeometry.outbound || [];
  const inboundLines = lineGeometry.inbound || [];

  // 1. 유려한 궤적 스무딩 적용 (쪼개지지 않은 온전한 선에 Bezier 곡선화 적용하여 날짜변경선 경계 짤림 방지)
  const smoothedOutboundUnsplit = useMemo(() => {
    return outboundLines.map((line) => makeBezierCurve(line));
  }, [outboundLines]);

  const smoothedInboundUnsplit = useMemo(() => {
    return inboundLines.map((line) => makeBezierCurve(line));
  }, [inboundLines]);

  // 2. 렌더링 직전에 날짜변경선(180도) 기준으로 정밀 분할
  const smoothedOutbound = useMemo(() => {
    return smoothedOutboundUnsplit.flatMap((line) => splitPolylineAtAntimeridian(line));
  }, [smoothedOutboundUnsplit]);

  const smoothedInbound = useMemo(() => {
    return smoothedInboundUnsplit.flatMap((line) => splitPolylineAtAntimeridian(line));
  }, [smoothedInboundUnsplit]);

  // 3. 실시간 지도 줌 감지를 통한 등간격 화살표 재생성
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());

  useMapEvents({
    zoomend: () => {
      setZoom(map.getZoom());
    },
  });

  const intervalKm = useMemo(() => {
    // 줌 레벨에 따라 화살표 배치 거리를 동적으로 계산 (De-cluttering 실현)
    if (zoom <= MAP_SETTINGS.ZOOM_THRESHOLDS.LOW) {
      return MAP_SETTINGS.ARROW_BASE_INTERVALS.ZOOM_LOW;
    }
    if (zoom <= 5) {
      return MAP_SETTINGS.ARROW_BASE_INTERVALS.ZOOM_MID;
    }
    if (zoom <= 7) {
      return MAP_SETTINGS.ARROW_BASE_INTERVALS.ZOOM_HIGH;
    }
    return MAP_SETTINGS.ARROW_BASE_INTERVALS.ZOOM_DETAIL;
  }, [zoom]);

  // 4. Turf.js 기반 등간격 화살표 실시간 생성 (쪼개지기 전의 곡선을 기준으로 연속 분포 확보)
  const outboundArrows = useMemo(() => {
    return smoothedOutboundUnsplit.flatMap((line) => getEquidistantArrows(line, intervalKm));
  }, [smoothedOutboundUnsplit, intervalKm]);

  const inboundArrows = useMemo(() => {
    return smoothedInboundUnsplit.flatMap((line) => getEquidistantArrows(line, intervalKm));
  }, [smoothedInboundUnsplit, intervalKm]);

  // 4. 호버(Hover) 시 라인 굵기 확장 및 복원용 이벤트 핸들러
  const handleMouseOver = (e, isGlow) => {
    const layer = e.target;
    if (isGlow) {
      layer.setStyle({
        weight: 18,
        opacity: 0.55,
      });
    } else {
      layer.setStyle({
        weight: 5.5,
        opacity: 1.0,
      });
    }
  };

  const handleMouseOut = (e, isGlow, baseColor) => {
    const layer = e.target;
    if (isGlow) {
      layer.setStyle({
        weight: 12,
        opacity: 0.4,
      });
    } else {
      layer.setStyle({
        weight: 3.5,
        opacity: 0.95,
      });
    }
  };

  return (
    <>
      {/* ── Outbound ── */}
      {smoothedOutbound.map((line, i) => (
        <span key={`ob-${i}`}>
          {/* Back Glow Line (호버 인터랙션 포함) */}
          <Polyline
            positions={line}
            pathOptions={{
              color: colors.outGlow,
              weight: 12,
              opacity: 0.4,
              lineJoin: 'round',
              lineCap: 'round',
            }}
            smoothFactor={1.5}
            eventHandlers={{
              mouseover: (e) => handleMouseOver(e, true),
              mouseout: (e) => handleMouseOut(e, true, colors.outGlow),
            }}
          />
          {/* Main Solid Line */}
          <Polyline
            positions={line}
            pathOptions={{
              color: colors.outColor,
              weight: 3.5,
              opacity: 0.95,
              lineJoin: 'round',
              lineCap: 'round',
            }}
            smoothFactor={1.5}
            eventHandlers={{
              mouseover: (e) => handleMouseOver(e, false),
              mouseout: (e) => handleMouseOut(e, false, colors.outColor),
            }}
          >
            {/* 호버 시 마우스를 둥둥 따라다니는 고품격 Sticky 툴팁 */}
            <Tooltip sticky direction="top" className="route-tooltip-ob">
              <div className="flex flex-col gap-0.5">
                <span className="font-bold text-xs">Outbound Leg</span>
                <span className="text-[10px] opacity-75">~{Math.round(lineGeometry.total_distance_km).toLocaleString()} km</span>
              </div>
            </Tooltip>
          </Polyline>
          {/* Flow Dash Animation Overlay (전방 흐름 시각화) */}
          <Polyline
            positions={line}
            pathOptions={{
              color: colors.outArrow,
              weight: 1.8,
              opacity: 0.9,
              lineJoin: 'round',
              lineCap: 'round',
              className: 'route-flow-ob',
            }}
            smoothFactor={1.5}
          />
        </span>
      ))}

      {/* ── Inbound ── */}
      {smoothedInbound.map((line, i) => (
        <span key={`ib-${i}`}>
          {/* Back Glow Line */}
          <Polyline
            positions={line}
            pathOptions={{
              color: colors.inGlow,
              weight: 12,
              opacity: 0.4,
              lineJoin: 'round',
              lineCap: 'round',
            }}
            smoothFactor={1.5}
            eventHandlers={{
              mouseover: (e) => handleMouseOver(e, true),
              mouseout: (e) => handleMouseOut(e, true, colors.inGlow),
            }}
          />
          {/* Main Solid Line */}
          <Polyline
            positions={line}
            pathOptions={{
              color: colors.inColor,
              weight: 3.5,
              opacity: 0.95,
              lineJoin: 'round',
              lineCap: 'round',
              dashArray: '10, 10', // Inbound를 점선(Dashed)으로 렌더링하여 Outbound(실선)와 극적으로 구분
            }}
            smoothFactor={1.5}
            eventHandlers={{
              mouseover: (e) => handleMouseOver(e, false),
              mouseout: (e) => handleMouseOut(e, false, colors.inColor),
            }}
          >
            <Tooltip sticky direction="top" className="route-tooltip-ib">
              <div className="flex flex-col gap-0.5">
                <span className="font-bold text-xs text-red-100">Inbound Leg</span>
                <span className="text-[10px] opacity-75">~{Math.round(lineGeometry.total_distance_km).toLocaleString()} km</span>
              </div>
            </Tooltip>
          </Polyline>
          {/* Flow Dash Animation Overlay (역방향/입항 흐름 시각화) */}
          <Polyline
            positions={line}
            pathOptions={{
              color: colors.inArrow,
              weight: 1.8,
              opacity: 0.9,
              lineJoin: 'round',
              lineCap: 'round',
              className: 'route-flow-ib',
              dashArray: '5, 8', // 애니메이션 오버레이도 점선 형태로 흐르게 유도
            }}
            smoothFactor={1.5}
          />
        </span>
      ))}

      {/* 실시간 줌 레벨에 따라 동적으로 등간격 배치된 고감도 화살표 마커 */}
      <ArrowMarker arrows={outboundArrows} color={colors.outArrow} />
      <ArrowMarker arrows={inboundArrows} color={colors.inArrow} />
    </>
  );
};

export default RouteLayer;
