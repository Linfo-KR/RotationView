import pandas as pd
import os
import json
import re

def normalize_name(name):
    """
    이름 정규화: 소문자 변환, 괄호 제거, 앞뒤 공백 제거
    """
    if not isinstance(name, str):
        return ""
    # "Manzanillo(Mexico)" -> "manzanillo"
    name = re.sub(r'\(.*?\)', '', name)
    return name.strip().lower()

def load_port_database(port_csv_path):
    """
    항구 DB를 로드하고 검색 최적화를 위해 Set으로 변환
    """
    if not os.path.exists(port_csv_path):
        print(f"[Error] Port DB file not found: {port_csv_path}")
        return set()

    df = pd.read_csv(port_csv_path)
    
    valid_names = set()
    
    for _, row in df.iterrows():
        # Main Name
        if pd.notna(row.get('port_name')):
            valid_names.add(normalize_name(row['port_name']))
        
        # Aliases (JSON string or list)
        aliases = row.get('aliases')
        if pd.notna(aliases):
            try:
                # If it's a string representation of list "['a', 'b']"
                if isinstance(aliases, str):
                    # Simple cleaning for CSV string format if not valid JSON
                    if aliases.startswith('[') and aliases.endswith(']'):
                        # Try parsing as JSON first
                        try:
                            alias_list = json.loads(aliases.replace("'", '"'))
                        except:
                            # Fallback: simple split
                            alias_list = aliases.strip("[]").replace("'", "").split(',')
                    else:
                        alias_list = [aliases]
                elif isinstance(aliases, list):
                    alias_list = aliases
                else:
                    alias_list = []

                for alias in alias_list:
                    if alias:
                        valid_names.add(normalize_name(alias.strip()))
            except Exception as e:
                pass
                
    return valid_names

def check_routes(route_csv_path, valid_ports):
    """
    노선 데이터를 읽고 매칭되지 않는 항구를 찾음
    """
    if not os.path.exists(route_csv_path):
        print(f"[Error] Route file not found: {route_csv_path}")
        return {}

    df = pd.read_csv(route_csv_path)
    
    unmatched_counts = {}
    
    # Assuming column name 'port_rotation' exists. If not, try common names.
    col_name = 'port_rotation'
    if col_name not in df.columns:
        # Try to find a similar column
        for c in df.columns:
            if 'rotation' in c.lower():
                col_name = c
                break
    
    if col_name not in df.columns:
        print(f"[Error] Could not find rotation column in {route_csv_path}")
        return {}

    print(f"[Info] Checking routes using column: {col_name}")

    for _, row in df.iterrows():
        rotation = row[col_name]
        if pd.isna(rotation):
            continue
            
        # Split by comma, hyphen, arrow
        ports = re.split(r'[,\->]+', str(rotation))
        
        for p in ports:
            raw_name = p.strip()
            if not raw_name:
                continue
                
            norm_name = normalize_name(raw_name)
            
            if norm_name not in valid_ports:
                if raw_name not in unmatched_counts:
                    unmatched_counts[raw_name] = 0
                unmatched_counts[raw_name] += 1
                
    return unmatched_counts

def main():
    # Configuration
    # Adjust paths based on your project structure
    port_db_path = "data/database/tb_port.csv" 
    # If using DB file directly isn't possible, use the input file
    if not os.path.exists(port_db_path):
        port_db_path = "data/input/port_coordinates.csv" 

    route_file_path = "data/database/tb_route.csv"
    # Fallback to input if DB dump not available
    if not os.path.exists(route_file_path):
        route_file_path = "data/input/proforma.csv"

    output_path = "data/output/unmatched_ports.csv"

    print("=== Port Matching Verification Start ===")
    
    # 1. Load Valid Ports
    print(f"[Step 1] Loading valid ports from {port_db_path}...")
    valid_ports = load_port_database(port_db_path)
    print(f" -> Loaded {len(valid_ports)} unique valid port names (including aliases).")

    # 2. Check Routes
    print(f"[Step 2] Checking routes in {route_file_path}...")
    unmatched = check_routes(route_file_path, valid_ports)
    
    # 3. Save Result
    print(f"[Step 3] Saving results...")
    if unmatched:
        df_result = pd.DataFrame(list(unmatched.items()), columns=['Unknown Port Name', 'Count'])
        df_result = df_result.sort_values(by='Count', ascending=False)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_result.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f" -> Found {len(unmatched)} unknown port names.")
        print(f" -> Top 5 unknown: {df_result.head(5)['Unknown Port Name'].tolist()}")
        print(f" -> Saved to: {output_path}")
        print(" -> Please review this file and update TB_PORT aliases or correct the route data.")
    else:
        print(" -> Perfect! All ports matched.")

if __name__ == "__main__":
    main()
