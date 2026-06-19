"""지리 유틸리티 함수 모음.

해상 경로 계산에 필요한 거리, 경도 정규화, 날짜변경선 보간, 구면 오프셋 및 방위각 정위 함수를 제공합니다.
"""
import math
from typing import Tuple, Optional, List

from ..config import (
    EARTH_RADIUS_KM,
    GEODETIC_OFFSET_KM,
    PORT_DECAY_THRESHOLD_KM,
    SHARP_TURN_THRESHOLD_DEG,
)


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """두 지점 간 대원 거리를 km 단위로 계산합니다.

    Args:
        lon1: 출발지 경도 (degrees)
        lat1: 출발지 위도 (degrees)
        lon2: 도착지 경도 (degrees)
        lat2: 도착지 위도 (degrees)

    Returns:
        두 지점 간 거리 (km)
    """
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return c * EARTH_RADIUS_KM


def normalize_lng(lng: float) -> float:
    """경도를 -180 ~ 180 범위로 정규화합니다.

    Args:
        lng: 입력 경도

    Returns:
        -180 ~ 180 범위로 정규화된 경도
    """
    while lng > 180:
        lng -= 360
    while lng < -180:
        lng += 360
    return lng


def normalize_lng_pacific(lng: float) -> float:
    """경도를 태평양 중심 뷰포트 기준인 -30 ~ 330 범위로 정규화합니다.

    Args:
        lng: 입력 경도

    Returns:
        -30 ~ 330 범위로 정규화된 경도
    """
    while lng > 330.0:
        lng -= 360.0
    while lng < -30.0:
        lng += 360.0
    return lng


def interpolate_antimeridian(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> Tuple[Optional[float], int]:
    """두 점 사이에서 날짜변경선(±180°) 교차점의 위도를 선형 보간으로 계산합니다.

    Args:
        lat1: 시작점 위도
        lng1: 시작점 경도 (-180~180 정규화 필수)
        lat2: 끝점 위도
        lng2: 끝점 경도 (-180~180 정규화 필수)

    Returns:
        (crossing_lat, sign) 튜플.
        sign = 1이면 동진(+180 → -180), -1이면 서진(-180 → +180).
        교차가 없으면 (None, 0).
    """
    diff = lng2 - lng1
    if diff < -180:  # 동진 (e.g. 175 -> -175, diff = -350)
        total_dist = diff + 360  # e.g. 10
        dist1 = 180 - lng1       # 180까지의 거리
        t = dist1 / total_dist if total_dist != 0 else 0.5
        cross_lat = lat1 + t * (lat2 - lat1)
        return cross_lat, 1
    elif diff > 180:  # 서진 (e.g. -175 -> 175, diff = 350)
        total_dist = 360 - diff  # e.g. 10
        dist1 = lng1 - (-180)    # -180까지의 거리
        t = dist1 / total_dist if total_dist != 0 else 0.5
        cross_lat = lat1 + t * (lat2 - lat1)
        return cross_lat, -1
    return None, 0


def calc_bearing(coord1: list, coord2: list) -> float:
    """두 좌표 간 방위각(bearing)을 대원 구면 기준 및 날짜변경선 정위 보정을 거쳐 계산합니다.

    unwrapping된 상태의 좌표 차이에서 발생할 수 있는 극적 부호 역전을 방지합니다.

    Args:
        coord1: [lng, lat] 형식의 시작 좌표
        coord2: [lng, lat] 형식의 끝 좌표

    Returns:
        방위각 (degrees, 0~360)
    """
    lng1, lat1 = math.radians(coord1[0]), math.radians(coord1[1])
    lng2, lat2 = math.radians(coord2[0]), math.radians(coord2[1])
    d_lng = lng2 - lng1

    # 날짜변경선 언래핑 경계면에서의 방위각 뒤틀림(180도 반전) 방지를 위한 구면 최단 경로 보정
    while d_lng > math.pi:
        d_lng -= 2 * math.pi
    while d_lng < -math.pi:
        d_lng += 2 * math.pi

    x = math.sin(d_lng) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lng)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def calculate_destination_point(
    lng: float, lat: float, bearing: float, distance_km: float, normalize: bool = True
) -> Tuple[float, float]:
    """구면 삼각법(Great Circle Destination)을 활용하여 주어진 점으로부터 특정 방위각 및 거리만큼 이동한 지점의 좌표를 계산합니다.

    Args:
        lng: 출발지 경도 (degrees)
        lat: 출발지 위도 (degrees)
        bearing: 방위각 (degrees, 0~360)
        distance_km: 이동할 구면 거리 (km)
        normalize: 경도를 -180~180 범위로 정규화할지 여부

    Returns:
        이동 후의 (lng, lat) 좌표 튜플 (degrees)
    """
    ad = distance_km / EARTH_RADIUS_KM
    lat_rad = math.radians(lat)
    lng_rad = math.radians(lng)
    bearing_rad = math.radians(bearing)

    lat_out = math.asin(
        math.sin(lat_rad) * math.cos(ad)
        + math.cos(lat_rad) * math.sin(ad) * math.cos(bearing_rad)
    )
    lng_out = lng_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(ad) * math.cos(lat_rad),
        math.cos(ad) - math.sin(lat_rad) * math.sin(lat_out),
    )

    lng_deg = math.degrees(lng_out)
    if normalize:
        lng_deg = normalize_lng(lng_deg)
    return lng_deg, math.degrees(lat_out)


def offset_polyline(
    coords: List[List[float]],
    offset_km: float = GEODETIC_OFFSET_KM,
    port_coords: Optional[List[List[float]]] = None,
) -> List[List[float]]:
    """Polyline 좌표 리스트에 수직 방향 geodetic offset을 적용하여 왜곡 없는 평행 경로를 생성합니다.

    기항지 근처에서는 오프셋 거리를 부드럽게 감쇠(Decay)시켜 기항지 중심을 통과하도록 유도하고,
    급격한 회전 구간(Heading Change)에서도 꼬임 방지를 위해 오프셋 크기를 조절합니다.

    Args:
        coords: [[lng, lat], ...] 형식의 좌표 리스트 (searoute/unwrap 적용본)
        offset_km: offset 거리 (km). 양수=오른쪽, 음수=왼쪽
        port_coords: [[lng, lat], ...] 형식의 기항지 좌표 리스트

    Returns:
        오프셋이 지리학적으로 정밀하게 반영된 새로운 좌표 리스트 [[lng, lat], ...]
    """
    if not coords or len(coords) < 2:
        return coords

    offset_coords = []
    n = len(coords)

    for i in range(n):
        # 1. 현재 포인트에서의 진행 방향 방위각 계산
        if i == 0:
            bearing = calc_bearing(coords[0], coords[1])
            bearing_next = bearing
            bearing_prev = bearing
        elif i == n - 1:
            bearing = calc_bearing(coords[i - 1], coords[i])
            bearing_next = bearing
            bearing_prev = bearing
        else:
            bearing_prev = calc_bearing(coords[i - 1], coords[i])
            bearing_next = calc_bearing(coords[i], coords[i + 1])
            # 두 구간 중간에서의 평균 흐름 각도를 잡기 위해 중간 방위각 활용
            bearing = calc_bearing(coords[i - 1], coords[i + 1])

        # 2. 수직 오프셋 방향 방위각 계산 (양수 = 오른쪽, 음수 = 왼쪽)
        if offset_km >= 0:
            offset_bearing = (bearing + 90.0) % 360.0
            base_offset = offset_km
        else:
            offset_bearing = (bearing - 90.0) % 360.0
            base_offset = -offset_km

        # 3. 꺾임각에 따른 오프셋 축소 (Heading Change Attenuation)
        if 0 < i < n - 1:
            alpha = abs(bearing_next - bearing_prev)
            if alpha > 180.0:
                alpha = 360.0 - alpha
            # 설정한 급커브 최소 기준각을 충족할 때 감쇠 활성화
            if alpha >= SHARP_TURN_THRESHOLD_DEG:
                attenuation_factor = math.cos(math.radians(alpha / 2.0))
                base_offset *= max(0.0, attenuation_factor)

        # 4. 기항지 부근에서의 오프셋 감쇠 (Offset Decay near Ports)
        if port_coords:
            min_dist = float("inf")
            for px, py in port_coords:
                dist = haversine(coords[i][0], coords[i][1], px, py)
                if dist < min_dist:
                    min_dist = dist

            if min_dist < PORT_DECAY_THRESHOLD_KM:
                decay_factor = min_dist / PORT_DECAY_THRESHOLD_KM
                base_offset *= decay_factor

        # 5. 구면 좌표 적용을 통한 오프셋 위치 획득
        if base_offset > 0.01:
            lng_off, lat_off = calculate_destination_point(
                coords[i][0], coords[i][1], offset_bearing, base_offset, normalize=False
            )
            offset_coords.append([lng_off, lat_off])
        else:
            # 오프셋이 사실상 0이면 원본 좌표 보존 (기항지 스냅 완벽 작동)
            offset_coords.append(list(coords[i]))

    return offset_coords


def simplify_polyline(
    coords: List[List[float]], epsilon: float = 0.1
) -> List[List[float]]:
    """Ramer-Douglas-Peucker 알고리즘을 사용하여 해상 경로 좌표들을 지능적으로 단순화(간소화)합니다.

    경로의 주요 꺾임점만 유지함으로써, 평행 오프셋 계산 시의 꼬임 현상을 방지하고 부드러운 시각화를 돕습니다.

    Args:
        coords: [[lng, lat], ...] 형식의 좌표 리스트
        epsilon: 단순화 허용 오차 임계값

    Returns:
        단순화된 좌표 리스트 [[lng, lat], ...]
    """
    if len(coords) < 3:
        return coords

    def get_sq_seg_dist(
        p: List[float], p1: List[float], p2: List[float]
    ) -> float:
        x, y = p[0], p[1]
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        dx = x2 - x1
        dy = y2 - y1
        if dx != 0 or dy != 0:
            t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
            if t > 1:
                x1, y1 = x2, y2
            elif t > 0:
                x1 += dx * t
                y1 += dy * t
        dx = x - x1
        dy = y - y1
        return dx * dx + dy * dy

    dmax = 0.0
    index = 0
    end = len(coords) - 1
    for i in range(1, end):
        d = get_sq_seg_dist(coords[i], coords[0], coords[end])
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon * epsilon:
        results1 = simplify_polyline(coords[: index + 1], epsilon)
        results2 = simplify_polyline(coords[index:], epsilon)
        return results1[:-1] + results2
    else:
        return [coords[0], coords[end]]
