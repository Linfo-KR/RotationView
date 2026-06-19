import pandas as pd
from typing import Dict, List, Optional, Union, Any
import logging
from pathlib import Path

from .mapper import DataMapper

class RouteProcessor:
    """
    라우트 데이터 처리 전용 클래스
    여러 라우트 컬럼을 결합하여 터미널 정보를 매핑
    """
    
    def __init__(self, data_mapper: DataMapper):
        self.mapper = data_mapper
    
    def process_routes(self, 
                      input_df: pd.DataFrame,
                      route_columns: List[str],
                      field_mappings: Dict[str, str],
                      max_terminals: int = 3,
                      output_prefix: str = "T") -> pd.DataFrame:
        """
        라우트 데이터 처리
        
        Args:
            input_df: 처리할 입력 DataFrame
            route_columns: 라우트 정보가 담긴 컬럼들
            field_mappings: 필드 매핑 딕셔너리 {"출력필드": "참조테이블컬럼"}
            max_terminals: 최대 터미널 수
            output_prefix: 출력 컬럼 접두사
        
        Returns:
            처리된 DataFrame
        """
        result_df = input_df.copy()

        # 출력 컬럼을 object 타입으로 미리 생성하여 FutureWarning 방지
        for field_key in field_mappings.keys():
            for terminal_num in range(1, max_terminals + 1):
                output_column = f"{output_prefix}{terminal_num}{field_key}"
                if output_column not in result_df.columns:
                    result_df[output_column] = pd.Series(dtype='object')
        
        for idx, row in result_df.iterrows():
            # 라우트 컬럼들에서 값 추출 및 결합
            route_values = []
            for col in route_columns:
                if col in row and pd.notna(row[col]):
                    value = str(row[col]).strip()
                    if value and value != 'nan':
                        route_values.append(value)
            
            if not route_values:
                continue
            
            combined_routes = ",".join(route_values)
            
            # 각 필드에 대해 터미널 정보 조회
            for field_key, reference_column in field_mappings.items():
                for terminal_num in range(1, max_terminals + 1):
                    output_column = f"{output_prefix}{terminal_num}{field_key}"
                    
                    value = self.mapper.lookup_values(
                        combined_routes, 
                        reference_column, 
                        terminal_num
                    )
                    
                    if value:
                        result_df.at[idx, output_column] = value
                    elif terminal_num == 1:
                        # 첫 번째 터미널 정보가 없으면 다음 터미널도 검사하지 않음
                        break
        
        return result_df