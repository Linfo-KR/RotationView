"""경로 지오메트리 계산 서비스.

searoute 라이브러리를 활용한 해상 경로 계산, 날짜변경선 분리,
Outbound/Inbound 분리, Offset 적용 등의 핵심 비즈니스 로직을 담당합니다.
"""
import hashlib
import json
import logging
import math
from typing import Dict, List, Any, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text
from .routing_service import find_shortest_path

from .port_matcher import get_port_coords, parse_port_rotation, get_port_candidates
from ..utils.geo import (
    haversine,
    normalize_lng,
    normalize_lng_pacific,
    interpolate_antimeridian,
    calc_bearing,
    offset_polyline,
    simplify_polyline,
)


logger = logging.getLogger(__name__)


def generate_great_circle_arc(
    origin: List[float], dest: List[float], num_points: int = 15
) -> List[List[float]]:
    """두 지점 간 최단 경로 방향으로 부드럽게 휜 구면 아치(Great Circle-like Arc) 좌표 목록을 생성합니다.

    아치 높이는 구간 거리에 비례하여 동적으로 계산됩니다.
    - 7,500km 이상: 최대 14도
    - 4,000km 수준: 약 8도
    - 그 이하: 최소 5도

    Args:
        origin (List[float]): 시작 좌표 [lng, lat]
        dest (List[float]): 끝 좌표 [lng, lat]
        num_points (int): 생성할 곡선상 포인트 개수

    Returns:
        List[List[float]]: [[lat, lng], ...] 형식의 곡선 좌표 리스트
    """
    lng1, lat1 = origin
    lng2, lat2 = dest

    # 날짜변경선 기준 최단 경로 방향으로 경도 언래핑
    diff = lng2 - lng1
    while diff > 180:
        lng2 -= 360
        diff = lng2 - lng1
    while diff < -180:
        lng2 += 360
        diff = lng2 - lng1

    # 구간 직선 거리 계산 (동적 아치 높이 결정용)
    direct_dist = haversine(lng1, lat1, lng2, lat2)

    # 거리에 비례하는 동적 아치 높이 (최소 5도, 최대 14도)
    arc_height = max(5.0, min(14.0, direct_dist / 550.0))

    arc_coords = []
    for idx in range(num_points):
        t = idx / (num_points - 1)
        lng = lng1 + t * (lng2 - lng1)
        lat = lat1 + t * (lat2 - lat1)

        # 북/남반구 위상에 따라 둥글게 휘는 아치 오프셋 적용
        mid_lat = (lat1 + lat2) / 2.0
        shift_direction = 1.0 if mid_lat >= -10.0 else -1.0
        # sin 곡선 오프셋 적용 (거리 비례 동적 높이)
        arc_offset = arc_height * math.sin(t * math.pi) * shift_direction

        lat = min(75.0, max(-65.0, lat + arc_offset))
        arc_coords.append([lng, lat])

    return [[c[1], c[0]] for c in arc_coords]


def _determine_region(lng: float, lat: float) -> str:
    """경위도 좌표를 기반으로 해당 항구가 속한 대략적인 해역 리전을 반환합니다."""
    # 경도는 -180 ~ 180 범위로 가정
    l = lng
    while l > 180:
        l -= 360
    while l < -180:
        l += 360

    # 1. 아시아 (동남아, 인도양 동부, 동북아)
    if 60.0 <= l <= 150.0 and -15.0 <= lat <= 60.0:
        return "ASIA"
    # 2. 유럽 & 지중해 & 홍해
    if -15.0 <= l <= 45.0 and 10.0 <= lat <= 75.0:
        return "EUROPE_MED"
    # 3. 서아프리카 / 남아프리카
    if -25.0 <= l <= 20.0 and -35.0 <= lat <= 15.0:
        return "AFRICA_WEST"
    # 4. 남미 동부 (브라질, 아르헨티나 등 대서양 연안)
    if -70.0 <= l <= -35.0 and -60.0 <= lat <= 15.0:
        return "SOUTH_AMERICA_EAST"
    # 5. 남미 서부 (칠레, 페루 등 태평양 연안)
    if -90.0 <= l <= -70.0 and -60.0 <= lat <= 15.0:
        return "SOUTH_AMERICA_WEST"
    # 6. 북미 동부 및 카리브해 (미국 동안, 멕시코만)
    if -100.0 <= l <= -50.0 and 10.0 <= lat <= 60.0:
        return "NORTH_AMERICA_EAST"
    # 7. 북미 서부
    if -140.0 <= l <= -100.0 and 15.0 <= lat <= 60.0:
        return "NORTH_AMERICA_WEST"
    # 8. 오세아니아 (호주, 뉴질랜드, 태평양 도서)
    if (110.0 <= l <= 180.0 or -180.0 <= l <= -130.0) and -50.0 <= lat <= 0.0:
        return "OCEANIA"

    return "UNKNOWN"


def _get_chokepoint_waypoints(lng1: float, lat1: float, lng2: float, lat2: float) -> List[List[float]]:
    """출발지와 도착지 해역 정보를 바탕으로 자동 주입되어야 할 핵심 관문(Chokepoint) 목록을 반환합니다."""
    r1 = _determine_region(lng1, lat1)
    r2 = _determine_region(lng2, lat2)

    waypoints = []

    # 1. ASIA <-> SOUTH_AMERICA_EAST (싱가포르 -> 남미 동안 등)
    # 수에즈 운하 및 지브롤터 경유 체인 자동 주입 (사용자 요청 보편적 로직 반영)
    if r1 == "ASIA" and r2 == "SOUTH_AMERICA_EAST":
        waypoints = [[102.2, 2.2], [32.3, 31.2], [-5.6, 35.9]]
    elif r1 == "SOUTH_AMERICA_EAST" and r2 == "ASIA":
        # 남미 동안 -> 아시아 복귀 (대서양 횡단 수에즈 경유 복귀)
        waypoints = [[-5.6, 35.9], [32.3, 31.2], [102.2, 2.2]]

    # 2. ASIA <-> EUROPE_MED (아시아 <-> 유럽/지중해)
    elif r1 == "ASIA" and r2 == "EUROPE_MED":
        waypoints = [[102.2, 2.2], [32.3, 31.2]]
    elif r1 == "EUROPE_MED" and r2 == "ASIA":
        waypoints = [[32.3, 31.2], [102.2, 2.2]]

    # 3. ASIA <-> AFRICA_WEST (아시아 <-> 서아프리카 - 희망봉 우회)
    elif r1 == "ASIA" and r2 == "AFRICA_WEST":
        waypoints = [[102.2, 2.2], [18.5, -34.8]]
    elif r1 == "AFRICA_WEST" and r2 == "ASIA":
        waypoints = [[18.5, -34.8], [102.2, 2.2]]

    # 4. EUROPE_MED <-> SOUTH_AMERICA_WEST (유럽 <-> 남미 서안 - 파나마 운하 경유)
    elif r1 == "EUROPE_MED" and r2 == "SOUTH_AMERICA_WEST":
        waypoints = [[-5.6, 35.9], [-79.9, 9.3]]
    elif r1 == "SOUTH_AMERICA_WEST" and r2 == "EUROPE_MED":
        waypoints = [[-79.9, 9.3], [-5.6, 35.9]]

    # 5. ASIA <-> NORTH_AMERICA_EAST (아시아 <-> 미국 동안)
    elif r1 == "ASIA" and r2 == "NORTH_AMERICA_EAST":
        # 갈 때는 파나마 운하 경유
        waypoints = [[-79.9, 9.3]]
    elif r1 == "NORTH_AMERICA_EAST" and r2 == "ASIA":
        # 올 때는 대서양 횡단 수에즈 운하 경유 복귀! (USEC6 등 표준 노선도 반영)
        waypoints = [[-5.6, 35.9], [32.3, 31.2], [102.2, 2.2]]

    # 6. EUROPE_MED <-> NORTH_AMERICA_WEST (유럽 <-> 미국 서안 - 파나마 운하 경유)
    elif r1 == "EUROPE_MED" and r2 == "NORTH_AMERICA_WEST":
        waypoints = [[-5.6, 35.9], [-79.9, 9.3]]
    elif r1 == "NORTH_AMERICA_WEST" and r2 == "EUROPE_MED":
        waypoints = [[-79.9, 9.3], [-5.6, 35.9]]

    # 7. ASIA <-> AMERICA_WEST (태평양 횡단 노선 - 태평양 한가운데 통과 보장)
    # 아시아에서 미주 서안(남미 서안, 북미 서안)으로 갈 때 태평양 횡단 안심 지점 주입
    elif r1 == "ASIA" and (r2 == "SOUTH_AMERICA_WEST" or r2 == "NORTH_AMERICA_WEST"):
        waypoints = [[180.0, 15.0]]
    elif (r1 == "SOUTH_AMERICA_WEST" or r1 == "NORTH_AMERICA_WEST") and r2 == "ASIA":
        waypoints = [[180.0, 15.0]]

    # 8. AMERICA_EAST <-> EUROPE_MED (미주 동안 <-> 유럽/지중해 - 지브롤터 해협 통과)
    elif r1 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST") and r2 == "EUROPE_MED":
        waypoints = [[-5.6, 35.9]]
    elif r1 == "EUROPE_MED" and r2 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST"):
        waypoints = [[-5.6, 35.9]]

    # 9. AMERICA_EAST <-> AMERICA_WEST (미주 동안 <-> 미주 서안 - 파나마 운하 해협 통과)
    elif r1 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST") and r2 in ("NORTH_AMERICA_WEST", "SOUTH_AMERICA_WEST"):
        waypoints = [[-79.9, 9.3]]
    elif r1 in ("NORTH_AMERICA_WEST", "SOUTH_AMERICA_WEST") and r2 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST"):
        waypoints = [[-79.9, 9.3]]

    return waypoints


def split_polyline_at_antimeridian(
    simplified_path: List[List[float]],
) -> List[List[List[float]]]:
    """프론트엔드에서 곡선 렌더링하기 직전에 쪼갤 수 있도록
    백엔드에서는 쪼개지 않고 단일 세그먼트로 감싸 반환합니다.
    """
    if not simplified_path:
        return []
    return [simplified_path]


def _build_divided_unwrapped_lines(
    db: Session,
    coords_list: list,
    turn_idx: int,
    apply_offset: bool = True,
    offset_km: float = 60.0,
) -> Tuple[List[List[float]], List[List[float]], List[float], List[List[float]]]:
    """노선의 전체 기항지 목록을 기점(첫 항구) 기준 하나의 누적 척도로 

    순차 언래핑(Sequential Unwrapping) 및 복수 기항 오프셋을 처리하여 
    분할된 Outbound/Inbound 경로와 개별 구간 거리 및 중간 좌표 목록을 반환합니다.
    """
    outbound_raw = []
    inbound_raw = []
    segment_distances = []
    segment_midpoints = []

    # 전체 언래핑 궤적을 순차적으로 담을 버퍼
    full_unwrapped_path = []
    
    # 각 기항지 구간(Leg)별로 계산된 좌표 조각들을 임시 저장
    segments_data = []

    # 중복 구간 오프셋 계산을 위한 방문 횟수 관리 맵
    segment_visit_counts = {}

    for i in range(len(coords_list) - 1):
        origin = coords_list[i]
        dest = coords_list[i + 1]

        lng1, lat1 = origin
        lng2, lat2 = dest

        # 복수 기항 구간 식별을 위한 키 (순서 무관하게 정렬된 위경도 튜플)
        seg_key = tuple(sorted([(round(lng1, 3), round(lat1, 3)), (round(lng2, 3), round(lat2, 3))]))
        visit_count = segment_visit_counts.get(seg_key, 0)
        segment_visit_counts[seg_key] = visit_count + 1

        # 자동 Chokepoints 주입 분석
        chokepoints = _get_chokepoint_waypoints(lng1, lat1, lng2, lat2)

        # 경로 세그먼트 구성 (출발 -> wp1 -> wp2 -> 도착)
        sub_segments = []
        curr = origin
        for wp in chokepoints:
            sub_segments.append((curr, wp))
            curr = wp
        sub_segments.append((curr, dest))

        segment_coords_all = []
        leg_dist = 0.0

        for start, end in sub_segments:
            direct_dist = haversine(start[0], start[1], end[0], end[1])

            # 7,500km 이상의 대양 횡단 구간은 자체 다익스트라 대신 100% 대원 아치 곡선으로 직접 강제 생성 (다익스트라 실패 방지)
            if direct_dist > 7500.0:
                arc_points = generate_great_circle_arc(start, end)
                for lat, lng in arc_points:
                    segment_coords_all.append([lat, lng])
                leg_dist += direct_dist
                continue

            try:
                # DB 노드/링크 기반 자체 다익스트라 최단 경로 계산
                route_coords, route_dist = find_shortest_path(db, start, end)
                segment_coords_all.extend(route_coords)
                leg_dist += route_dist
            except Exception as e:
                # 실패 시 대원 아치 곡선으로 fallback (로깅 포함)
                logger.warning("자체 라우팅 계산 실패 (구간: %s -> %s): %s", start, end, e)
                arc_points = generate_great_circle_arc(start, end)
                for lat, lng in arc_points:
                    segment_coords_all.append([lat, lng])
                leg_dist += direct_dist

        # 🌟 지능형 개별 오프셋(Adaptive Leg Offset) 및 복수 기항 오프셋 적용
        # Outbound와 Inbound, 그리고 중복 방문 순번에 맞춰 평행 이격 처리를 수행합니다.
        avg_lat = (lat1 + lat2) / 2.0
        lat_factor = math.cos(math.radians(avg_lat))
        
        # 중복 방문 횟수에 비례하여 오프셋 거리를 점진적으로 확장하여 겹침 방지 (1배 -> 1.45배 -> 1.9배)
        adjusted_offset_km = offset_km * (1.0 + 0.45 * visit_count)

        if leg_dist < 3000.0:
            adjusted_offset_km = min(adjusted_offset_km, 18.0) * max(0.5, lat_factor)
        else:
            adjusted_offset_km = adjusted_offset_km * max(0.6, lat_factor)

        # Outbound는 우측(+), Inbound는 좌측(-) 방향 이격
        direction = 1.0 if i < turn_idx else -1.0
        offset_val = adjusted_offset_km * direction

        if apply_offset and len(segment_coords_all) >= 2:
            # offset_polyline은 [[lng, lat], ...] 포맷 수신
            lng_lat_line = [[c[1], c[0]] for c in segment_coords_all]
            off_line = offset_polyline(lng_lat_line, offset_val, port_coords=[origin, dest])
            segment_coords_all = [[c[1], c[0]] for c in off_line]

        # 오프셋 및 병합 완료된 선형 상의 정중앙 미드포인트 추출
        if segment_coords_all:
            mid_idx = len(segment_coords_all) // 2
            segment_midpoints.append(segment_coords_all[mid_idx])
        else:
            segment_midpoints.append([avg_lat, (lng1 + lng2) / 2.0])

        segments_data.append(segment_coords_all)
        segment_distances.append(leg_dist)

    # 수집된 모든 세그먼트 좌표 조각들을 단 하나의 기준에서 순차 언래핑 병합
    for i, seg in enumerate(segments_data):
        seg_unwrapped = []
        for lat, lng in seg:
            if len(full_unwrapped_path) > 0:
                prev_lat, prev_lng = full_unwrapped_path[-1]
                diff = lng - prev_lng
                while diff > 180:
                    lng -= 360
                    diff = lng - prev_lng
                while diff < -180:
                    lng += 360
                    diff = lng - prev_lng
            seg_unwrapped.append([lat, lng])
            full_unwrapped_path.append([lat, lng])

        # outbound와 inbound 분기 적재
        # 0 <= i < turn_idx 구간은 outbound, 그 이후는 inbound
        if i < turn_idx:
            outbound_raw.extend(seg_unwrapped)
        else:
            inbound_raw.extend(seg_unwrapped)

    return outbound_raw, inbound_raw, segment_distances, segment_midpoints


# NOTE: _extract_arrow_points() 함수는 제거되었습니다.
# 프론트엔드(RouteLayer.jsx)에서 Turf.js 기반으로 줌 레벨에 따라
# 등간격 화살표를 실시간 생성하므로, 백엔드에서의 중복 searoute 호출은 불필요합니다.
# 이 변경으로 노선당 searoute 호출 횟수가 절반으로 감소합니다.


def _match_port_coordinates(db: Session, port_names: List[str]) -> List[List[float]]:
    """항구 목록에 대응하는 [lng, lat] 좌표 목록을 DB 조회를 통해 최적으로 매칭합니다.

    동명 항구가 있을 경우, 인접한 항구와의 거리를 최소화하는 기점 매칭 및
    역방향 보정 패스를 순차 적용합니다.

    Args:
        db (Session): DB 세션 객체
        port_names (List[str]): 항구 이름 리스트

    Returns:
        List[List[float]]: 최종 실존 항구들의 [lng, lat] 좌표 리스트
    """
    coords_list = []
    candidates_by_index = []

    for name in port_names:
        candidates = get_port_candidates(db, name)
        candidates_by_index.append(candidates)

        if not candidates:
            coords_list.append(None)
            continue

        if len(candidates) == 1:
            coords_list.append([candidates[0][1], candidates[0][0]])
        else:
            prev_active = None
            for prev_coord in reversed(coords_list):
                if prev_coord is not None:
                    prev_active = prev_coord
                    break

            if prev_active:
                best_candidate = min(
                    candidates,
                    key=lambda c: haversine(prev_active[0], prev_active[1], c[1], c[0])
                )
                coords_list.append([best_candidate[1], best_candidate[0]])
            else:
                coords_list.append([candidates[0][1], candidates[0][0]])

    for i in range(len(coords_list) - 2, -1, -1):
        candidates = candidates_by_index[i]
        if not candidates or len(candidates) <= 1:
            continue

        next_active = None
        for next_idx in range(i + 1, len(coords_list)):
            if coords_list[next_idx] is not None:
                next_active = coords_list[next_idx]
                break

        if next_active:
            best_candidate = min(
                candidates,
                key=lambda c: haversine(next_active[0], next_active[1], c[1], c[0])
            )
            coords_list[i] = [best_candidate[1], best_candidate[0]]

    return [c for c in coords_list if c is not None]


def _find_turn_index(coords_list: List[List[float]]) -> int:
    """시작 항구에서 가장 멀리 있는 항구(회차점)의 인덱스를 계산합니다.

    단순 Haversine 최장 거리 기준과 지리적 리전 시퀀스 분석을 병합하여
    출발 리전에서 타겟 리전으로 진입했다가 다시 출발 리전으로 복귀하기 직전의
    최적의 회차점을 판정합니다.

    Args:
        coords_list (List[List[float]]): 항구 좌표 목록 [[lng, lat], ...]

    Returns:
        int: 회차점 기항지 인덱스
    """
    if not coords_list or len(coords_list) < 2:
        return 0

    # 1. 각 좌표별 대략적인 해역 리전 판별
    regions = [_determine_region(lng, lat) for lng, lat in coords_list]
    start_region = regions[0]

    # 2. 리전 변경 시퀀스 추적
    # 출발 리전을 벗어나 다른 리전에 진입했다가, 다시 출발 리전으로 돌아오기 전의 마지막 다른 리전의 인덱스 탐색
    foreign_idx = -1
    return_idx = -1

    for idx, r in enumerate(regions):
        if r != start_region and r != "UNKNOWN":
            foreign_idx = idx
        elif foreign_idx != -1 and r == start_region:
            return_idx = idx
            break

    # 타겟 리전에서 출발 리전으로 돌아오는 구간이 존재하면 그 직전 항구를 회차점으로 선정
    if foreign_idx != -1 and return_idx != -1:
        turn_idx = max(foreign_idx, return_idx - 1)
        if 0 < turn_idx < len(coords_list) - 1:
            return turn_idx

    # 3. Fallback: 기존 Haversine 기준 최장 거리 항구 탐색
    start_lon, start_lat = coords_list[0]
    max_dist = -1.0
    turn_idx = 0
    for i, (lon, lat) in enumerate(coords_list):
        d = haversine(start_lon, start_lat, lon, lat)
        if d > max_dist:
            max_dist = d
            turn_idx = i

    if turn_idx == 0:
        turn_idx = len(coords_list) // 2
    return turn_idx


def _apply_global_lng_shift(outbound_raw: List[List[float]], inbound_raw: List[List[float]]) -> None:
    """경로의 첫 시작점을 태평양 중심 뷰포트 내에 고정시키기 위한 글로벌 경도 평행이동을 적용합니다.

    Args:
        outbound_raw (List[List[float]]): Outbound 경로 좌표 리스트
        inbound_raw (List[List[float]]): Inbound 경로 좌표 리스트
    """
    ref_lng = None
    if outbound_raw:
        ref_lng = outbound_raw[0][1]
    elif inbound_raw:
        ref_lng = inbound_raw[0][1]

    if ref_lng is not None:
        ref_lng_norm = normalize_lng_pacific(ref_lng)
        shift_offset = ref_lng_norm - ref_lng

        if outbound_raw:
            for pt in outbound_raw:
                pt[1] += shift_offset
        if inbound_raw:
            for pt in inbound_raw:
                pt[1] += shift_offset


def _apply_adaptive_offset(
    outbound_raw: List[List[float]],
    inbound_raw: List[List[float]],
    coords_list: List[List[float]],
    total_distance: float,
    offset_km: float,
    apply_offset: bool,
) -> Tuple[List[List[float]], List[List[float]]]:
    """위도별 메르카토르 왜곡 보정 및 노선 거리 비례 가변 오프셋(Adaptive Offset)을 적용합니다.

    Args:
        outbound_raw (List[List[float]]): Outbound 경로 좌표 리스트
        inbound_raw (List[List[float]]): Inbound 경로 좌표 리스트
        coords_list (List[List[float]]): 항구 좌표 목록
        total_distance (float): 총 노선 거리 (km)
        offset_km (float): 기본 오프셋 거리 (km)
        apply_offset (bool): 오프셋 적용 여부

    Returns:
        Tuple[List[List[float]], List[List[float]]]: 오프셋이 적용된 [outbound_raw, inbound_raw]
    """
    if not apply_offset:
        return outbound_raw, inbound_raw

    avg_lat = sum(c[0] for c in coords_list) / len(coords_list) if coords_list else 0.0
    lat_factor = math.cos(math.radians(avg_lat))
    adjusted_offset_km = offset_km

    if total_distance < 3000.0:
        adjusted_offset_km = min(offset_km, 18.0) * max(0.5, lat_factor)
    else:
        adjusted_offset_km = offset_km * max(0.6, lat_factor)

    if outbound_raw:
        lng_lat_line = [[c[1], c[0]] for c in outbound_raw]
        off_line = offset_polyline(lng_lat_line, adjusted_offset_km, port_coords=coords_list)
        outbound_raw = [[c[1], c[0]] for c in off_line]

    if inbound_raw:
        lng_lat_line = [[c[1], c[0]] for c in inbound_raw]
        off_line = offset_polyline(lng_lat_line, -adjusted_offset_km, port_coords=coords_list)
        inbound_raw = [[c[1], c[0]] for c in off_line]

    return outbound_raw, inbound_raw


def _simplify_route_lines(
    outbound_raw: List[List[float]],
    inbound_raw: List[List[float]],
    total_distance: float,
) -> Tuple[List[List[float]], List[List[float]]]:
    """단거리/장거리 여부에 따라 적절한 엡실론 값을 적용하여 경로 선을 RDP 알고리즘으로 단순화합니다.

    Args:
        outbound_raw (List[List[float]]): Outbound 경로 좌표 리스트
        inbound_raw (List[List[float]]): Inbound 경로 좌표 리스트
        total_distance (float): 총 노선 거리 (km)

    Returns:
        Tuple[List[List[float]], List[List[float]]]: 단순화된 [outbound_raw, inbound_raw]
    """
    epsilon_val = 0.1
    if total_distance < 3000.0:
        epsilon_val = 0.03

    if outbound_raw:
        outbound_raw = simplify_polyline(outbound_raw, epsilon=epsilon_val)
    if inbound_raw:
        inbound_raw = simplify_polyline(inbound_raw, epsilon=epsilon_val)

    return outbound_raw, inbound_raw


def calculate_route_geometry(
    db: Session,
    port_rotation: str,
    apply_offset: bool = True,
    offset_km: float = 60.0,
) -> Dict[str, Any]:
    """해상 노선의 전체 지오메트리를 계산합니다.

    Args:
        db (Session): DB 세션
        port_rotation (str): 항구 로테이션 문자열 (예: "CNSHA-USLAX-KRPUS")
        apply_offset (bool): 경로 병렬 이격(offset) 적용 여부
        offset_km (float): 이격 거리 (km)

    Returns:
        Dict[str, Any]: {outbound: GeoJSON, inbound: GeoJSON, ...} 형태의 결과 딕셔너리
    """
    port_names = parse_port_rotation(port_rotation)

    # 1단계: 항구 매칭
    coords_list = _match_port_coordinates(db, port_names)

    if len(coords_list) < 2:
        return {
            "outbound": [], "inbound": [],
            "outbound_arrows": [], "inbound_arrows": [],
            "total_distance_km": 0,
            "segment_distances": [],
        }

    # 2단계: 회차점 탐색
    turn_idx = _find_turn_index(coords_list)

    # 3단계: Outbound/Inbound 분할 해상 경로 생성 및 개별 구간 거리 연산
    outbound_raw, inbound_raw, segment_distances, segment_midpoints = _build_divided_unwrapped_lines(
        db, coords_list, turn_idx, apply_offset, offset_km
    )

    # 4단계: 글로벌 경도 보정
    _apply_global_lng_shift(outbound_raw, inbound_raw)

    # 미드포인트에도 동일한 shift_offset 적용
    ref_lng = None
    if outbound_raw:
        ref_lng = outbound_raw[0][1]
    elif inbound_raw:
        ref_lng = inbound_raw[0][1]

    if ref_lng is not None:
        ref_lng_norm = normalize_lng_pacific(ref_lng)
        shift_offset = ref_lng_norm - ref_lng
        for pt in segment_midpoints:
            pt[1] += shift_offset

    # 5단계: 총 거리 계산
    total_distance = sum(segment_distances)

    # 6단계: 경로 단순화
    outbound_raw, inbound_raw = _simplify_route_lines(outbound_raw, inbound_raw, total_distance)

    # 7단계: 날짜변경선 분할 패키징
    outbound_lines = split_polyline_at_antimeridian(outbound_raw)
    inbound_lines = split_polyline_at_antimeridian(inbound_raw)

    return {
        "outbound": outbound_lines,
        "inbound": inbound_lines,
        "outbound_arrows": [],
        "inbound_arrows": [],
        "total_distance_km": round(total_distance, 1),
        "segment_distances": [round(d, 1) for d in segment_distances],
        "segment_midpoints": segment_midpoints,
    }


def _hash_rotation(port_rotation: str) -> str:
    """port_rotation의 MD5 해시 생성"""
    return hashlib.md5(port_rotation.encode('utf-8')).hexdigest()


def get_cached_geometry(db: Session, route_idx: int, port_rotation: str) -> Optional[Dict]:
    """캐시 테이블에서 지오메트리 조회"""
    current_hash = _hash_rotation(port_rotation)
    try:
        result = db.execute(
            text(
                'SELECT outbound_geojson, inbound_geojson, arrow_points, '
                'total_distance_km, port_rotation_hash '
                'FROM "TB_ROUTE_GEOMETRY" WHERE route_idx = :idx'
            ),
            {"idx": route_idx}
        ).fetchone()

        if result and result[4] == current_hash:
            return {
                "outbound": json.loads(result[0]) if result[0] else [],
                "inbound": json.loads(result[1]) if result[1] else [],
                **(json.loads(result[2]) if result[2] else {
                    "outbound_arrows": [], "inbound_arrows": []
                }),
                "total_distance_km": result[3] or 0,
            }
    except Exception as e:
        logger.warning("지오메트리 캐시 조회 실패 (route_idx=%d): %s", route_idx, e)

    return None


def save_geometry_cache(
    db: Session, route_idx: int, port_rotation: str, geometry: Dict
) -> None:
    """계산된 지오메트리를 캐시 테이블에 저장"""
    rotation_hash = _hash_rotation(port_rotation)
    arrow_data = json.dumps({
        "outbound_arrows": geometry.get("outbound_arrows", []),
        "inbound_arrows": geometry.get("inbound_arrows", []),
        "segment_distances": geometry.get("segment_distances", []),
        "segment_midpoints": geometry.get("segment_midpoints", []),
    })

    try:
        db.execute(
            text(
                'INSERT INTO "TB_ROUTE_GEOMETRY" '
                '(route_idx, outbound_geojson, inbound_geojson, arrow_points, '
                'total_distance_km, port_rotation_hash, computed_at) '
                'VALUES (:idx, :ob, :ib, :arrows, :dist, :hash, NOW()) '
                'ON CONFLICT (route_idx) DO UPDATE SET '
                'outbound_geojson = :ob, inbound_geojson = :ib, '
                'arrow_points = :arrows, total_distance_km = :dist, '
                'port_rotation_hash = :hash, computed_at = NOW()'
            ),
            {
                "idx": route_idx,
                "ob": json.dumps(geometry.get("outbound", [])),
                "ib": json.dumps(geometry.get("inbound", [])),
                "arrows": arrow_data,
                "dist": geometry.get("total_distance_km", 0),
                "hash": rotation_hash,
            }
        )
        db.commit()
    except Exception as e:
        logger.warning("지오메트리 캐시 저장 실패 (route_idx=%d): %s", route_idx, e)
        db.rollback()


def get_or_compute_geometry(
    db: Session, route_idx: int, port_rotation: str
) -> Dict[str, Any]:
    """캐시 확인 후 없으면 계산하여 캐시에 저장"""
    cached = get_cached_geometry(db, route_idx, port_rotation)
    if cached is not None:
        return cached

    geometry = calculate_route_geometry(db, port_rotation)
    save_geometry_cache(db, route_idx, port_rotation, geometry)
    return geometry
