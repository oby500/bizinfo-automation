"""
PDF 파싱 완전판 - 구조화된 JSON 생성 포함
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
                    
                    # 표 추출
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            text += " | ".join([str(cell) if cell else "" for cell in row]) + "\n"
        except Exception as e2:
            print(f"pdfplumber도 실패: {e2}")
            return ""
    
    return text

def extract_comprehensive_info(text: str, title: str) -> Dict:
    """종합적인 정보 추출 - 정부지원사업에 특화"""
    
    # 완전한 JSON 구조
    extracted = {
        # 기본 정보
        "title": title,
        "parsed_at": datetime.now().isoformat(),
        
        # 사업 개요
        "business_overview": {
            "purpose": None,           # 사업 목적
            "background": None,         # 추진 배경
            "expected_effect": None,    # 기대 효과
            "business_type": None,      # 사업 유형
            "business_category": None   # 사업 분류
        },
        
        # 지원 정보
        "support_info": {
            "total_budget": None,       # 총 예산
            "support_amount": None,     # 지원 금액
            "support_scale": None,      # 지원 규모
            "support_items": [],        # 지원 항목
            "support_ratio": None,      # 지원 비율
            "self_burden_ratio": None,  # 자부담 비율
            "support_period": None,     # 지원 기간
            "number_of_selection": None # 선정 인원/업체 수
        },
        
        # 신청 대상
        "target_info": {
            "target_audience": None,    # 지원 대상
            "age_limit": None,          # 연령 제한
            "business_years": None,     # 사업 연차 제한
            "location_limit": None,     # 지역 제한
            "industry_limit": [],       # 업종 제한
            "company_size": None,       # 기업 규모
            "prerequisites": [],        # 필수 조건
            "preferential": []          # 우대 조건
        },
        
        # 제외 대상
        "exclusion_info": {
            "excluded_targets": [],     # 제외 대상
            "excluded_industries": [],  # 제외 업종
            "other_restrictions": []    # 기타 제한사항
        },
        
        # 신청 정보
        "application_info": {
            "application_period": None, # 신청 기간
            "application_method": None, # 신청 방법
            "application_url": None,    # 신청 URL
            "announcement_date": None,  # 공고일
            "result_date": None        # 결과 발표일
        },
        
        # 제출 서류
        "document_info": {
            "required_documents": [],   # 필수 서류
            "optional_documents": [],   # 선택 서류
            "document_format": None,    # 서류 형식
            "submission_method": None   # 제출 방법
        },
        
        # 평가 정보
        "evaluation_info": {
            "evaluation_method": None,  # 평가 방법
            "evaluation_criteria": {},  # 평가 기준 (항목: 배점)
            "evaluation_process": [],   # 평가 절차
            "extra_points": [],         # 가점 사항
            "deduction_points": []      # 감점 사항
        },
        
        # 연락처
        "contact_info": {
            "organization": None,       # 주관 기관
            "department": None,         # 담당 부서
            "person": None,            # 담당자
            "phone": None,             # 전화번호
            "email": None,             # 이메일
            "website": None,           # 홈페이지
            "address": None            # 주소
        },
        
        # 추가 정보
        "additional_info": {
            "faq": [],                 # 자주 묻는 질문
            "notes": [],               # 유의사항
            "changes_from_last": [],   # 전년 대비 변경사항
            "related_programs": []     # 관련 사업
        },
        
        # 메타데이터
        "metadata": {
            "text_length": len(text),
            "has_table": "표" in text or "Table" in text,
            "has_evaluation_criteria": "평가" in text and "기준" in text,
            "confidence_score": 0.0    # 추출 신뢰도 (0-1)
        }
    }
    
    # === 정보 추출 로직 ===
    
    # 1. 지원금액 추출 (개선된 버전)
    amount_patterns = [
        r'최대\s*(\d+억?\s*원|\d+,?\d+만\s*원)',
        r'지원금액\s*[:：]\s*([^\n]+)',
        r'지원규모\s*[:：]\s*([^\n]+)',
        r'(\d+억?\s*원|\d+,?\d+만\s*원)\s*지원',
        r'업체당\s*(\d+억?\s*원|\d+,?\d+만\s*원)'
    ]
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            extracted["support_info"]["support_amount"] = matches[0].strip()
            break
    
    # 2. 지원대상 추출 (개선된 버전)
    target_keywords = ['지원대상', '신청자격', '참여자격', '신청대상']
    for keyword in target_keywords:
        if keyword in text:
            idx = text.index(keyword)
            # 다음 섹션까지 또는 500자까지
            end_idx = idx + 500
            for next_keyword in ['제외대상', '신청방법', '제출서류', '평가기준']:
                if next_keyword in text[idx:idx+500]:
                    next_idx = text.index(next_keyword, idx)
                    if next_idx < end_idx:
                        end_idx = next_idx
            
            target_text = text[idx:end_idx]
            # 첫 줄은 제목일 수 있으므로 제외
            lines = target_text.split('\n')
            if len(lines) > 1:
                extracted["target_info"]["target_audience"] = '\n'.join(lines[1:3]).strip()
            break
    
    # 3. 신청기간 추출
    date_pattern = r'(\d{4}[\.\-년]\s*\d{1,2}[\.\-월]\s*\d{1,2}[일]?)'
    dates = re.findall(date_pattern, text)
    
    # 접수기간 찾기
    if '접수' in text or '신청' in text:
        for keyword in ['접수기간', '신청기간', '모집기간']:
            if keyword in text:
                idx = text.index(keyword)
                period_text = text[idx:idx+100]
                period_dates = re.findall(date_pattern, period_text)
                if len(period_dates) >= 2:
                    extracted["application_info"]["application_period"] = f"{period_dates[0]} ~ {period_dates[1]}"
                    break
    
    # 4. 제출서류 추출 (개선)
    doc_keywords = ['제출서류', '구비서류', '신청서류', '첨부서류']
    for keyword in doc_keywords:
        if keyword in text:
            idx = text.index(keyword)
            doc_section = text[idx:idx+1000]
            
            # 번호나 불릿으로 시작하는 항목 찾기
            doc_patterns = [
                r'[①②③④⑤⑥⑦⑧⑨⑩]\s*([^\n]+)',
                r'\d+[\.\)]\s*([^\n]+)',
                r'[가나다라마바사아자차]\.\s*([^\n]+)',
                r'[-•▪▫◦‣⁃]\s*([^\n]+)'
            ]
            
            for pattern in doc_patterns:
                doc_items = re.findall(pattern, doc_section)
                if doc_items:
                    extracted["document_info"]["required_documents"] = [item.strip() for item in doc_items[:15]]
                    break
            
            if extracted["document_info"]["required_documents"]:
                break
    
    # 5. 평가기준 추출 (표 형태 고려)
    if '평가' in text:
        eval_section = ""
        for keyword in ['평가기준', '평가항목', '심사기준', '선정기준']:
            if keyword in text:
                idx = text.index(keyword)
                eval_section = text[idx:idx+1500]
                break
        
        if eval_section:
            # 평가항목과 배점 찾기
            eval_patterns = [
                r'([가-힣\s]+?)\s*(\d+점)',
                r'([가-힣\s]+?)\s*\((\d+점)\)',
                r'([가-힣\s]+?)\s*(\d+)%',
                r'([가-힣\s]+?)\s*[:：]\s*(\d+)'
            ]
            
            for pattern in eval_patterns:
                eval_items = re.findall(pattern, eval_section)
                if eval_items:
                    extracted["evaluation_info"]["evaluation_criteria"] = {
                        item[0].strip(): item[1] for item in eval_items[:10]
                    }
                    break
    
    # 6. 선정인원 추출
    selection_patterns = [
        r'선정\s*[:：]\s*(\d+개?\s*업체|\d+명|\d+개사)',
        r'(\d+개?\s*업체|\d+명|\d+개사)\s*선정',
        r'선정규모\s*[:：]\s*(\d+개?\s*업체|\d+명|\d+개사)',
        r'모집규모\s*[:：]\s*(\d+개?\s*업체|\d+명|\d+개사)'
    ]
    for pattern in selection_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            extracted["support_info"]["number_of_selection"] = matches[0]
            break
    
    # 7. 제외대상 추출
    exclude_keywords = ['제외대상', '신청불가', '지원제외', '신청제외']
    for keyword in exclude_keywords:
        if keyword in text:
            idx = text.index(keyword)
            exclude_section = text[idx:idx+500]
            
            # 제외 항목 찾기
            exclude_patterns = [
                r'[①②③④⑤⑥⑦⑧⑨⑩]\s*([^\n]+)',
                r'\d+[\.\)]\s*([^\n]+)',
                r'[-•▪▫◦‣⁃]\s*([^\n]+)'
            ]
            
            for pattern in exclude_patterns:
                exclude_items = re.findall(pattern, exclude_section)
                if exclude_items:
                    extracted["exclusion_info"]["excluded_targets"] = [item.strip() for item in exclude_items[:10]]
                    break
            
            if extracted["exclusion_info"]["excluded_targets"]:
                break
    
    # 8. 연락처 추출
    phone_pattern = r'(\d{2,4}[-\.\s]?\d{3,4}[-\.\s]?\d{3,4})'
    phones = re.findall(phone_pattern, text)
    if phones:
        extracted["contact_info"]["phone"] = phones[0]
    
    email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    emails = re.findall(email_pattern, text)
    if emails:
        extracted["contact_info"]["email"] = emails[0]
    
    # 9. 기관명 추출
    if '문의' in text:
        idx = text.index('문의')
        contact_section = text[idx:idx+200]
        lines = contact_section.split('\n')
        for line in lines:
            if '기관' in line or '부서' in line or '센터' in line:
                extracted["contact_info"]["organization"] = line.strip()
                break
    
    # 10. 신뢰도 점수 계산
    confidence = 0.0
    if extracted["support_info"]["support_amount"]: confidence += 0.2
    if extracted["target_info"]["target_audience"]: confidence += 0.2
    if extracted["application_info"]["application_period"]: confidence += 0.2
    if extracted["document_info"]["required_documents"]: confidence += 0.2
    if extracted["evaluation_info"]["evaluation_criteria"]: confidence += 0.2
    
    extracted["metadata"]["confidence_score"] = confidence
    
    return extracted

def save_complete_json(announcement_id: str, source: str, parsed_data: Dict, text: str) -> bool:
    """완전한 JSON 데이터 저장"""
    try:
        # attachment_parsed_data 테이블에 저장
        data = {
            "announcement_id": announcement_id,
            "source": source,
            "file_type": "PDF",
            "parsed_data": parsed_data,
            "extracted_text": text[:50000] if len(text) > 50000 else text,  # 텍스트 크기 제한
            "created_at": datetime.now().isoformat()
        }
        
        result = supabase.table('attachment_parsed_data').upsert(data).execute()
        
        # 로컬 JSON 파일로도 저장 (백업 및 MCP 접근용)
        json_dir = "E:\\claude-workspace\\temp\\pdf_json"
        os.makedirs(json_dir, exist_ok=True)
        
        json_file = os.path.join(json_dir, f"{announcement_id}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, ensure_ascii=False, indent=2)
        
        print(f"JSON 저장 완료: {announcement_id}")
        return True
        
    except Exception as e:
        print(f"JSON 저장 실패: {e}")
        return False

def update_main_table(announcement_id: str, source: str, extracted_info: Dict) -> bool:
    """메인 테이블 업데이트"""
    try:
        table_name = "kstartup_complete" if source == "kstartup" else "bizinfo_complete"
        
        # 업데이트할 필드 준비
        update_data = {}
        
        # 공통 필드
        if extracted_info["support_info"]["support_amount"]:
            if source == "kstartup":
                # K-Startup은 컬럼명이 다를 수 있음
                pass
            else:
                update_data["sprt_scale"] = extracted_info["support_info"]["support_amount"]
        
        if extracted_info["target_info"]["target_audience"]:
            if source == "kstartup":
                update_data["aply_trgt_ctnt"] = extracted_info["target_info"]["target_audience"]
            else:
                update_data["sprt_trgt"] = extracted_info["target_info"]["target_audience"]
        
        if extracted_info["document_info"]["required_documents"]:
            docs_text = ", ".join(extracted_info["document_info"]["required_documents"])
            if source == "bizinfo":
                update_data["submit_mtrl"] = docs_text
        
        if extracted_info["evaluation_info"]["evaluation_criteria"]:
            criteria_text = json.dumps(extracted_info["evaluation_info"]["evaluation_criteria"], ensure_ascii=False)
            if source == "bizinfo":
                update_data["slctn_stdr"] = criteria_text
        
        if extracted_info["support_info"]["number_of_selection"]:
            if source == "kstartup":
                update_data["selection_count"] = extracted_info["support_info"]["number_of_selection"]
        
        # 업데이트 실행
        if update_data:
            if source == "kstartup":
                result = supabase.table(table_name).update(update_data).eq("announcement_id", announcement_id).execute()
            else:
                result = supabase.table(table_name).update(update_data).eq("pblanc_id", announcement_id).execute()
            
            print(f"테이블 업데이트 완료: {announcement_id}")
            return True
        
        return False
        
    except Exception as e:
        print(f"테이블 업데이트 실패: {e}")
        return False

def save_for_mcp_summary(announcement_id: str, text: str, extracted_info: Dict):
    """MCP가 읽을 수 있도록 파일 저장"""
    mcp_dir = "E:\\claude-workspace\\temp\\for_summary"
    os.makedirs(mcp_dir, exist_ok=True)
    
    #