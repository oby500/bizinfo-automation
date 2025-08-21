#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import glob
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from supabase import create_client

# 로그 함수
def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()

log("기업마당 스크래퍼 시작")

# 환경 변수
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    log("❌ SUPABASE_URL 또는 SUPABASE_KEY가 없습니다")
    sys.exit(1)

# Supabase 연결
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    log("✅ Supabase 연결 성공")
except Exception as e:
    log(f"❌ Supabase 연결 실패: {str(e)}")
    sys.exit(1)

# Chrome 설정
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option('excludeSwitches', ['enable-logging'])

# 다운로드 경로
download_dir = "/tmp/downloads"
os.makedirs(download_dir, exist_ok=True)

# 다운로드 설정
prefs = {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "safebrowsing.disable_download_protection": True
}
options.add_experimental_option("prefs", prefs)

# WebDriver 초기화
driver = None
try:
    log("Chrome 드라이버 초기화...")
    driver = webdriver.Chrome(options=options)
    log("✅ 드라이버 준비 완료")
    
    # 기업마당 접속
    url = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"
    log(f"기업마당 접속: {url}")
    driver.get(url)
    
    # 페이지 로드 대기
    log("페이지 로드 대기...")
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    log("✅ 페이지 로드 완료")
    
    # JavaScript 실행 가능 대기
    time.sleep(3)
    
    # 엑셀 다운로드
    log("엑셀 다운로드 시작...")
    try:
        driver.execute_script("excelDown();")
    except Exception as e:
        log(f"JavaScript 실행 오류: {str(e)}")
        # 대체 방법 시도
        log("대체 방법으로 다운로드 시도...")
        excel_button = driver.find_element(By.CLASS_NAME, "btn_excel")
        excel_button.click()
    
    # 다운로드 대기
    log("다운로드 대기 (45초)...")
    time.sleep(45)
    
    # 파일 찾기
    files = glob.glob(f"{download_dir}/*.xlsx") + glob.glob(f"{download_dir}/*.xls")
    
    if not files:
        log(f"다운로드 경로 내용: {os.listdir(download_dir)}")
        raise Exception("엑셀 파일을 찾을 수 없습니다")
    
    latest_file = max(files, key=os.path.getctime)
    log(f"✅ 파일 발견: {os.path.basename(latest_file)}")
    
    # 엑셀 읽기
    log("엑셀 파일 읽는 중...")
    df = pd.read_excel(latest_file)
    log(f"✅ 데이터: {len(df)}개 행")
    
    # 컬럼 확인
    columns = df.columns.tolist()
    log(f"컬럼 목록: {', '.join(columns)}")
    
    # DB 저장
    success = 0
    skip = 0
    error = 0
    
    for idx, row in df.iterrows():
        try:
            # 데이터 매핑 (bizinfo_complete 테이블 구조에 맞게)
            record = {
                "pblanc_id": str(row.get("번호", f"TEMP_{idx}")),
                "pblanc_nm": str(row.get("공고명", "")),
                "organ_nm": str(row.get("소관부처", "")),  # jrsd_instt_nm 대신 organ_nm 사용
                "bsns_sumry": f"{row.get('지원분야', '')} - {row.get('지원목적', '')}"[:200],
                "src_system_nm": "bizinfo_excel",
                "dtl_url": str(row.get("공고상세URL", ""))
            }
            
            # 날짜 처리
            start_date = row.get("신청시작일자")
            end_date = row.get("신청종료일자")
            
            if pd.notna(start_date):
                try:
                    record["reqst_begin_ymd"] = pd.to_datetime(start_date).strftime('%Y-%m-%d')
                except:
                    record["reqst_begin_ymd"] = None
            else:
                record["reqst_begin_ymd"] = None
                
            if pd.notna(end_date):
                try:
                    record["reqst_end_ymd"] = pd.to_datetime(end_date).strftime('%Y-%m-%d')
                except:
                    record["reqst_end_ymd"] = None
            else:
                record["reqst_end_ymd"] = None
            
            # 빈 값 처리
            for key, value in record.items():
                if pd.isna(value) or value == "nan" or value == "":
                    record[key] = None
            
            # pblanc_id가 없으면 건너뛰기
            if not record["pblanc_id"] or record["pblanc_id"] == "None":
                log(f"행 {idx}: pblanc_id 없음, 건너뛰기")
                continue
            
            # 중복 체크
            existing = supabase.table("bizinfo_complete").select("id").eq("pblanc_id", record["pblanc_id"]).execute()
            
            if not existing.data:
                result = supabase.table("bizinfo_complete").insert(record).execute()
                success += 1
                if success % 100 == 0:
                    log(f"진행상황: {success}개 저장")
            else:
                skip += 1
                
        except Exception as e:
            error += 1
            if error <= 5:
                log(f"❌ 행 {idx} 오류: {str(e)}")
    
    # 최종 결과
    log("="*50)
    log(f"✅ 처리 완료!")
    log(f"   - 전체: {len(df)}개")
    log(f"   - 신규 저장: {success}개")
    log(f"   - 중복 건너뛰기: {skip}개")
    log(f"   - 오류: {error}개")
    log("="*50)
    
except Exception as e:
    log(f"❌ 치명적 오류: {str(e)}")
    import traceback
    log(f"상세 오류:\n{traceback.format_exc()}")
    sys.exit(1)
    
finally:
    if driver:
        driver.quit()
        log("브라우저 종료")