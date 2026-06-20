import * as turf from '@turf/turf';
import { MAP_SETTINGS } from '../../config/mapSettings';

/**
 * 경도를 -180 ~ 180 범위로 정규화합니다.
 */
/**
 * 경도를 -180 ~ 180 범위로 정규화합니다.
 */
export const normalizeLng = (lng) => {
  let l = lng;
  while (l > 180) l -= 360;
  while (l < -180) l += 360;
  return l;
};

export const normalizeLngPacific = (lng) => {
  let l = lng;
  while (l > 330) l -= 360;
  while (l < -30) l += 360;
  return l;
};

/**
 * 두 Turf 포인트 간의 방위각을 날짜변경선 안전 보정을 적용하여 구합니다.
 */
const getCleanBearing = (pt1, pt2) => {
  const c1 = [normalizeLng(pt1.geometry.coordinates[0]), pt1.geometry.coordinates[1]];
  const c2 = [normalizeLng(pt2.geometry.coordinates[0]), pt2.geometry.coordinates[1]];
  return turf.bearing(turf.point(c1), turf.point(c2));
};

/**
 * Turf.js 기반 베지어 스플라인 곡선을 정밀하게 생성합니다.
 * 백엔드에서 unwrapping하여 전달한 연속된 궤적 경도 좌표계를 그대로 보존하여
 * 태평양 대원 항로가 날짜변경선(180도) 부근에서 찢어지거나 지구 반대편을 가로지르는 수평선 버그를 원천 해결합니다.
 *
 * @param {Array<[number, number]>} points - [lat, lng] 좌표 배열
 * @returns {Array<[number, number]>} 스무딩된 [lat, lng] 좌표 배열
 */
export const makeBezierCurve = (points) => {
  if (!points || points.length < 3) return points;
  try {
    // 1. Turf.js 입력을 위해 [lng, lat] 형식으로만 변환 (인위적 180도 정규화 절대 금지)
    const normalizedPoints = points.map(p => [p[1], p[0]]);

    const line = turf.lineString(normalizedPoints);
    const curved = turf.bezierSpline(line, {
      resolution: MAP_SETTINGS.BEZIER.RESOLUTION,
      sharpness: MAP_SETTINGS.BEZIER.SHARPNESS
    });
    
    // 2. 부드러워진 궤적 그대로 [lat, lng] 순으로 변환하여 연속성 완벽 보존
    return curved.geometry.coordinates.map(c => [c[1], c[0]]);
  } catch (e) {
    console.warn("Bezier curve failed, returning original", e);
    return points;
  }
};

/**
 * Turf.js를 활용하여 경로 상에 일정한 지리적 거리 간격으로 등간격 화살표 포인트(방위각 포함)를 반환합니다.
 * 줌 레벨에 따른 기준 간격에 항로의 실거리 비례 지수 감쇠 보정을 적용하여
 * 단구간에서는 화살표 밀도를 자연스럽게 낮추고 대구간은 조밀하게 유지합니다.
 *
 * @param {Array<[number, number]>} points - [lat, lng] 정렬된 좌표 배열
 * @param {number} baseIntervalKm - 줌 레벨별 기준 화살표 간격 (km)
 * @returns {Array<{lat: number, lng: number, bearing: number}>} 화살표 마커 데이터 배열
 */
// Turf.js along 연산 병목 제거를 위한 인메모리 화살표 캐시 맵 선언
const arrowCache = new Map();
const MAX_ARROW_CACHE_SIZE = 200; // 메모리 누수 방지를 위한 캐시 크기 제한

export const getEquidistantArrows = (points, baseIntervalKm = 400) => {
  if (!points || points.length < 2) return [];
  
  // 1. O(1) 초고속 캐시 키 생성 (첫점, 끝점, 배열 길이 및 간격 조합)
  const startPt = points[0];
  const endPt = points[points.length - 1];
  const cacheKey = `${startPt[0].toFixed(4)}_${startPt[1].toFixed(4)}_${endPt[0].toFixed(4)}_${endPt[1].toFixed(4)}_${points.length}_${baseIntervalKm}`;
  
  if (arrowCache.has(cacheKey)) {
    return arrowCache.get(cacheKey);
  }

  try {
    // 2. Turf.js 용 [lng, lat] 변환 (unwrapped 궤적 보존)
    const normalizedPoints = points.map(p => [p[1], p[0]]);

    const line = turf.lineString(normalizedPoints);
    const totalLength = turf.length(line, { units: 'kilometers' });
    
    // 3. 지리적 실거리 $L$에 비례하는 지수 감쇠 화살표 밀도 스케일러 적용
    const adjustedInterval = baseIntervalKm * (1.0 + 3.0 * Math.exp(-totalLength / 600.0));
    const arrowPoints = [];
    
    // 4. 단구간 예외 처리: 구간 총 거리가 조절된 간격보다 짧은 경우 중앙에 1개만 배치
    if (totalLength < adjustedInterval) {
      if (totalLength > MAP_SETTINGS.ARROW_MIN_LEG_DISTANCE_KM) {
        const midDist = totalLength / 2;
        const pt1 = turf.along(line, Math.max(0, midDist - 2), { units: 'kilometers' });
        const ptC = turf.along(line, midDist, { units: 'kilometers' });
        const pt2 = turf.along(line, Math.min(totalLength, midDist + 2), { units: 'kilometers' });
        const bearing = getCleanBearing(pt1, pt2);
        
        arrowPoints.push({
          lat: ptC.geometry.coordinates[1],
          lng: normalizeLng(ptC.geometry.coordinates[0]),
          bearing: bearing
        });
      }
      // 캐시 크기 초과 시 가장 오래된 항목 제거 (LRU 방식)
      if (arrowCache.size >= MAX_ARROW_CACHE_SIZE) {
        const oldestKey = arrowCache.keys().next().value;
        arrowCache.delete(oldestKey);
      }
      arrowCache.set(cacheKey, arrowPoints);
      return arrowPoints;
    }

    // 5. Multi-leg: adjustedInterval 간격으로 균등 배치
    let currentDistance = adjustedInterval / 2;
    while (currentDistance < totalLength) {
      const pt1 = turf.along(line, Math.max(0, currentDistance - 2), { units: 'kilometers' });
      const ptC = turf.along(line, currentDistance, { units: 'kilometers' });
      const pt2 = turf.along(line, Math.min(totalLength, currentDistance + 2), { units: 'kilometers' });
      
      const bearing = getCleanBearing(pt1, pt2);
      
      arrowPoints.push({
        lat: ptC.geometry.coordinates[1],
        lng: normalizeLng(ptC.geometry.coordinates[0]),
        bearing: bearing
      });
      
      currentDistance += adjustedInterval;
    }
    
    // 캐시 크기 초과 시 가장 오래된 항목 제거 (LRU 방식)
    if (arrowCache.size >= MAX_ARROW_CACHE_SIZE) {
      const oldestKey = arrowCache.keys().next().value;
      arrowCache.delete(oldestKey);
    }
    arrowCache.set(cacheKey, arrowPoints);
    return arrowPoints;
  } catch (e) {
    console.warn("Arrow generation failed", e);
    return [];
  }
};

/**
 * Chaikin의 Corner Cutting 알고리즘.
 * 각진 꺾임을 부드러운 곡선으로 변환하며 시작과 끝점은 보존합니다.
 */
export const chaikinSmooth = (points, iterations = 3) => {
  if (!points || points.length < 3) return points;
  let pts = points;
  for (let iter = 0; iter < iterations; iter++) {
    const result = [pts[0]]; 
    for (let i = 0; i < pts.length - 1; i++) {
      const [lat0, lng0] = pts[i];
      const [lat1, lng1] = pts[i + 1];
      result.push([0.75 * lat0 + 0.25 * lat1, 0.75 * lng0 + 0.25 * lng1]);
      result.push([0.25 * lat0 + 0.75 * lat1, 0.25 * lng0 + 0.75 * lng1]);
    }
    result.push(pts[pts.length - 1]); 
    pts = result;
  }
  return pts;
};

/**
 * 노선의 모든 포트 경도를 분석하여 최적의 지도 center 경도를 계산합니다.
 */
export const calcOptimalCenter = (ports) => {
  if (!ports || ports.length === 0) return { lat: 25, lng: 155 };

  const lngs = ports.map(p => parseFloat(p.lng));
  const lats = ports.map(p => parseFloat(p.lat));

  // 1. 대한민국 부산항(129.0도)을 아시아/태평양 기준 앵커로 상정
  const anchorLng = 129.0;
  
  // 2. 모든 기항지 경도를 부산 기점 상대적 최단 경로 연속각으로 시프트 연산
  const shiftedLngs = lngs.map(l => {
    let diff = l - anchorLng;
    while (diff > 180) diff -= 360;
    while (diff < -180) diff += 360;
    return anchorLng + diff;
  });

  const avgLng = shiftedLngs.reduce((sum, val) => sum + val, 0) / shiftedLngs.length;
  let centerLng = normalizeLng(avgLng);

  // 3. 아메리카가 우측에 배치되는 아시아-태평양 중심 뷰(130~180도)를 강제 보장하기 위해 0도 이하 음수 경도 보정
  if (centerLng < 0) {
    centerLng += 360;
  }

  const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;

  return { lat: centerLat, lng: centerLng };
};

/**
 * 두 좌표 간의 bearing(방위각)을 degree로 계산합니다.
 */
export const calcBearing = (from, to) => {
  const toRad = (deg) => (deg * Math.PI) / 180;
  const lat1 = toRad(from[0]);
  const lat2 = toRad(to[0]);
  const dLng = toRad(to[1] - from[1]);
  const x = Math.sin(dLng) * Math.cos(lat2);
  const y =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  const bearing = (Math.atan2(x, y) * 180) / Math.PI;
  return (bearing + 360) % 360;
};

/**
 * 180도 경계가 아닌, 태평양 중심 지도의 대서양 경계(-30도/330도)를 기준으로 
 * 단일 Polyline 좌표 배열을 찢어짐 없이 분할하여 여러 개의 Polyline 형태로 반환합니다.
 * 백엔드에서 통짜 언래핑 및 글로벌 시프트가 끝난 좌표열을 대서양 가장자리에서 정밀하게 쪼개 렌더링합니다.
 *
 * @param {Array<[number, number]>} path - [[lat, lng], ...] 형태의 좌표 리스트 (unwrapped)
 * @returns {Array<Array<[number, number]>>} [[[lat, lng], ...], ...] 형태의 분할된 리스트
 */
export const splitPolylineAtAntimeridian = (path) => {
  if (!path || path.length === 0) return [];

  const multiLine = [];
  let currentSegment = [];

  for (let i = 0; i < path.length; i++) {
    const lat = path[i][0];
    const lng = path[i][1];

    if (currentSegment.length === 0) {
      currentSegment.push([lat, normalizeLngPacific(lng)]);
      continue;
    }

    const [prevLat, prevLngUnwrapped] = path[i - 1];
    const prevLng = normalizeLngPacific(prevLngUnwrapped);
    const currLngNormalized = normalizeLngPacific(lng);

    // 대서양 경계선(-30도/330도) 교차 여부 판별 (정규화된 값의 급격한 점프)
    let diff = currLngNormalized - prevLng;
    let sign = 0;
    let crossLat = null;

    if (diff < -180) { // 동진하여 330도 경계를 넘어 -30도 영역으로
      const totalDist = diff + 360;
      const dist1 = 330 - prevLng;
      const t = totalDist !== 0 ? dist1 / totalDist : 0.5;
      crossLat = prevLat + t * (lat - prevLat);
      sign = 1;
    } else if (diff > 180) { // 서진하여 -30도 경계를 넘어 330도 영역으로
      const totalDist = 360 - diff;
      const dist1 = prevLng - (-30);
      const t = totalDist !== 0 ? dist1 / totalDist : 0.5;
      crossLat = prevLat + t * (lat - prevLat);
      sign = -1;
    }

    if (sign !== 0 && crossLat !== null) {
      // 교차점(330도 / -30도) 추가하고 이전 세그먼트 마감
      const boundaryLngPrev = sign > 0 ? 330.0 : -30.0;
      currentSegment.push([crossLat, boundaryLngPrev]);
      multiLine.push(currentSegment);

      // 반대편(-30도 / 330도)에서 새 세그먼트 시작
      const boundaryLngNext = sign > 0 ? -30.0 : 330.0;
      currentSegment = [
        [crossLat, boundaryLngNext],
        [lat, currLngNormalized]
      ];
    } else {
      currentSegment.push([lat, currLngNormalized]);
    }
  }

  if (currentSegment.length > 0) {
    multiLine.push(currentSegment);
  }

  return multiLine;
};

/**
 * 날짜변경선(180도) 및 태평양 횡단을 고려한 최적 뷰포트 Bounds를 구합니다.
 * 백엔드에서 언래핑된 좌표계를 기준으로 뷰포트가 찢어지지 않도록 패딩을 포함한 경계 좌표를 리턴합니다.
 */
export const getOptimizedBounds = (points) => {
  if (!points || points.length === 0) return null;

  let minLat = 90, maxLat = -90;
  let minLng = Infinity, maxLng = -Infinity;

  points.forEach(([lat, lng]) => {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    
    // 태평양 중심 시프트 정규화 반영
    const normLng = normalizeLngPacific(lng);
    if (normLng < minLng) minLng = normLng;
    if (normLng > maxLng) maxLng = normLng;
  });

  // 지도 주변부 상하좌우 안전 패딩 마진 2도
  return [
    [minLat - 2, minLng - 2],
    [maxLat + 2, maxLng + 2]
  ];
};
