"""
PDF 스트리밍 파서 - K-Startup/BizInfo PDF 파일 파싱 및 DB 업데이트
"""

import os
import json
import requests
import PyPDF2
import pdfplumber
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from supabase import create_client, Client
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트 초기화
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def extract_pdf_text(pdf_content: bytes) -> str:
    """PDF에서 텍스트 추출"""
    text = ""
    
    # PyPDF2로 시도
    try:
        pdf_file = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    except Exception as e:
        print(f"PyPDF2 실패: {e}")
        
        # pdfplumber로 재시도
        try:
            pdf_file = BytesIO(pdf_content)
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e2:
            print(f"pdfplumber도 실패: {e2}")
            return ""
    
    return text

def extract_structured_info(text: str) -> Dict:
    """텍스트에서 구조화된 정보 추출"""
    
    extracted = {
        "support_amount": None,
        "target_audience": None,
        "application_period": None,
        "required_documents": [],
        "evaluation_criteria": {},
        "exclusions": None,
        "contact_info": None,
        "selection_count": None
    }
    
    # 지원금액 추출
    amount_patterns = [
        r'최대\s*(\d+억?\s*원|\d+,?\d+만\s*원)',
        r'지원금액\s*[:：]\s*(\d+억?\s*원|\d+,?\d+만\s*원)',
        r'(\d+억?\s*원|\d+,?\d+만\s*원)\s*지원'
    ]
    for pattern in amount_patterns:
        matches = re.findall(pattern, text)
        if matches:
            extracted["support_amount"] = matches[0]
            break
    
    # 지원대상 추출
    if '지원대상' in text or '신청자격' in text:
        for keyword in ['지원대상', '신청자격']:
            if keyword in text:
                idx = text.index(keyword)
                extracted["target_audience"] = text[idx:idx+300].split('\n')[0]
                break
    
    # 신청기간 추출
    date_pattern = r'(\d{4}[\.\-년]\s*\d{1,2}[\.\-월]\s*\d{1,2})'
    dates = re.findall(date_pattern, text)
    if len(dates) >= 2:
        extracted["application_period"] = f"{dates[0]} ~ {dates[1]}"
    
    # 제출서류 추출
    if '제출서류' in text or '구비서류' in text:
        for keyword in ['제출서류', '구비서류']:
            if keyword in text:
                idx = text.index(keyword)
                doc_section = text[idx:idx+500]
                # 번호나 불릿으로 시작하는 항목 찾기
                doc_items = re.findall(r'[①②③④⑤⑥⑦⑧⑨⑩\d]+[\.\)]\s*([^\n]+)', doc_section)
                extracted["required_documents"] = doc_items[:10]  # 최대 10개
                break
    
    # 평가기준 추출 (표 형태일 가능성 높음)
    if '평가' in text and ('기준' in text or '항목' in text):
        eval_section = re.findall(r'([가-힣\s]+)\s*(\d+점|\d+%)', text)
        if eval_section:
            extracted["evaluation_criteria"] = {item[0].strip(): item[1] for item in eval_section[:10]}
    
    # 선정인원 추출
    selection_patterns = [
        r'선정\s*인원\s*[:：]\s*(\d+명|\d+개사)',
        r'(\d+명|\d+개사)\s*선정',
        r'선정\s*규모\s*[:：]\s*(\d+명|\d+개사)'
    ]
    for pattern in selection_patterns:
        matches = re.findall(pattern, text)
        if matches:
            extracted["selection_count"] = matches[0]
            break
    
    # 제외대상 추출
    if '제외' in text or '불가' in text:
        for keyword in ['제외대상', '신청불가', '지원제외']:
            if keyword in text:
                idx = text.index(keyword)
                extracted["exclusions"] = text[idx:idx+300].split('\n')[0]
                break
    
    # 연락처 추출
    phone_pattern = r'(\d{2,3}[-\.\s]?\d{3,4}[-\.\s]?\d{4})'
    phones = re.findall(phone_pattern, text)
    if phones:
        extracted["contact_info"] = phones[0]
    
    return extracted

def save_parsed_json(announcement_id: str, source: str, parsed_data: Dict) -> bool:
    """파싱된 데이터를 attachment_parsed_data 테이블에 저장"""
    try:
        # 테이블 존재 확인 및 생성
        try:
            result = supabase.table('attachment_parsed_data').select('id').limit(1).execute()
        except:
            # 테이블이 없으면 생성
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS attachment_parsed_data (
                id SERIAL PRIMARY KEY,
                announcement_id TEXT NOT NULL,
                source TEXT NOT NULL,
                parsed_data JSONB,
                extracted_text TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_attachment_parsed_unique 
            ON attachment_parsed_data(announcement_id, source);
            """
            # 여기서는 테이블 생성 생략 (이미 있다고 가정)
        
        # 데이터 삽입 또는 업데이트
        data = {
            "announcement_id": announcement_id,
            "source": source,
            "parsed_data": parsed_data,
            "created_at": datetime.now().isoformat()
        }
        
        result = supabase.table('attachment_parsed_data').upsert(data).execute()
        return True
        
    except Exception as e:
        print(f"JSON 저장 실패: {e}")
        return False

def update_database_fields(announcement_id: str, source: str, extracted_info: Dict) -> bool:
    """추출된 정보로 DB 필드 업데이트"""
    try:
        table_name = "kstartup_complete" if source == "kstartup" else "bizinfo_complete"
        
        # 업데이트할 필드 준비
        update_data = {}
        
        # K-Startup 테이블 업데이트
        if source == "kstartup":
            if extracted_info.get("target_audience"):
                update_data["aply_trgt_ctnt"] = extracted_info["target_audience"]
            if extracted_info.get("selection_count"):
                update_data["selection_count"] = extracted_info["selection_count"]
                
        # BizInfo 테이블 업데이트
        else:
            if extracted_info.get("support_amount"):
                update_data["sprt_scale"] = extracted_info["support_amount"]
            if extracted_info.get("target_audience"):
                update_data["sprt_trgt"] = extracted_info["target_audience"]
            if extracted_info.get("required_documents"):
                update_data["submit_mtrl"] = ", ".join(extracted_info["required_documents"])
            if extracted_info.get("evaluation_criteria"):
                update_data["slctn_stdr"] = json.dumps(extracted_info["evaluation_criteria"], ensure_ascii=False)
        
        if update_data:
            if source == "kstartup":
                result = supabase.table(table_name).update(update_data).eq("announcement_id", announcement_id).execute()
            else:
                result = supabase.table(table_name).update(update_data).eq("pblanc_id", announcement_id).execute()
            return True
            
    except Exception as e:
        print(f"DB 업데이트 실패: {e}")
        return False

def save_to_temp_file(announcement_id: str, text: str, extracted_info: Dict):
    """임시로 파일로 저장 (MCP로 읽을 수 있도록)"""
    temp_dir = "E:\\claude-workspace\\temp\\pdf_extracted"
    os.makedirs(temp_dir, exist_ok=True)
    
    # 텍스트 저장
    text_file = os.path.join(temp_dir, f"{announcement_id}_text.txt")
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(text)
    
    # 추출 정보 저장
    info_file = os.path.join(temp_dir, f"{announcement_id}_info.json")
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_info, f, ensure_ascii=False, indent=2)
    
    print(f"임시 파일 저장: {announcement_id}")

def process_single_pdf(record: Dict, source: str) -> Dict:
    """단일 PDF 처리"""
    try:
        if source == "kstartup":
            announcement_id = record['announcement_id']
            title = record['biz_pbanc_nm']
            attachments = record.get('attachment_urls', [])
        else:
            announcement_id = record['pblanc_id']
            title = record['pblanc_nm']
            attachments = record.get('attachment_urls', [])
        
        # PDF 파일 찾기
        pdf_urls = []
        for att in attachments:
            if isinstance(att, dict) and att.get('type') == 'PDF':
                pdf_urls.append(att['url'])
        
        if not pdf_urls:
            return {"status": "no_pdf", "id": announcement_id}
        
        # 첫 번째 PDF 처리
        pdf_url = pdf_urls[0]
        
        # PDF 다운로드 (메모리로)
        response = requests.get(pdf_url, timeout=30)
        if response.status_code != 200:
            return {"status": "download_failed", "id": announcement_id}
        
        # 텍스트 추출
        text = extract_pdf_text(response.content)
        if not text:
            return {"status": "extraction_failed", "id": announcement_id}
        
        # 정보 추출
        extracted_info = extract_structured_info(text)
        
        # 임시 파일 저장 (MCP용)
        save_to_temp_file(announcement_id, text, extracted_info)
        
        # JSON 저장
        save_parsed_json(announcement_id, source, extracted_info)
        
        # DB 필드 업데이트
        update_database_fields(announcement_id, source, extracted_info)
        
        return {
            "status": "success",
            "id": announcement_id,
            "title": title,
            "extracted": extracted_info
        }
        
    except Exception as e:
        return {"status": "error", "id": announcement_id, "error": str(e)}

def process_batch(source: str = "kstartup", batch_size: int = 50):
    """배치 처리"""
    table_name = "kstartup_complete" if source == "kstartup" else "bizinfo_complete"
    id_field = "announcement_id" if source == "kstartup" else "pblanc_id"
    date_field = "pbanc_rcpt_end_dt" if source == "kstartup" else "reqst_end_ymd"
    
    # PDF가 있는 레코드 조회
    query = supabase.table(table_name).select(
        f"{id_field}, {'biz_pbanc_nm' if source == 'kstartup' else 'pblanc_nm'}, attachment_urls, summary"
    )
    
    # 활성 공고만
    query = query.gte(date_field, datetime.now().date().isoformat())
    
    # Summary가 없거나 부실한 것만
    query = query.or_(f"summary.is.null,summary.lt.100")
    
    # 배치 크기만큼
    query = query.limit(batch_size)
    
    result = query.execute()
    records = result.data
    
    print(f"처리할 레코드: {len(records)}개")
    
    # 멀티스레딩으로 처리 (5개 스레드)
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for record in records:
            future = executor.submit(process_single_pdf, record, source)
            futures.append(future)
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            # 진행 상황 출력
            success_count = len([r for r in results if r['status'] == 'success'])
            print(f"진행: {len(results)}/{len(records)} (성공: {success_count})")
    
    # 결과 요약
    summary = {
        "total": len(results),
        "success": len([r for r in results if r['status'] == 'success']),
        "no_pdf": len([r for r in results if r['status'] == 'no_pdf']),
        "failed": len([r for r in results if r['status'] in ['download_failed', 'extraction_failed', 'error']])
    }
    
    print("\n=== 처리 결과 ===")
    print(json.dumps(summary, indent=2))
    
    return results

if __name__ == "__main__":
    print("PDF 스트리밍 파서 시작...")
    print("=" * 50)
    
    # K-Startup 먼저 처리 (테스트로 10개만)
    print("\n[K-Startup PDF 처리]")
    kstartup_results = process_batch("kstartup", batch_size=10)
    
    # 잠시 대기
    time.sleep(2)
    
    # BizInfo 처리 (테스트로 10개만)
    print("\n[BizInfo PDF 처리]")
    bizinfo_results = process_batch("bizinfo", batch_size=10)
    
    print("\n완료!")
