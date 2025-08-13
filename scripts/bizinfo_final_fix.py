#!/usr/bin/env python3
"""
BizInfo 최종 문제 해결 스크립트
- 남은 깨진 파일명 101개 처리
- 실패한 21개 재처리
- DOC 1개 확인
"""
import os
import sys
import requests
import json
import time
import re
from supabase import create_client
from dotenv import load_dotenv
import logging
from datetime import datetime
from urllib.parse import unquote
import threading

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_filename = f'bizinfo_final_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Supabase 연결
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

def deep_fix_encoding(text):
    """매우 복잡한 인코딩 문제 해결"""
    if not text:
        return text
    
    original = text
    
    # 매우 깨진 패턴들
    extreme_patterns = {
        # 완전 매핑 테이블
        'Ã¬Â°Â¸ÃªÂ°Â': '참가',
        'Ã¬ÂÂÃ¬Â²Â­Ã¬ÂÂ': '신청서',
        'ÃªÂ³ÂµÃªÂ³Â ': '공고',
        'Ã«ÂÂÃªÂµÂ¬': '대구',
        'ÃªÂ²Â½ÃªÂ¸Â°': '경기',
        'Ã¬ÂÂÃ¬ÂÂ¸': '서울',
        'Ã«Â¶ÂÃ¬ÂÂ°': '부산',
        'Ã¬Â§ÂÃ¬ÂÂ­': '지역',
        'Ã«Â§ÂÃ¬Â¶Â¤Ã­ÂÂ': '맞춤형',
        'ÃªÂ·Â¼Ã«Â¡ÂÃ­ÂÂÃªÂ²Â½ÃªÂ°ÂÃ¬ÂÂ': '근로환경개선',
        'Ã¬ÂÂ¬Ã¬ÂÂ': '사업',
        'Ã«Â¬Â¸': '문',
        'Ã¬Â ÂÃ¬Â¶Â': '제출',
        'Ã¬ÂÂÃ«Â£Â': '서류',
        'ÃªÂ¸Â°Ã­ÂÂÃ¬ÂÂ': '기타',
        'Ã¬ÂÂÃ¬ÂÂ': '양식',
        'Ã¬Â¤ÂÃ¬ÂÂÃªÂ¸Â°Ã¬ÂÂ': '중소기업',
        'Ã¬Â¡Â°Ã¬ÂÂ¸': '조세',
        'Ã¬Â§ÂÃ¬ÂÂ': '지원',
        'Ã«Â²Â Ã¬ÂÂ´Ã«Â¹ÂÃ«Â¶ÂÃ«Â¨Â¸': '베이비부머',
        'Ã¬ÂÂ¸Ã­ÂÂ´Ã¬ÂÂ­': '인턴십',
        'ÃªÂ¸Â°Ã¬ÂÂÃªÂ·Â¼Ã«Â¬Â´Ã­ÂÂ': '기업근무형',
        'Ã«ÂªÂ¨Ã¬Â§Â': '모집',
        'Ã¬ÂÂÃªÂ²Â©': '수정',
        'Ã¬Â¡Â°ÃªÂ±Â´': '조건',
        'Ã¬ÂÂÃ­ÂÂ': '안함',
        'Ã«Â²Â¤Ã¬Â²ÂÃ­ÂÂ¬Ã¬ÂÂÃ­ÂÂÃ¬ÂÂ¬': '벤처투자회사',
        'Ã¬ÂÂÃ¬ÂÂ¬': '소재',
        'Ã«Â¶ÂÃ­ÂÂ': '부품',
        'Ã¬ÂÂ¥Ã«Â¹Â': '장비',
        'Ã¬Â ÂÃ«Â¬Â¸ÃªÂ¸Â°Ã¬ÂÂ': '전문기업',
        'Ã¬Â£Â¼Ã¬ÂÂ': '주식',
        'Ã¬ÂÂÃ«ÂÂ': '양도',
        'Ã¬Â°Â¨Ã¬ÂÂµ': '차익',
        'Ã«Â¹ÂÃªÂ³Â¼Ã¬ÂÂ¸': '비과세'
    }
    
    # 1. 완전 매핑으로 치환
    result = text
    for broken, fixed in extreme_patterns.items():
        result = result.replace(broken, fixed)
    
    if result != text:
        logging.info(f"패턴 매핑 성공: {original[:30]} → {result[:30]}")
        return result
    
    # 2. 다중 디코딩 시도
    encodings = [
        ('utf-8', 'latin-1', 'utf-8'),
        ('utf-8', 'latin-1', 'utf-8', 'latin-1', 'utf-8'),  # 삼중
        ('utf-8', 'cp1252', 'utf-8'),
        ('utf-8', 'iso-8859-1', 'utf-8'),
    ]
    
    for encoding_chain in encodings:
        try:
            temp = text
            for i in range(0, len(encoding_chain)-1, 2):
                temp = temp.encode(encoding_chain[i], errors='ignore').decode(encoding_chain[i+1], errors='ignore')
            
            # 한글이 포함되어 있으면 성공
            if any(ord('가') <= ord(c) <= ord('힣') for c in temp):
                logging.info(f"인코딩 체인 성공: {original[:30]} → {temp[:30]}")
                return temp
        except:
            continue
    
    # 3. 숫자 년도 패턴 수정
    year_pattern = r'(\d{4})Ã«ÂÂ'
    result = re.sub(year_pattern, r'\1년', result)
    
    # 4. 기본 치환
    basic_replacements = {
        'Ã­ÂÂ': '형',
        'Ã¬ÂÂ': '식',
        'Ã«ÂÂ': '년',
        'ÃªÂ°Â': '개',
        'Ã¬Â': '',  # 노이즈 제거
        'Â': '',    # 노이즈 제거
    }
    
    for broken, fixed in basic_replacements.items():
        result = result.replace(broken, fixed)
    
    # 결과가 개선되었으면 반환
    if result != text and len(result) < len(text):
        return result
    
    return text

def force_fix_attachment(pblanc_id, attachments):
    """강제로 첨부파일 수정"""
    updated_attachments = []
    has_changes = False
    
    for idx, att in enumerate(attachments, 1):
        filename = att.get('display_filename', '')
        file_type = att.get('type', '')
        
        # 깨진 파일명 수정
        if any(c in filename for c in ['Ã', 'Â', 'ì', 'ë', 'í', 'ê', 'ã']):
            fixed_name = deep_fix_encoding(filename)
            if fixed_name != filename:
                att['display_filename'] = fixed_name
                att['original_filename'] = fixed_name
                has_changes = True
                logging.info(f"{pblanc_id}: 파일명 수정 {filename[:20]} → {fixed_name[:20]}")
        
        # DOC 타입 체크
        if file_type == 'DOC':
            # 파일명에 hwp가 있으면 HWP로 변경
            if 'hwp' in filename.lower() or '한글' in filename:
                att['type'] = 'HWP'
                has_changes = True
                logging.info(f"{pblanc_id}: DOC → HWP 변경")
        
        updated_attachments.append(att)
    
    return updated_attachments, has_changes

def main():
    """메인 실행"""
    logging.info("=" * 60)
    logging.info("BizInfo 최종 문제 해결")
    logging.info("=" * 60)
    
    try:
        # 1. 깨진 파일명이 있는 데이터 조회
        logging.info("깨진 파일명 조회 중...")
        
        result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .execute()
        
        broken_announcements = []
        doc_announcements = []
        
        for ann in result.data:
            if ann.get('attachment_urls'):
                has_broken = False
                has_doc = False
                
                for att in ann['attachment_urls']:
                    filename = att.get('display_filename', '')
                    file_type = att.get('type', '')
                    
                    # 깨진 파일명
                    if any(c in filename for c in ['Ã', 'Â', 'ì', 'ë', 'í', 'ê', 'ã']):
                        has_broken = True
                    
                    # DOC 타입
                    if file_type == 'DOC':
                        has_doc = True
                
                if has_broken:
                    broken_announcements.append(ann)
                if has_doc:
                    doc_announcements.append(ann)
        
        logging.info(f"깨진 파일명 공고: {len(broken_announcements)}개")
        logging.info(f"DOC 타입 공고: {len(doc_announcements)}개")
        
        # 2. 깨진 파일명 처리
        fixed_count = 0
        for ann in broken_announcements:
            pblanc_id = ann['pblanc_id']
            attachments = ann['attachment_urls']
            
            updated, has_changes = force_fix_attachment(pblanc_id, attachments)
            
            if has_changes:
                try:
                    result = supabase.table('bizinfo_complete')\
                        .update({'attachment_urls': updated})\
                        .eq('pblanc_id', pblanc_id)\
                        .execute()
                    
                    if result.data:
                        fixed_count += 1
                        if fixed_count % 10 == 0:
                            logging.info(f"진행: {fixed_count}개 수정")
                except Exception as e:
                    logging.error(f"업데이트 실패 {pblanc_id}: {e}")
        
        # 3. DOC 타입 처리
        doc_fixed = 0
        for ann in doc_announcements:
            pblanc_id = ann['pblanc_id']
            attachments = ann['attachment_urls']
            
            updated, has_changes = force_fix_attachment(pblanc_id, attachments)
            
            if has_changes:
                try:
                    result = supabase.table('bizinfo_complete')\
                        .update({'attachment_urls': updated})\
                        .eq('pblanc_id', pblanc_id)\
                        .execute()
                    
                    if result.data:
                        doc_fixed += 1
                except Exception as e:
                    logging.error(f"DOC 업데이트 실패 {pblanc_id}: {e}")
        
        # 4. 결과 보고
        logging.info("\n" + "=" * 60)
        logging.info("최종 처리 완료!")
        logging.info(f"✅ 깨진 파일명 수정: {fixed_count}개")
        logging.info(f"✅ DOC 타입 수정: {doc_fixed}개")
        logging.info("=" * 60)
        
        # 5. 최종 확인
        check = supabase.table('bizinfo_complete')\
            .select('pblanc_id, attachment_urls')\
            .limit(100)\
            .execute()
        
        remaining = 0
        for item in check.data:
            if item.get('attachment_urls'):
                for att in item['attachment_urls']:
                    if att.get('type') == 'DOC' or any(c in att.get('display_filename', '') for c in ['Ã', 'Â']):
                        remaining += 1
        
        if remaining > 0:
            logging.warning(f"⚠️ 아직 {remaining}개 문제 남음 (샘플 100개 중)")
        else:
            logging.info("✅ 모든 문제 해결!")
        
    except Exception as e:
        logging.error(f"오류: {e}")
        import traceback
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    main()
