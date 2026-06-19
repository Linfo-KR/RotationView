import pandas as pd
from typing import Dict, List, Optional, Union, Any
import logging
from pathlib import Path

from .mapper import DataMapper
from .route import RouteProcessor
from .normalize_schedule import ScheduleNormalizer

class ExportData:
    """
    CSV 파일 처리를 위한 고수준 인터페이스
    """
    
    @staticmethod
    def process_terminal_routes(proforma: Union[str, Path],
                                svc: Union[str, Path],
                                output: Union[str, Path],
                                config: Dict[str, Any]) -> pd.DataFrame:
        """
        터미널 라우트 처리를 위한 원스톱 함수
        
        Args:
            proforma: 터미널 별 프로포마 물량 데이터 (data/proforma.csv)
            svc: 노선 별 BPA 서비스 코드 데이터 (data/bpa_service_code.csv)
            output: 출력 파일 경로
            config: 설정 딕셔너리
        
        Returns:
            처리된 DataFrame
        """
        # 설정값 추출 (기본값 포함)
        key_column = config.get('key_column', 'SVC')
        route_columns = config.get('route_columns', ['Route1', 'Route2'])
        field_mappings = config.get('field_mappings', {
            'Name': 'Name',
            'Wtp': 'Wtp', 
            'Sch': 'Sch'
        })
        max_terminals = config.get('max_terminals', 3)
        output_prefix = config.get('output_prefix', 'T')
        
        try:
            # 데이터 매퍼 초기화
            mapper = DataMapper.from_csv(proforma, key_column)
            
            # 입력 데이터 로드
            input_df = pd.read_csv(svc)
            
            # 라우트 프로세서로 처리
            processor = RouteProcessor(mapper)
            result_df = processor.process_routes(
                input_df, route_columns, field_mappings, max_terminals, output_prefix
            )
            
            # 'Sch' 필드가 매핑 대상인 경우, 스케줄 정보 정규화
            if 'Sch' in field_mappings:
                normalizer = ScheduleNormalizer()
                for i in range(1, max_terminals + 1):
                    sch_column = f"{output_prefix}{i}Sch"
                    if sch_column in result_df.columns:
                        result_df[sch_column] = result_df[sch_column].apply(
                            lambda x: normalizer.normalize(str(x)) if pd.notna(x) else ""
                        )
            
            # 결과 저장
            result_df.to_csv(output, index=False)
            print(f"작업 완료. 결과가 '{output}' 파일에 저장되었습니다.")
            
            return result_df
            
        except Exception as e:
            logging.error(f"Processing failed: {e}")
            raise