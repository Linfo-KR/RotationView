import logging
import heapq
import json
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from .. import models
from ..utils.geo import haversine

logger = logging.getLogger(__name__)

# 인메모리 라우팅 그래프 캐시
_graph: Dict[int, List[Tuple[int, float, int]]] = {}  # source_id -> [(target_id, weight, link_id)]
_nodes: Dict[int, Tuple[float, float]] = {}  # node_id -> (lng, lat)
_links: Dict[int, Dict[str, Any]] = {}  # link_id -> link_properties
_graph_loaded = False


def load_graph(db: Session, force_reload: bool = False) -> None:
    """DB로부터 해상 네트워크 노드 및 활성 링크 데이터를 메모리에 적재합니다."""
    global _graph, _nodes, _links, _graph_loaded
    if _graph_loaded and not force_reload:
        return

    logger.info("Loading routing graph from DB...")
    try:
        # 노드 로딩
        db_nodes = db.query(models.RouteNode).all()
        _nodes = {n.node_id: (n.lng, n.lat) for n in db_nodes}

        # 링크 로딩
        db_links = db.query(models.RouteLink).filter(models.RouteLink.is_active == True).all()
        
        # 그래프 인접 리스트 구성
        _graph = {}
        _links = {}
        for l in db_links:
            _links[l.link_id] = {
                "source": l.source_node,
                "target": l.target_node,
                "distance": l.distance_km,
                "weight": l.distance_km * l.weight_modifier,
                "path_coords": l.path_coords
            }

            # 양방향 그래프 구성 (해상은 기본적으로 양방향 통행 가능)
            weight = l.distance_km * l.weight_modifier
            if l.source_node not in _graph:
                _graph[l.source_node] = []
            if l.target_node not in _graph:
                _graph[l.target_node] = []

            _graph[l.source_node].append((l.target_node, weight, l.link_id))
            _graph[l.target_node].append((l.source_node, weight, l.link_id))

        _graph_loaded = True
        logger.info(f"Routing graph loaded successfully. Nodes: {len(_nodes)}, Links: {len(_links)}")
    except Exception as e:
        logger.error(f"Failed to load routing graph: {e}", exc_info=True)


def _find_nearest_node(lng: float, lat: float) -> Optional[int]:
    """주어진 좌표 [lng, lat]와 가장 가까운 해상 노드 ID를 반환합니다."""
    if not _nodes:
        return None

    nearest_node_id = None
    min_dist = float('inf')

    # 단순 전체 스캔 (노드 개수가 수천 개 수준이라 파이썬 루프로 0.1ms 소요로 충분히 빠름)
    for node_id, (n_lng, n_lat) in _nodes.items():
        d = haversine(lng, lat, n_lng, n_lat)
        if d < min_dist:
            min_dist = d
            nearest_node_id = node_id

    return nearest_node_id


def ccw(A: List[float], B: List[float], C: List[float]) -> bool:
    """세 지점 A, B, C가 반시계 방향(CCW) 관계에 있는지 판별합니다."""
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def intersect(A: List[float], B: List[float], C: List[float], D: List[float]) -> bool:
    """선분 AB와 선분 CD가 교차하는지 여부를 판별합니다."""
    return (ccw(A, C, D) != ccw(B, C, D)) and (ccw(A, B, C) != ccw(A, B, D))


# 육지 관통 위험 장벽 (Barrier Line & Bypass Waypoint)
_BARRIERS = [
    {
        "name": "인도 반도",
        "line": ([68.0, 22.0], [79.5, 7.0]),  # 인도 서안 ~ 스리랑카 남단
        "bypass": [80.5, 5.0]  # 스리랑카 남단 해상
    },
    {
        "name": "말레이 반도",
        "line": ([98.0, 8.0], [103.5, 1.5]),  # 말레이 반도 중간 가로지름
        "bypass": [103.8, 1.0]  # 싱가포르 남단 해상
    },
    {
        "name": "아라비아 반도",
        "line": ([32.5, 29.5], [50.0, 15.0]),  # 아라비아 반도 중간
        "bypass": [43.2, 12.6]  # 바브엘만데브 해협 (홍해 입구)
    }
]


def _find_shortest_path_raw(
    db: Session, start_coords: List[float], end_coords: List[float]
) -> Tuple[List[List[float]], float]:
    """메모리 내 해상 네트워크 상에서 시작지와 목적지 간의 최단 경로를 구하며, 
    단절된 노드 발견 시 자가치유 가상 링크를 생성하여 우회 경로를 탐색합니다.
    """
    load_graph(db)

    if not _nodes or not _graph:
        logger.warning("Routing graph is empty. Returning direct line.")
        return [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]], haversine(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

    # 1. 가장 가까운 해상 노드 검색
    start_node = _find_nearest_node(start_coords[0], start_coords[1])
    end_node = _find_nearest_node(end_coords[0], end_coords[1])

    if start_node is None or end_node is None or start_node == end_node:
        return [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]], haversine(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

    # 2. 다익스트라 최단 경로 연산
    queue = [(0.0, start_node, [], [start_node])]
    distances = {start_node: 0.0}
    parents = {}  # target_node -> (parent_node, link_id)
    path_found = False

    while queue:
        cost, u, path_links, path_nodes = heapq.heappop(queue)

        if u == end_node:
            path_found = True
            break

        if cost > distances.get(u, float('inf')):
            continue

        for v, weight, link_id in _graph.get(u, []):
            next_cost = cost + weight
            if next_cost < distances.get(v, float('inf')):
                distances[v] = next_cost
                parents[v] = (u, link_id)
                heapq.heappush(queue, (next_cost, v, path_links + [link_id], path_nodes + [v]))

    # 3. 자가치유 (Self-Healing): 다익스트라 실패 시 고립 노드 가상 링크 주입 및 재탐색
    if not path_found:
        logger.info(f"Self-healing: connecting isolated nodes for {start_node} -> {end_node}")
        temp_inserted_links = []

        # start_node 및 end_node 주변 200km 이내의 본선 노드들을 이어주는 임시 가상 링크 생성
        for node in [start_node, end_node]:
            n_lng, n_lat = _nodes[node]
            candidates = []
            for target_id, (t_lng, t_lat) in _nodes.items():
                if target_id == node:
                    continue
                d = haversine(n_lng, n_lat, t_lng, t_lat)
                if d <= 200.0:
                    candidates.append((d, target_id))

            candidates.sort()
            for d, target_id in candidates[:3]:
                if node not in _graph:
                    _graph[node] = []
                if target_id not in _graph:
                    _graph[target_id] = []

                exists = False
                for existing_target, _, _ in _graph[node]:
                    if existing_target == target_id:
                        exists = True
                        break

                if not exists:
                    # 임시 가상 링크 ID 음수 지정 (-1000 - i)
                    v_link_id = -1000 - len(temp_inserted_links)
                    weight = d * 1.2  # 가상 링크는 페널티 부여
                    
                    _graph[node].append((target_id, weight, v_link_id))
                    _graph[target_id].append((node, weight, v_link_id))
                    
                    _links[v_link_id] = {
                        "source": node,
                        "target": target_id,
                        "distance": d,
                        "weight": weight,
                        "path_coords": [[n_lat, n_lng], [t_lat, t_lng]]
                    }
                    temp_inserted_links.append((node, target_id, v_link_id))

        if temp_inserted_links:
            logger.info(f"Temporarily inserted {len(temp_inserted_links)} virtual links. Retrying Dijkstra...")
            queue = [(0.0, start_node, [], [start_node])]
            distances = {start_node: 0.0}
            parents = {}

            while queue:
                cost, u, path_links, path_nodes = heapq.heappop(queue)
                if u == end_node:
                    path_found = True
                    break
                if cost > distances.get(u, float('inf')):
                    continue
                for v, weight, link_id in _graph.get(u, []):
                    next_cost = cost + weight
                    if next_cost < distances.get(v, float('inf')):
                        distances[v] = next_cost
                        parents[v] = (u, link_id)
                        heapq.heappush(queue, (next_cost, v, path_links + [link_id], path_nodes + [v]))

        # 가상 링크 롤백 (원래 상태 복원)
        for node, target_id, v_link_id in temp_inserted_links:
            if node in _graph:
                _graph[node] = [item for item in _graph[node] if item[2] != v_link_id]
            if target_id in _graph:
                _graph[target_id] = [item for item in _graph[target_id] if item[2] != v_link_id]
            if v_link_id in _links:
                del _links[v_link_id]

    if not path_found:
        logger.warning(f"No path found between node {start_node} and {end_node}. Fallback to direct.")
        return [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]], haversine(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

    # 4. 경로 추적 및 좌표 조립
    curr = end_node
    link_chain = []
    node_chain = [end_node]
    while curr != start_node:
        parent, link_id = parents[curr]
        link_chain.append(link_id)
        node_chain.append(parent)
        curr = parent

    link_chain.reverse()
    node_chain.reverse()

    final_path = []
    total_dist = 0.0

    for i, link_id in enumerate(link_chain):
        u = node_chain[i]
        v = node_chain[i + 1]
        link_data = _links.get(link_id)
        if not link_data:
            continue
        
        coords = link_data["path_coords"] or []
        if not coords:
            u_coord = _nodes[u]
            v_coord = _nodes[v]
            coords = [[u_coord[1], u_coord[0]], [v_coord[1], v_coord[0]]]

        if link_data["source"] == u:
            seg_coords = coords
        else:
            seg_coords = coords[::-1]

        if final_path and seg_coords:
            if final_path[-1] == seg_coords[0]:
                final_path.extend(seg_coords[1:])
            else:
                final_path.extend(seg_coords)
        else:
            final_path.extend(seg_coords)

        total_dist += link_data["distance"]

    # 진입/퇴출 연결 보완
    start_pt = [start_coords[1], start_coords[0]]
    end_pt = [end_coords[1], end_coords[0]]

    if final_path:
        if final_path[0] != start_pt:
            final_path.insert(0, start_pt)
        if final_path[-1] != end_pt:
            final_path.append(end_pt)
    else:
        final_path = [start_pt, end_pt]

    return final_path, total_dist


def find_shortest_path(
    db: Session, start_coords: List[float], end_coords: List[float]
) -> Tuple[List[List[float]], float]:
    """메모리 내 해상 네트워크 상에서 시작지와 목적지 간의 최단 경로와 총 거리를 계산합니다.
    
    경로선이 지정된 지리적 장벽(Barrier, 예: 인도 내륙)을 통과하는 경우 우회점(Sri Lanka 남단 등)을 주입해
    자가 우회 경로를 빌딩합니다.
    """
    # 장벽 감지 및 우회점 주입
    bypass_wp = None
    for barrier in _BARRIERS:
        # A, B는 출발-목적 좌표 [lng, lat]
        if intersect(start_coords, end_coords, barrier["line"][0], barrier["line"][1]):
            bypass_wp = barrier["bypass"]
            logger.info(f"Geographic barrier detected: '{barrier['name']}'. Routing bypass via {bypass_wp}.")
            break

    if bypass_wp:
        try:
            path1, dist1 = _find_shortest_path_raw(db, start_coords, bypass_wp)
            path2, dist2 = _find_shortest_path_raw(db, bypass_wp, end_coords)
            
            # 최종 궤적 병합
            combined_path = path1[:]
            if path2 and combined_path[-1] == path2[0]:
                combined_path.extend(path2[1:])
            else:
                combined_path.extend(path2)
                
            return combined_path, dist1 + dist2
        except Exception as e:
            logger.warning(f"Bypass routing failed ({e}). Falling back to direct routing.")

    return _find_shortest_path_raw(db, start_coords, end_coords)
