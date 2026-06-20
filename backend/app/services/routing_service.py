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


def find_shortest_path(
    db: Session, start_coords: List[float], end_coords: List[float]
) -> Tuple[List[List[float]], float]:
    """메모리 내 해상 네트워크 상에서 시작지와 목적지 간의 최단 경로와 총 거리를 계산합니다.

    Args:
        db (Session): DB 세션
        start_coords (List[float]): 출발 좌표 [lng, lat]
        end_coords (List[float]): 도착 좌표 [lng, lat]

    Returns:
        Tuple[List[List[float]], float]: [[lat, lng], ...] 형태의 경로 좌표들과 누적 거리 (km)
    """
    load_graph(db)

    if not _nodes or not _graph:
        logger.warning("Routing graph is empty. Returning direct line.")
        return [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]], haversine(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

    # 1. 가장 가까운 해상 노드 검색
    start_node = _find_nearest_node(start_coords[0], start_coords[1])
    end_node = _find_nearest_node(end_coords[0], end_coords[1])

    if start_node is None or end_node is None or start_node == end_node:
        # Fallback: 직선 반환
        return [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]], haversine(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

    # 2. 다익스트라 최단 경로 연산
    # queue: (cost, current_node, path_links, path_nodes)
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

    # 3. 경로 추적 및 좌표 어셈블링
    if not path_found:
        logger.warning(f"No path found between node {start_node} and {end_node}. Fallback to direct.")
        return [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]], haversine(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

    # 역추적으로 노드/링크 체인 획득
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

    # 링크 상세 좌표들을 이어붙여 최종 궤적 리스트 구성
    final_path = []
    total_dist = 0.0

    for i, link_id in enumerate(link_chain):
        u = node_chain[i]
        v = node_chain[i + 1]
        link_data = _links[link_id]
        
        coords = link_data["path_coords"] or []
        if not coords:
            # 궤적 정보 유실 대비 백업
            u_coord = _nodes[u]
            v_coord = _nodes[v]
            coords = [[u_coord[1], u_coord[0]], [v_coord[1], v_coord[0]]]

        # 링크가 u -> v 순서인지 반대인지 검사해 뒤집기 처리
        if link_data["source"] == u:
            # 순방향
            seg_coords = coords
        else:
            # 역방향
            seg_coords = coords[::-1]

        # 연속 궤적 병합 시 겹치는 중복 포인트 제거
        if final_path and seg_coords:
            if final_path[-1] == seg_coords[0]:
                final_path.extend(seg_coords[1:])
            else:
                final_path.extend(seg_coords)
        else:
            final_path.extend(seg_coords)

        total_dist += link_data["distance"]

    # 4. 포트와 네트워크 노드 간의 안전한 시각 진입/퇴출 연결선 보강
    # [lat, lng] 포맷
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
