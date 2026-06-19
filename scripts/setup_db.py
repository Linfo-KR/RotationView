import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

def create_database(user, password, host="localhost", port="5432", dbname="rotation_db"):
    try:
        # Default postgres db 에 연결
        con = psycopg2.connect(dbname='postgres', user=user, host=host, port=port, password=password)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        
        # rotation_db 가 있는지 확인
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{dbname}'")
        exists = cur.fetchone()
        
        if not exists:
            # DB 생성
            cur.execute(f'CREATE DATABASE {dbname}')
            print(f"Database '{dbname}' successfully created.")
        else:
            print(f"Database '{dbname}' already exists.")
            
        cur.close()
        con.close()
        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

if __name__ == "__main__":
    success = create_database("postgres", "postgres")
    if not success:
        sys.exit(1)
