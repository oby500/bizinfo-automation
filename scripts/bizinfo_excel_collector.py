from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from supabase import create_client, Client
import pandas as pd
import os
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

def main():
    print(f"[{datetime.now()}] 기업마당 자동 수집 시작")
    
    # Supabase 연결
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    supabase: Client = create_client(url, key)
    
    # Selenium 설정 (GitHub Actions용)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # 다운로드 설정
    download_dir = "/tmp"
    if os.name == 'nt':  # Windows
        download_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(download_dir, exist_ok=True)
    
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # 드라이버 시작
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        # 1. 페이지 접속
        print("페이지 접속 중...")
        driver.get("https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do")
        time.sleep(5)
        
        # 2. 엑셀 다운로드
        print("엑셀 다운로드 시작...")
        driver.execute_script("excelDown()")
        time.sleep(20)  # 다운로드 대기
        
        # 3. 다운로드된 파일 찾기
        files = [f for f in os.listdir(download_dir) if f.endswith('.xlsx')]
        if not files:
            print("엑셀 파일을 찾을 수 없습니다")
            return
            
        latest_file = max(files, key=lambda x: os.path.getctime(os.path.join(download_dir, x)))
        file_path = os.path.join(download_dir, latest_file)
        print(f"다운로드 완료: {latest_file}")
        
        # 4. 엑셀 처리
        df = pd.read_excel(file_path)
        print(f"총 {len(df)}개 공고 발견")
        
        # 컬럼명 확인
        print(f"컬럼: {df.columns.tolist()}")
        
        # 5. 기존 pblanc_id 목록 한 번에 조회 (중요!)
        print("기존 데이터 확인 중...")
        existing_result = supabase.table('bizinfo_complete').select('pblanc_id').execute()
        existing_ids = {item['pblanc_id'] for item in existing_result.data} if existing_result.data else set()
        print(f"기존 데이터: {len(existing_ids)}개")
        
        # 6. 배치 처리용 리스트
        new_records = []
        duplicate_count = 0
        
        for idx, row in df.iterrows():
            try:
                # URL에서 pblanc_id 추출
                dtl_url = str(row.get('공고상세URL', ''))
                pblanc_id = None
                
                if dtl_url and 'pblancId=' in dtl_url:
                    parsed = urlparse(dtl_url)
                    params = parse_qs(parsed.query)
                    pblanc_id = params.get('pblancId', [None])[0]
                
                if not pblanc_id:
                    pblanc_id = f"PBLN_{datetime.now().strftime('%Y%m%d')}_{idx:04d}"
                
                # 중복 체크 (메모리에서!)
                if pblanc_id in existing_ids:
                    duplicate_count += 1
                    if duplicate_count <= 10:  # 처음 10개만 출력
                        print(f"  [{idx+1}/{len(df)}] ⏭️ 중복: {row.get('공고명', '')[:30]}...")
                    continue
                
                # 신청기간 처리
                start_date = str(row.get('신청시작일자', ''))
                end_date = str(row.get('신청종료일자', ''))
                
                # 신규 레코드 생성
                record = {
                    'pblanc_id': pblanc_id,
                    'pblanc_nm': str(row.get('공고명', '')),
                    'spnsr_organ_nm': str(row.get('소관부처', '')),
                    'exctv_organ_nm': str(row.get('사업수행기관', '')),
                    'reqst_begin_ymd': start_date,
                    'reqst_end_ymd': end_date,
                    'sprt_realm_nm': str(row.get('지원분야', '')),
                    'dtl_url': dtl_url,
                    'regist_dt': str(row.get('등록일자', '')),
                    'src_system_nm': 'github_actions',
                    'created_at': datetime.now().isoformat()
                }
                
                new_records.append(record)
                print(f"  [{idx+1}/{len(df)}] ✅ 신규: {record['pblanc_nm'][:30]}...")
                
            except Exception as e:
                print(f"  [{idx+1}/{len(df)}] ❌ 오류: {e}")
                continue
        
        # 7. 배치 삽입 (한 번에!)
        success_count = 0
        if new_records:
            print(f"\n배치 저장 중... ({len(new_records)}개)")
            
            # 100개씩 나눠서 저장 (Supabase 제한)
            batch_size = 100
            for i in range(0, len(new_records), batch_size):
                batch = new_records[i:i+batch_size]
                try:
                    result = supabase.table('bizinfo_complete').insert(batch).execute()
                    if result.data:
                        success_count += len(result.data)
                        print(f"  배치 {i//batch_size + 1} 저장 완료: {len(result.data)}개")
                except Exception as e:
                    print(f"  배치 저장 오류: {e}")
        
        print(f"\n=== 수집 완료 ===")
        print(f"✅ 신규 저장: {success_count}개")
        print(f"⏭️ 중복 제외: {duplicate_count}개")
        print(f"📊 전체 처리: {len(df)}개")
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        raise
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
