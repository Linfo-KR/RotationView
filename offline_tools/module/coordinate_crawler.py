import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import json
import threading  # 추가된 부분
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from tqdm import tqdm
import os
from typing import Union, List

class CoordinateCrawler:
    """
    shipxplorer.com에서 항만 기본 정보와 상세 좌표를 병렬 처리로 빠르게 크롤링하는 클래스.
    
    - 1단계: 전체 항만 목록에서 국가명, 항만명, 항만 코드를 수집합니다.
    - 2단계: 각 항만 코드를 병렬로 처리하여 상세 페이지에서 위도(Latitude)와 경도(Longitude)를 수집합니다.
    """

    BASE_URL = "https://www.shipxplorer.com/data/ports"

    def __init__(self, headless=True, max_workers=10):
        """
        크롤러를 초기화합니다.
        :param headless: True일 경우 브라우저 UI 없이 백그라운드에서 실행합니다.
        :param max_workers: 동시에 실행할 최대 스레드(일꾼) 수.
        """
        self.headless = headless
        self.max_workers = max_workers
        # 각 스레드가 독립적인 드라이버를 저장할 공간 (핵심 변경)
        self.thread_local = threading.local()
        self.drivers: List[webdriver.Chrome] = [] # 생성된 드라이버를 추적하기 위한 리스트

    def _get_driver(self) -> webdriver.Chrome:
        """
        현재 스레드에 할당된 드라이버를 반환합니다. 없으면 새로 생성합니다.
        """
        # 현재 스레드에 드라이버가 없으면 새로 생성
        if not hasattr(self.thread_local, 'driver'):
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument("--headless")
            
            # 성능 최적화: 이미지 및 CSS 로딩 비활성화
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.stylesheets": 2,
            }
            options.add_experimental_option("prefs", prefs)
            
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            self.thread_local.driver = driver
            self.drivers.append(driver) # 추적 리스트에 추가
        return self.thread_local.driver

    def get_port_list(self) -> list[dict]:
        """
        1단계: 전체 항만 목록 페이지에서 국가, 항만명, 항만 코드를 크롤링합니다.
        """
        # 이 메서드는 단일 스레드로 실행되므로 기존 로직 유지
        driver = self._get_driver() 
        port_list = []
        print("Starting to collect the main port list...")
        
        try:
            driver.get(self.BASE_URL)
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.list.port-list")))
            
            country_sections = driver.find_elements(By.CSS_SELECTOR, "ul.list.port-list > li:not([id])")
            
            for section in country_sections:
                country_div = section.find_element(By.CSS_SELECTOR, "div.collapsible.hidden")
                country_name_raw = country_div.get_attribute("id")
                country_name = country_name_raw.replace('-collapse', '').replace('_', ' ').title()

                port_links = country_div.find_elements(By.CSS_SELECTOR, "div.ports > a")
                
                for link in port_links:
                    href = link.get_attribute('href')
                    if not href or '/data/ports/' not in href:
                        continue
                    
                    port_code = href.split('/')[-1]
                    full_text = driver.execute_script("return arguments[0].textContent;", link).strip()
                    port_name = full_text.replace(port_code, '').strip()
                    
                    port_list.append({
                        "country_name": country_name,
                        "port_name": port_name,
                        "port_code": port_code
                    })
        except (TimeoutException, NoSuchElementException) as e:
            print(f"An error occurred while getting the port list: {e}")
        # finally 블록에서 driver.quit() 제거
            
        print(f"Collected basic info for {len(port_list)} ports. Now starting to fetch coordinates.")
        
        return port_list

    def _fetch_coordinates_worker(self, port_info: dict) -> Union[dict, None]:
        """
        (일꾼 함수) 단일 항만 코드에 대한 좌표를 크롤링합니다. (드라이버 재사용)
        """
        # 스레드에 할당된 드라이버를 가져옴 (매번 생성하지 않음)
        driver = self._get_driver()
        port_code = port_info['port_code']
        port_url = f"{self.BASE_URL}/{port_code}"
        
        try:
            driver.get(port_url)
            
            # Strategy 1: Parse JSON from <script> tag
            try:
                page_source = driver.page_source
                match = re.search(r'window\.init\((.*?)\);?\s*<\/script>', page_source, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    data = json.loads(json_str)
                    if 'port' in data and 'lat' in data['port'] and 'lng' in data['port']:
                        port_info.update({'lat': data['port']['lat'], 'lng': data['port']['lng']})
                        return port_info
            except Exception:
                pass

            # Strategy 2: Scrape DOM elements (Fallback)
            try:
                wait = WebDriverWait(driver, 5) # 타임아웃 감소
                info_list_ul = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.ListNew__ListStyle-sc-1kdnh14-1")))
                info_items = info_list_ul.find_elements(By.CSS_SELECTOR, "li.ListItem__ListItemStyle-sc-k0s881-0")
                
                if info_items:
                    first_list_item = info_items[0]
                    WebDriverWait(first_list_item, 3).until(EC.presence_of_element_located((By.ID, "title")))
                    
                    titles = first_list_item.find_elements(By.ID, "title")
                    values = first_list_item.find_elements(By.ID, "value")
                    
                    lat, lng = None, None
                    for title, value in zip(titles, values):
                        title_text = title.text.strip().lower()
                        if 'latitude' in title_text:
                            lat = value.text.strip()
                        elif 'longitude' in title_text:
                            lng = value.text.strip()
                    
                    if lat and lng:
                        port_info.update({'lat': lat, 'lng': lng})
                        return port_info
            except Exception:
                pass

            return None

        except Exception as e:
            # print(f"[{port_code}] A critical error occurred: {e}") # 디버깅 시 주석 해제
            return None
        # finally 블록에서 driver.quit() 제거 (매우 중요)

    def _close_drivers(self):
        """생성된 모든 웹 드라이버를 종료합니다."""
        print("Closing all web drivers...")
        for driver in self.drivers:
            try:
                driver.quit()
            except Exception:
                pass # 이미 닫혔거나 오류가 발생해도 무시

    def run(self) -> pd.DataFrame:
        """
        전체 크롤링 파이프라인을 병렬로 실행합니다.
        """
        all_port_data = []
        try:
            ports = self.get_port_list()
            if not ports:
                return pd.DataFrame()

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self._fetch_coordinates_worker, port) for port in ports]
                
                for future in tqdm(as_completed(futures), total=len(ports), desc="Fetching Coordinates"):
                    result = future.result()
                    if result:
                        all_port_data.append(result)
        finally:
            # 모든 작업이 끝나면 생성된 모든 드라이버를 정리
            self._close_drivers()
                    
        return pd.DataFrame(all_port_data)


if __name__ == '__main__':
    try:
        # PC 사양과 네트워크 환경에 따라 max_workers 수를 조절하여 성능을 최적화할 수 있습니다.
        # 서버 차단을 피하기 위해 10 내외의 낮은 값으로 시작하는 것을 권장합니다.
        crawler = CoordinateCrawler(headless=True, max_workers=10)
        
        port_data_df = crawler.run()
        
        if not port_data_df.empty:
            # --- 경로 문제 해결을 위한 절대 경로 설정 ---
            # 이 스크립트 파일(coordinate_crawler.py)의 절대 경로를 기준으로 경로를 설정합니다.
            SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
            # 이 스크립트의 상위 폴더가 프로젝트 루트 폴더입니다.
            PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
            
            # 절대 경로를 사용하여 정확한 출력 경로를 지정합니다.
            output_path = os.path.join(PROJECT_ROOT, "data", "coordinate", "port_coordinates.csv")
            
            # 출력 디렉토리가 존재하는지 확인하고 없으면 생성합니다.
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            port_data_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"\nCrawling complete! Saved {len(port_data_df)} port coordinates to '{output_path}'.")
        else:
            print("\nNo data was collected. This might be due to server-side blocking (rate-limiting).")

    except Exception as e:
        print(f"An unexpected error occurred during the crawling process: {e}")
