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
        
        # 5. DB에 저장
        success_count = 0
        duplicate_count = 0
        
        for idx, row in df.iterrows():
            try:
                # URL에서 pblanc_id 추출
                dtl_url = str(row.get('링크', ''))
                pblanc_id = None
                
                if dtl_url and 'pblancId=' in dtl_url:
                    parsed = urlparse(dtl_url)
                    params = parse_qs(parsed.query)
                    pblanc_id = params.get('pblancId', [None])[0]
                
                if not pblanc_id:
                    pblanc_id = f"PBLN_{datetime.now().strftime('%Y%m%d')}_{idx:04d}"
                
                # 레코드 생성
                record = {
                    'pblanc_id': pblanc_id,
                    'pblanc_nm': str(row.get('공고명', '')),
                    'jrsd_instt_nm': str(row.get('소관부처명', '') or row.get('관할기관', '')),
                    'exc_instt_nm': str(row.get('수행기관', '')),
                    'reqst_begin_end_de': str(row.get('신청기간', '')),
                    'trget_nm': str(row.get('지원대상', '')),
                    'pldir_sport_realm_lclas_code_nm': str(row.get('지원분야', '')),
                    'dtl_url': dtl_url,
                    'inqire_co': int(row.get('조회', 0)) if pd.notna(row.get('조회')) else 0,
                    'src_system_nm': 'github_actions',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                
                # 중복 체크 후 저장
                existing = supabase.table('bizinfo_complete').select('id').eq('pblanc_id', record['pblanc_id']).execute()
                
                if not existing.data:
                    result = supabase.table('bizinfo_complete').insert(record).execute()
                    if result.data:
                        success_count += 1
                        print(f"  [{idx+1}/{len(df)}] ✅ 저장: {record['pblanc_nm'][:30]}...")
                else:
                    duplicate_count += 1
                    print(f"  [{idx+1}/{len(df)}] ⏭️ 중복: {record['pblanc_nm'][:30]}...")
                    
            except Exception as e:
                print(f"  [{idx+1}/{len(df)}] ❌ 오류: {e}")
                continue
        
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
