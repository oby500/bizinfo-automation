"""
PDF 파싱 실행 스크립트 - 단계별 처리
Step 1: PDF 다운로드 및 텍스트 추출
"""

import os
import sys
import json
import requests
import PyPDF2
import pdfplumber
from io import BytesIO
from datetime import datetime
from pathlib import Path
import re
from dotenv import load_dotenv
from supabase import create_client

# 환경변수 로드
load_dotenv()

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 환경변수 설정 필요: SUPABASE_URL, SUPABASE_KEY")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_pdf_text(pdf_content: bytes) -> str:
    """PDF에서 텍스트 추출"""
    text = ""
    
    try:
        # PyPDF2로 추출
        pdf_file = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- 페이지 {page_num + 1} ---\n"
                text += page_text
        
        print(f"  PyPDF2로 {len(text)}자 추출")
        
    except Exception as e:
        print(f"  PyPDF2 실패: {e}")
        
        # pdfplumber로 재시도
        try:
            pdf_file = BytesIO(pdf_content)
            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- 페이지 {page_num + 1} ---\n"
                        text += page_text
                    
                    # 표도 추출
                    tables = page.extract_tables()
                    if tables:
                        text += "\n[표 데이터]\n"
                        for table in tables:
                            for row in table:
                                text += " | ".join([str(cell) if cell else "" for cell in row]) + "\n"
            
            print(f"  pdfplumber로 {len(text)}자 추출")
            
        except Exception as e2:
            print(f"  pdfplumber도 실패: {e2}")
    
    return text

def extract_info_from_text(text: str, title: str) -> dict:
    """텍스트에서 정보 추출"""
    
    info = {
        "title": title,
        "support_amount": None,
        "target_audience": None,
        "application_period": None,
        "required_documents": [],
        "evaluation_criteria": {},
        "selection_count": None,
        "contact": None
    }
    
    # 지원금액 찾기
    amount_patterns = [
        r'최대\s*(\d+억?\s*원|\d+,?\d+만\s*원)',
        r'지원금액\s*[:：]\s*([^\n]+)',
        r'(\d+억?\s*원|\d+,?\d+만\s*원)\s*지원'
    ]
    
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            info["support_amount"] = matches[0].strip()
            break
    
    # 지원대상 찾기
    if '지원대상' in text:
        idx = text.find('지원대상')
        info["target_audience"] = text[idx:idx+300].split('\n')[1:3]
    
    # 신청기간 찾기
    date_pattern = r'(\d{4}[\.\-]\d{1,2}[\.\-]\d{1,2})'
    dates = re.findall(date_pattern, text)
    if len(dates) >= 2:
        info["application_period"] = f"{dates[0]} ~ {dates[1]}"
    
    # 제출서류 찾기
    if '제출서류' in text or '구비서류' in text:
        keyword = '제출서류' if '제출서류' in text else '구비서류'
        idx = text.find(keyword)
        doc_section = text[idx:idx+500]
        
        # 번호로 시작하는 항목 찾기
        doc_items = re.findall(r'[①②③④⑤\d]+[\.\)]\s*([^\n]+)', doc_section)
        info["required_documents"] = doc_items[:10]
    
    # 평가기준 찾기
    if '평가' in text and '기준' in text:
        eval_items = re.findall(r'([가-힣\s]+?)\s*(\d+점|\d+%)', text)
        if eval_items:
            info["evaluation_criteria"] = {item[0].strip(): item[1] for item in eval_items[:10]}
    
    # 선정인원 찾기
    selection_match = re.search(r'(\d+개?\s*업체|\d+명|\d+개사)\s*선정', text)
    if selection_match:
        info["selection_count"] = selection_match.group(1)
    
    return info

def process_single_record(record: dict, source: str = "kstartup"):
    """단일 레코드 처리"""
    
    if source == "kstartup":
        announcement_id = record['announcement_id']
        title = record['biz_pbanc_nm']
    else:
        announcement_id = record['pblanc_id']
        title = record['pblanc_nm']
    
    print(f"\n처리 중: {announcement_id} - {title[:50]}...")
    
    attachments = record.get('attachment_urls', [])
    
    # PDF 찾기
    pdf_url = None
    pdf_filename = None
    
    for att in attachments:
        if isinstance(att, dict) and att.get('type') == 'PDF':
            pdf_url = att['url']
            pdf_filename = att.get('display_filename', 'unknown.pdf')
            break
    
    if not pdf_url:
        print("  PDF 없음 - 건너뜀")
        return None
    
    print(f"  PDF 발견: {pdf_filename}")
    
    try:
        # PDF 다운로드
        print("  다운로드 중...")
        response = requests.get(pdf_url, timeout=30)
        
        if response.status_code != 200:
            print(f"  다운로드 실패: {response.status_code}")
            return None
        
        print(f"  크기: {len(response.content):,} bytes")
        
        # 텍스트 추출
        text = extract_pdf_text(response.content)
        
        if not text:
            print("  텍스트 추출 실패")
            return None
        
        print(f"  텍스트 추출: {len(text):,}자")
        
        # 정보 추출
        extracted_info = extract_info_from_text(text, title)
        
        # MCP용 파일 저장
        output_dir = Path("E:\\claude-workspace\\temp\\for_summary")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 요청 파일 생성
        request_file = output_dir / f"{announcement_id}_request.json"
        request_data = {
            "announcement_id": announcement_id,
            "source": source,
            "title": title,
            "text_preview": text[:5000],  # 처음 5000자
            "extracted_info": extracted_info,
            "full_text_length": len(text),
            "pdf_filename": pdf_filename,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        with open(request_file, 'w', encoding='utf-8') as f:
            json.dump(request_data, f, ensure_ascii=False, indent=2)
        
        # 전체 텍스트도 저장
        text_file = output_dir / f"{announcement_id}_text.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"  ✅ 저장 완료: {request_file.name}")
        
        return {
            "announcement_id": announcement_id,
            "title": title,
            "extracted_info": extracted_info,
            "text_length": len(text)
        }
        
    except Exception as e:
        print(f"  ❌ 에러: {e}")
        return None

def main():
    """메인 실행"""
    
    print("=" * 60)
    print("PDF 파싱 Step 1: 텍스트 추출 및 정보 추출")
    print("=" * 60)
    
    # K-Startup에서 PDF가 있는 최신 공고 조회
    print("\n1. K-Startup 공고 조회 중...")
    
    result = supabase.table('kstartup_complete').select(
        'announcement_id, biz_pbanc_nm, attachment_urls'
    ).gte('pbanc_rcpt_end_dt', datetime.now().date().isoformat()).limit(5).execute()
    
    records = result.data
    print(f"  조회 결과: {len(records)}개")
    
    # 처리
    success_count = 0
    results = []
    
    for record in records:
        result = process_single_record(record, "kstartup")
        if result:
            success_count += 1
            results.append(result)
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("처리 결과")
    print("=" * 60)
    print(f"전체: {len(records)}개")
    print(f"성공: {success_count}개")
    print(f"실패: {len(records) - success_count}개")
    
    if results:
        print("\n성공한 공고:")
        for r in results:
            print(f"  - {r['announcement_id']}: {r['title'][:40]}... ({r['text_length']:,}자)")
            if r['extracted_info']['support_amount']:
                print(f"    지원금: {r['extracted_info']['support_amount']}")
    
    print("\n" + "=" * 60)
    print("✅ Step 1 완료!")
    print("다음 단계: Claude가 Summary 작성")
    print("=" * 60)

if __name__ == "__main__":
    main()
