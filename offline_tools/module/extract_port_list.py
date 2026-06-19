import pandas as pd
import os
import sys
from typing import List

def extract_port_list(file_path: str, sheet_name: str, column_name: str, output_file: str, separator: str = ',') -> List[str]:
    """
    엑셀 파일의 특정 컬럼에서 구분자로 분리된 모든 고유 값을 추출합니다.
    Pandas의 벡터화 연산을 사용하여 성능을 최적화했습니다.

    Args:
        file_path (str): 엑셀 파일 경로
        sheet_name (str): 시트 이름
        column_name (str): 대상 컬럼 이름
        separator (str): 값을 분리할 구분자 (기본값: ',')

    Returns:
        List[str]: 정렬된 고유 값 리스트
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        if column_name not in df.columns:
            raise ValueError(f"컬럼 '{column_name}'을(를) 시트 '{sheet_name}'에서 찾을 수 없습니다.")

        # 최적화된 로직:
        # 1. dropna(): 결측치 제거
        # 2. astype(str): 문자열로 변환
        # 3. str.split(separator): 구분자로 분리 (리스트 반환)
        # 4. explode(): 리스트를 개별 행으로 펼침
        # 5. str.strip(): 앞뒤 공백 제거
        # 6. unique(): 고유값 추출
        unique_values = (
            df[column_name]
            .dropna()
            .astype(str)
            .str.split(separator)
            .explode()
            .str.strip()
            .unique()
        )
        
        # None이나 빈 문자열이 포함될 수 있으므로 필터링 후 정렬
        unique_ports = sorted([val for val in unique_values if val])
        
        return unique_ports

    except Exception as e:
        raise RuntimeError(f"데이터 추출 중 오류 발생: {e}")
    
def main():
    # config
    input_file = "data/input/route_master.xlsx"
    sheet_name = "MasterTable"
    column_name = "Port Rotation"
    output_file = "data/output/unique_port_list.csv"

    print(f"[Info] '{input_file}'에서 항만 목록 추출을 시작합니다...")

    try:
        # 1. 데이터 추출 (유틸리티 모듈 사용)
        unique_ports = extract_port_list(input_file, sheet_name, column_name)
        print(f"[Info] 총 {len(unique_ports)}개의 고유 항만명을 찾았습니다.")

        # 2. 결과 저장
        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # DataFrame 변환 및 CSV 저장
        df_output = pd.DataFrame(unique_ports, columns=["port_name"])
        df_output.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"[Success] 결과가 저장되었습니다: {output_file}")

    except Exception as e:
        print(f"[Erruor] 작업 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()