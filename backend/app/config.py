"""시스템 전역 상수 및 설정 값 정의 모듈.

해상 항로 기하 계산(오프셋, 감쇠, 대원 계산 등)에 관여하는 수학적/비즈니스 상수를 정의합니다.
"""

# ── 해상 항로 기하(GIS) 및 오프셋 상수 ──
GEODETIC_OFFSET_KM: float = 60.0          # Outbound/Inbound 기본 평행 오프셋 분리 거리 (km)
PORT_DECAY_THRESHOLD_KM: float = 150.0   # 기항지 인접 오프셋 감쇠(Decay) 개시 임계 거리 (km)
EARTH_RADIUS_KM: float = 6371.0          # 지구 평균 반경 상수 (km)
SHARP_TURN_THRESHOLD_DEG: float = 60.0   # 회전각 감쇠를 적용할 최소 변침각 (degrees)
