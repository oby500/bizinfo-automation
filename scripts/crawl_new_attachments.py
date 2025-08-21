#!/usr/bin/env python3
"""
새로운 기업마당 공고의 첨부파일 자동 크롤링
"""
import os
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, parse_qs, urlparse
import time
import re
from datetime import datetime
from supabase import create_client, Client

# 환경변수에서 Supabase 설정 가져오기
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

def get_supabase_client():
    """Supabase 클라이언트 생성"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL과 SUPABASE_KEY 환경변수를 설정하세요")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_unprocessed_announcements(supabase: Client, limit=50):
    """첨부파일 처리가 안 된 공고 가져오기"""
    try:
        result = supabase.table('bizinfo_complete').select(
            'id', 'pblanc_id', 'pblanc_nm', 'detail_url'
        ).or_(
            'attachment_urls.is.null',
            'attachment_urls.eq.[]'
        ).limit(limit).execute()
        
        return result.data
    except Exception as e:
        print(f"데이터베이스 조회 오류: {e}")
        return []

def extract_attachments_from_url(detail_url):
    """URL에서 첨부파일 정보 추출"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(detail_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        unique_files = {}
        
        # getImageFile.do 패턴 찾기
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if 'getImageFile.do' in href:
                full_url = urljoin(detail_url, href)
                clean_url = re.sub(r';jsessionid=[^?]*', '', full_url)
                
                parsed = urlparse(clean_url)
                params = parse_qs(parsed.query)
                
                atch_file_id = params.get('atchFileId', [''])[0]
                file_sn = params.get('fileSn', ['0'])[0]
                unique_key = f"{atch_file_id}_{file_sn}"
                
                if unique_key not in unique_files and atch_file_id:
                    unique_files[unique_key] = {
                        'url': clean_url,
                        'atchFileId': atch_file_id,
                        'fileSn': file_sn,
                        'fileName': text if text and text != '다운로드' else f'첨부파일_{len(unique_files)+1}'
                    }
        
        return list(unique_files.values())
        
    except Exception as e:
        print(f"크롤링 오류 ({detail_url}): {e}")
        return []

def update_attachment_info(supabase: Client, pblanc_id, attachments):
    """데이터베이스에 첨부파일 정보 업데이트"""
    try:
        # 파일명에 공고ID 추가
        for att in attachments:
            original_name = att.get('fileName', '')
            att['originalFileName'] = original_name
            att['fileName'] = f"{pblanc_id}_{original_name}"
        
        # 업데이트
        result = supabase.table('bizinfo_complete').update({
            'attachment_urls': attachments,
            'attachment_processing_status': {
                'processed': True,
                'processedAt': datetime.now().isoformat(),
                'attachmentCount': len(attachments),
                'method': 'auto_crawler'
            }
        }).eq('pblanc_id', pblanc_id).execute()
        
        return True
    except Exception as e:
        print(f"DB 업데이트 오류 ({pblanc_id}): {e}")
        return False

def main():
    """메인 실행 함수"""
    print(f"=== 기업마당 첨부파일 자동 크롤링 시작 ===")
    print(f"실행 시간: {datetime.now()}")
    
    # Supabase 클라이언트 생성
    supabase = get_supabase_client()
    
    # 처리 안 된 공고 가져오기
    announcements = get_unprocessed_announcements(supabase)
    print(f"\n처리할 공고 수: {len(announcements)}개")
    
    # 통계
    processed_count = 0
    attachment_count = 0
    error_count = 0
    
    # 각 공고 처리
    for idx, announcement in enumerate(announcements):
        pblanc_id = announcement['pblanc_id']
        title = announcement['pblanc_nm']
        detail_url = announcement['detail_url']
        
        print(f"\n[{idx + 1}/{len(announcements)}] {pblanc_id}")
        print(f"  제목: {title[:50]}...")
        
        if not detail_url:
            print("  ⚠️  상세 URL 없음")
            continue
        
        # 첨부파일 추출
        attachments = extract_attachments_from_url(detail_url)
        
        if attachments:
            print(f"  ✅ {len(attachments)}개 첨부파일 발견")
            attachment_count += len(attachments)
            
            # DB 업데이트
            if update_attachment_info(supabase, pblanc_id, attachments):
                processed_count += 1
                print("  ✅ DB 업데이트 완료")
            else:
                error_count += 1
                print("  ❌ DB 업데이트 실패")
        else:
            # 첨부파일이 없는 경우도 표시
            update_attachment_info(supabase, pblanc_id, [])
            processed_count += 1
            print("  ℹ️  첨부파일 없음")
        
        # API 부하 방지
        time.sleep(1)
        
        # 배치 처리 (10개마다 잠시 대기)
        if (idx + 1) % 10 == 0:
            print(f"\n--- {idx + 1}개 처리 완료, 잠시 대기 ---")
            time.sleep(5)
    
    # 결과 요약
    print(f"\n\n=== 크롤링 완료 ===")
    print(f"처리된 공고: {processed_count}개")
    print(f"발견된 첨부파일: {attachment_count}개")
    print(f"오류 발생: {error_count}개")
    print(f"완료 시간: {datetime.now()}")
    
    # 로그 파일 저장 (선택사항)
    log_data = {
        'execution_time': datetime.now().isoformat(),
        'processed_count': processed_count,
        'attachment_count': attachment_count,
        'error_count': error_count
    }
    
    with open('crawler_log.json', 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_data, ensure_ascii=False) + '\n')

if __name__ == "__main__":
    main()
