"""
PDF 파싱 테스트 - 단일 파일 테스트
"""

import os
import json
import requests
import PyPDF2
from io import BytesIO
from dotenv import load_dotenv
from supabase import create_client

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

def test_single_pdf():
    """단일 PDF 테스트"""
    
    # 테스트할 PDF 가져오기
    result = supabase.table('kstartup_complete').select(
        'announcement_id, biz_pbanc_nm, attachment_urls'
    ).limit(1).execute()
    
    if not result.data:
        print("데이터 없음")
        return
    
    record = result.data[0]
    print(f"테스트 공고: {record['biz_pbanc_nm']}")
    
    # PDF URL 찾기
    attachments = record.get('attachment_urls', [])
    pdf_url = None
    
    for att in attachments:
        if isinstance(att, dict) and att.get('type') == 'PDF':
            pdf_url = att['url']
            break
    
    if not pdf_url:
        print("PDF 없음")
        # HWP 파일이 있는지 확인
        for att in attachments:
            if isinstance(att, dict):
                print(f"파일 타입: {att.get('type')}, URL: {att.get('url')[:50]}...")
        return
    
    print(f"PDF URL: {pdf_url}")
    
    # PDF 다운로드
    print("다운로드 중...")
    response = requests.get(pdf_url, timeout=30)
    print(f"응답 코드: {response.status_code}")
    print(f"크기: {len(response.content)} bytes")
    
    # 텍스트 추출
    try:
        pdf_file = BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        print(f"페이지 수: {len(pdf_reader.pages)}")
        
        text = ""
        for i, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            text += page_text
            if i == 0:  # 첫 페이지만 출력
                print(f"\n첫 페이지 내용 (500자):\n{page_text[:500]}")
        
        print(f"\n전체 텍스트 길이: {len(text)}자")
        
        # 파일로 저장
        output_file = f"E:\\claude-workspace\\temp\\pdf_extracted\\test_output.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"저장 완료: {output_file}")
        
    except Exception as e:
        print(f"에러: {e}")

if __name__ == "__main__":
    test_single_pdf()
