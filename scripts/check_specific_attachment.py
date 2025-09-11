import os
import sys
from supabase import create_client
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv('E:/gov-support-automation/config/.env')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Supabase 클라이언트 생성
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# PBLN_000000000114380의 첨부파일 확인
try:
    result = supabase.table('bizinfo_complete').select('pblanc_no, dtl_url, attachment_urls').eq('pblanc_no', 'PBLN_000000000114380').execute()
    
    if result.data:
        for row in result.data:
            print(f"공고번호: {row['pblanc_no']}")
            print(f"\n첨부파일 URL들:")
            if row['attachment_urls']:
                for url in row['attachment_urls']:
                    # URL에서 파일명 추출
                    if '/' in url:
                        filename = url.split('/')[-1]
                    else:
                        filename = url
                    print(f"  - {filename}")
                    print(f"    전체 URL: {url}")
            else:
                print("  첨부파일 없음")
    else:
        print("해당 공고를 찾을 수 없습니다")
        
except Exception as e:
    print(f"오류 발생: {e}")

# 실제 다운로드된 파일 확인
print("\n실제 다운로드된 파일:")
download_dir = "E:/gov-support-automation/downloads/bizinfo/"
for file in os.listdir(download_dir):
    if "PBLN_000000000114380" in file:
        file_path = os.path.join(download_dir, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            print(f"  - {file} ({size:,} bytes)")