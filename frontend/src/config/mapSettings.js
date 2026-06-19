/**
 * 프론트엔드 해상 지도 시각화 설정 및 상수 정의 모듈.
 * 
 * 맵의 기본 중심점, 줌 레벨별 스타일 임계값, Turf.js 베지어 정밀도,
 * 화살표 배치의 지리적 간격 등을 중앙 집중 제어합니다.
 */

export const MAP_SETTINGS = {
  // ── 지도 초기 기점 및 범위 ──
  DEFAULT_CENTER: [25.0, 140.0],
  DEFAULT_ZOOM: 3,
  MIN_ZOOM: 2,
  MAX_ZOOM: 12,

  // ── 줌 구역 분류 임계값 (CSS 클래스 바인딩용) ──
  ZOOM_THRESHOLDS: {
    LOW: 3,
    MID: 6
  },

  // ── Turf.js Bezier 스플라인 곡선화 파라미터 ──
  BEZIER: {
    RESOLUTION: 12000, // 곡선을 쪼갤 보간 세그먼트 해상도
    SHARPNESS: 0.4     // 0(부드러움)~1(각짐). 육지 침범 방지를 위해 0.4 적용
  },

  // ── 동적 줌 레벨별 기준 화살표 배치 간격 (km) ──
  ARROW_BASE_INTERVALS: {
    ZOOM_LOW: 4000,   // 대양 뷰 (줌 3 이하)에서 화살표를 극도로 드물게 배치하여 깔끔함 유도
    ZOOM_MID: 2200,   // 3 < zoom <= 5
    ZOOM_HIGH: 1000,  // 5 < zoom <= 7
    ZOOM_DETAIL: 500  // 상세 뷰 (zoom > 7)
  },

  // ── 단구간 화살표 배치 제한 ──
  ARROW_MIN_LEG_DISTANCE_KM: 100.0 // 100km 이하 단거리 세그먼트는 화살표 생략
};
