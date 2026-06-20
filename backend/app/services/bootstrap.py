import os
import json
import inspect
import logging
from sqlalchemy.orm import Session

import searoute as sr
from .. import models
from ..utils.geo import haversine

logger = logging.getLogger(__name__)


def bootstrap_routing_data(db: Session) -> None:
    """searoute 패키지의 내장 geojson 데이터를 파싱하여 DB에 라우팅 노드 및 링크를 적재합니다."""
    # 노드 개수 체크
    node_count = db.query(models.RouteNode).count()
    if node_count > 0:
        logger.info("Routing nodes already exist in DB. Skipping bootstrap.")
        return

    logger.info("Starting routing nodes and links bootstrap...")

    # 1. searoute data 디렉토리 경로 획득
    module_dir = os.path.dirname(inspect.getfile(sr))
    geojson_path = os.path.join(module_dir, "data", "marnet_searoute.geojson")

    if not os.path.exists(geojson_path):
        logger.error(f"searoute geojson file not found at {geojson_path}")
        return

    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)

        features = geojson_data.get("features", [])
        logger.info(f"Loaded {len(features)} features from geojson.")

        # 2. 고유 좌표(노드) 수집
        # 소수점 6자리 반올림하여 딕셔너리 키로 사용 (미세 오차 보정)
        unique_nodes = {}  # (round(lng, 6), round(lat, 6)) -> {lat, lng}

        for feat in features:
            geom = feat.get("geometry", {})
            geom_type = geom.get("type")
            coords = geom.get("coordinates", [])
            if not coords:
                continue

            lines = []
            if geom_type == "LineString":
                lines = [coords]
            elif geom_type == "MultiLineString":
                lines = coords

            for line in lines:
                for pt in line:
                    if len(pt) >= 2:
                        lng, lat = pt[0], pt[1]
                        key = (round(lng, 6), round(lat, 6))
                        if key not in unique_nodes:
                            unique_nodes[key] = {"lng": lng, "lat": lat}

        logger.info(f"Collected {len(unique_nodes)} unique nodes.")

        # 3. 노드 DB 일괄 적재
        node_db_list = []
        for key, val in unique_nodes.items():
            node_db_list.append(models.RouteNode(
                lng=val["lng"],
                lat=val["lat"],
                is_port=False
            ))

        db.bulk_save_objects(node_db_list)
        db.commit()

        # 삽입된 노드 ID 매핑 복원
        db_nodes = db.query(models.RouteNode).all()
        # 노드 캐시 구축: (round(lng, 6), round(lat, 6)) -> node_id
        node_id_map = {(round(n.lng, 6), round(n.lat, 6)): n.node_id for n in db_nodes}

        # 4. 링크 DB 생성 및 적재
        link_db_list = []
        for idx, feat in enumerate(features):
            geom = feat.get("geometry", {})
            geom_type = geom.get("type")
            coords = geom.get("coordinates", [])
            if not coords:
                continue

            lines = []
            if geom_type == "LineString":
                lines = [coords]
            elif geom_type == "MultiLineString":
                lines = coords

            for line in lines:
                if len(line) < 2:
                    continue

                start_coord = line[0]
                end_coord = line[-1]

                start_key = (round(start_coord[0], 6), round(start_coord[1], 6))
                end_key = (round(end_coord[0], 6), round(end_coord[1], 6))

                source_id = node_id_map.get(start_key)
                target_id = node_id_map.get(end_key)

                if not source_id or not target_id:
                    continue

                # 구간 누적 거리 계산
                dist = 0.0
                for i in range(len(line) - 1):
                    dist += haversine(line[i][0], line[i][1], line[i + 1][0], line[i + 1][1])

                # 좌표 리스트 [[lat, lng], ...] 형태로 저장
                path_coords = [[c[1], c[0]] for c in line]

                link_db_list.append(models.RouteLink(
                    source_node=source_id,
                    target_node=target_id,
                    distance_km=round(dist, 2),
                    is_active=True,
                    weight_modifier=1.0,
                    path_coords=path_coords
                ))

        db.bulk_save_objects(link_db_list)
        db.commit()
        logger.info(f"Successfully bootstrapped {len(link_db_list)} links.")

    except Exception as e:
        logger.error(f"Failed to bootstrap routing data: {e}", exc_info=True)
        db.rollback()
