"""경로 지오메트리 계산 서비스.

searoute 라이브러리를 활용한 해상 경로 계산, 날짜변경선 분리,
Outbound/Inbound 분리, Offset 적용, 화살표 중간점 추출 등의 핵심 비즈니스 로직을 담당합니다.
"""
import hashlib
import json
import math
from typing import Dict, List, Any, Optional, Tuple

import searoute as sr
from sqlalchemy.orm import Session
from sqlalchemy import text

from .port_matcher import get_port_coords, parse_port_rotation
from ..utils.geo import (
    haversine,
    normalize_lng,
    normalize_lng_pacific,
    interpolate_antimeridian,
    calc_bearing,
    offset_polyline,
    simplify_polyline,
)


def generate_great_circle_arc(
    origin: List[float], dest: List[float], num_points: int = 15
) -> List[List[float]]:
    """두 지점 간 최단 경로 방향으로 부드럽게 휜 구면 아치(Great Circle-like Arc) 좌표 목록을 생성합니다.

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

    arc_coords = []
    for idx in range(num_points):
        t = idx / (num_points - 1)
        lng = lng1 + t * (lng2 - lng1)
        lat = lat1 + t * (lat2 - lat1)

        # 북/남반구 위상에 따라 둥글게 휘는 아치 오프셋 적용
        # 중간 영역으로 갈수록 최대 14도 시프트
        mid_lat = (lat1 + lat2) / 2.0
        shift_direction = 1.0 if mid_lat >= -10.0 else -1.0
        # sin 곡선 오프셋 적용
        arc_offset = 14.0 * math.sin(t * math.pi) * shift_direction

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

    # 8. AMERICA_EAST <-> EUROPE_MED (미주 동안 <-> 유럽/지중해 - 지브롤터 필수 통과)
    elif r1 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST") and r2 == "EUROPE_MED":
        waypoints = [[-5.6, 35.9]]
    elif r1 == "EUROPE_MED" and r2 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST"):
        waypoints = [[-5.6, 35.9]]

    # 9. AMERICA_EAST <-> AMERICA_WEST (미주 동안 <-> 미주 서안 - 파나마 운하 필수 통과)
    elif r1 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST") and r2 in ("NORTH_AMERICA_WEST", "SOUTH_AMERICA_WEST"):
        waypoints = [[-79.9, 9.3]]
    elif r1 in ("NORTH_AMERICA_WEST", "SOUTH_AMERICA_WEST") and r2 in ("NORTH_AMERICA_EAST", "SOUTH_AMERICA_EAST"):
        waypoints = [[-79.9, 9.3]]

    return waypoints


def split_polyline_at_antimeridian(
    simplified_path: List[List[float]],
) -> List[List[List[float]]]:
    """[스플릿 로직 제거] 프론트엔드가 곡선 피팅 후 렌더링하기 직전에 쪼갤 수 있도록 

    백엔드에서는 쪼개지 않고 단일 세그먼트로 감싸 반환합니다.
    """
    if not simplified_path:
        return []
    return [simplified_path]


def _build_divided_unwrapped_lines(
    coords_list: list, turn_idx: int
) -> Tuple[List[List[float]], List[List[float]]]:
    """노선의 전체 기항지 목록을 기점(첫 항구) 기준 하나의 누적 척도로 

    순차 언래핑(Sequential Unwrapping)을 수행하여, Outbound와 Inbound 간의 
    경도 스케일 불일치(찢어짐)를 원천 차단하고 분할하여 반환합니다.
    """
    outbound_raw = []
    inbound_raw = []

    # 전체 언래핑 궤적을 순차적으로 담을 버퍼
    full_unwrapped_path = []
    
    # 각 기항지 구간(Leg)별로 계산된 좌표 조각들을 임시 저장
    segments_data = []

    for i in range(len(coords_list) - 1):
        origin = coords_list[i]
        dest = coords_list[i + 1]

        lng1, lat1 = origin
        lng2, lat2 = dest

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
        for start, end in sub_segments:
            direct_dist = haversine(start[0], start[1], end[0], end[1])

            # 4,500km 이상의 대양 횡단 구간은 searoute 연산을 완전히 스킵하고 100% 대원 아치 곡선으로 직접 강제 생성 (다익스트라 실패 방지)
            if direct_dist > 4500.0:
                arc_points = generate_great_circle_arc(start, end)
                for lat, lng in arc_points:
                    segment_coords_all.append([lat, lng])
                continue

            try:
                segment_geom = sr.searoute(start, end, append_orig_dest=True)
                if not segment_geom:
                    # searoute 실패 시 대원 아치 곡선으로 fallback
                    arc_points = generate_great_circle_arc(start, end)
                    for lat, lng in arc_points:
                        segment_coords_all.append([lat, lng])
                    continue

                geom = segment_geom.get('geometry') or (
                    segment_geom.get('features', [{}])[0].get('geometry')
                    if segment_geom.get('features') else None
                )
                if not geom:
                    continue

                segment_coords = []
                if geom['type'] == 'LineString':
                    segment_coords = geom['coordinates']
                elif geom['type'] == 'MultiLineString':
                    for line in geom['coordinates']:
                        segment_coords.extend(line)

                # searoute 결과 궤적의 누적 해상 거리 계산
                route_dist = 0.0
                if len(segment_coords) >= 2:
                    for idx in range(len(segment_coords) - 1):
                        route_dist += haversine(
                            segment_coords[idx][0], segment_coords[idx][1],
                            segment_coords[idx + 1][0], segment_coords[idx + 1][1]
                        )

                # 오차 보정 판별 조건:
                # - searoute 최단 경로 거리가 실제 최단 구면 거리보다 1.4배 이상 긴 경우 (방향 거꾸로 돎)
                is_wrong_dir = (direct_dist > 2000.0 and route_dist > direct_dist * 1.4)

                if is_wrong_dir:
                    arc_points = generate_great_circle_arc(start, end)
                    for lat, lng in arc_points:
                        segment_coords_all.append([lat, lng])
                else:
                    # 정상적인 해상 궤적 삽입 (c[1]=lat, c[0]=lng)
                    for c in segment_coords:
                        segment_coords_all.append([c[1], c[0]])
            except Exception:
                # 실패 시 대원 아치 곡선으로 fallback
                arc_points = generate_great_circle_arc(start, end)
                for lat, lng in arc_points:
                    segment_coords_all.append([lat, lng])

        segments_data.append(segment_coords_all)

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

    return outbound_raw, inbound_raw


def _extract_arrow_points(coord_slice: list) -> list:
    """각 기항지 간 구간(Leg)의 중간점 좌표와 방위각을 추출합니다."""
    arrows = []
    for i in range(len(coord_slice) - 1):
        origin = coord_slice[i]
        dest = coord_slice[i + 1]
        try:
            segment_geom = sr.searoute(origin, dest, append_orig_dest=True)
            if not segment_geom:
                continue

            geom = segment_geom.get('geometry') or (
                segment_geom.get('features', [{}])[0].get('geometry')
                if segment_geom.get('features') else None
            )
            if not geom:
                continue

            coords = []
            if geom['type'] == 'LineString':
                coords = geom['coordinates']
            elif geom['type'] == 'MultiLineString':
                for line in geom['coordinates']:
                    coords.extend(line)

            if len(coords) >= 2:
                mid_idx = len(coords) // 2
                mid_point = coords[mid_idx]
                next_idx = min(mid_idx + 1, len(coords) - 1)
                bearing = calc_bearing(coords[mid_idx], coords[next_idx])
                arrows.append({
                    "lat": mid_point[1],
                    "lng": normalize_lng(mid_point[0]),
                    "bearing": bearing,
                })
        except Exception:
            pass

    return arrows


def calculate_route_geometry(
    db: Session,
    port_rotation: str,
    apply_offset: bool = True,
    offset_km: float = 60.0,
) -> Dict[str, Any]:
    """해상 노선의 전체 지오메트리를 계산합니다."""
    port_names = parse_port_rotation(port_rotation)

    coords_list = []
    for name in port_names:
        lat, lng = get_port_coords(db, name)
        if lat is not None and lng is not None:
            coords_list.append([lng, lat])

    if len(coords_list) < 2:
        return {
            "outbound": [], "inbound": [],
            "outbound_arrows": [], "inbound_arrows": [],
            "total_distance_km": 0,
        }

    start_lon, start_lat = coords_list[0]
    max_dist = -1
    turn_idx = 0
    for i, (lon, lat) in enumerate(coords_list):
        d = haversine(start_lon, start_lat, lon, lat)
        if d > max_dist:
            max_dist = d
            turn_idx = i

    if turn_idx == 0:
        turn_idx = len(coords_list) // 2

    outbound_slice = coords_list[: turn_idx + 1]
    inbound_slice = coords_list[turn_idx:]

    # A. 전체 궤적에 대해 통짜 순차 언래핑을 적용하고 분리
    outbound_raw, inbound_raw = _build_divided_unwrapped_lines(coords_list, turn_idx)

    # 🌟 글로벌 경도 평행이동 보정 (Global Longitude Shift) 적용
    # 경로의 첫 시작점을 [-180, 180] 범위 내에 강제 안착시키고, 
    # 나머지 연속된 좌표들도 그 기점에 맞춰 메인 지도 뷰포트 내에 고정되게 함.
    ref_lng = None
    if outbound_raw:
        ref_lng = outbound_raw[0][1]
    elif inbound_raw:
        ref_lng = inbound_raw[0][1]

    if ref_lng is not None:
        ref_lng_norm = normalize_lng_pacific(ref_lng)
        shift_offset = ref_lng_norm - ref_lng
        
        # outbound 및 inbound 전체 좌표 시프트 적용
        if outbound_raw:
            for pt in outbound_raw:
                pt[1] += shift_offset
        if inbound_raw:
            for pt in inbound_raw:
                pt[1] += shift_offset

    # 총 노선 거리(단거리 피더 여부 판단 및 성능 최적화용) 계산
    total_distance = 0.0
    for i in range(len(coords_list) - 1):
        total_distance += haversine(
            coords_list[i][0], coords_list[i][1],
            coords_list[i + 1][0], coords_list[i + 1][1]
        )

    # 지능형 오프셋(Adaptive Offsetting): 단거리 로컬 피더는 육지 관통/겹침 방지를 위해 오프셋 축소
    adjusted_offset_km = offset_km
    if total_distance < 3000.0:
        adjusted_offset_km = min(offset_km, 18.0)

    # B. 언래핑 및 쉬프트가 완벽히 완료된 상태에서 꼬임 없이 오프셋 평행선을 연산
    if apply_offset:
        if outbound_raw:
            lng_lat_line = [[c[1], c[0]] for c in outbound_raw]
            off_line = offset_polyline(lng_lat_line, adjusted_offset_km, port_coords=coords_list)
            outbound_raw = [[c[1], c[0]] for c in off_line]

        if inbound_raw:
            lng_lat_line = [[c[1], c[0]] for c in inbound_raw]
            off_line = offset_polyline(lng_lat_line, -adjusted_offset_km, port_coords=coords_list)
            inbound_raw = [[c[1], c[0]] for c in off_line]

    # C. 오프셋이 완벽하게 끝난 선에 대해 RDP 단순화 수행 (로컬 피더는 곡선 보존을 위해 epsilon 축소)
    epsilon_val = 0.1
    if total_distance < 3000.0:
        epsilon_val = 0.03

    if outbound_raw:
        outbound_raw = simplify_polyline(outbound_raw, epsilon=epsilon_val)
    if inbound_raw:
        inbound_raw = simplify_polyline(inbound_raw, epsilon=epsilon_val)

    # D. 마지막에 날짜변경선을 기준으로 쪼개는 대신 단일 세그먼트로 감싸서 넘김
    outbound_lines = split_polyline_at_antimeridian(outbound_raw)
    inbound_lines = split_polyline_at_antimeridian(inbound_raw)

    outbound_arrows = _extract_arrow_points(outbound_slice)
    inbound_arrows = _extract_arrow_points(inbound_slice)

    return {
        "outbound": outbound_lines,
        "inbound": inbound_lines,
        "outbound_arrows": outbound_arrows,
        "inbound_arrows": inbound_arrows,
        "total_distance_km": round(total_distance, 1),
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
    except Exception:
        pass

    return None


def save_geometry_cache(
    db: Session, route_idx: int, port_rotation: str, geometry: Dict
) -> None:
    """계산된 지오메트리를 캐시 테이블에 저장"""
    rotation_hash = _hash_rotation(port_rotation)
    arrow_data = json.dumps({
        "outbound_arrows": geometry.get("outbound_arrows", []),
        "inbound_arrows": geometry.get("inbound_arrows", []),
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
    except Exception:
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
