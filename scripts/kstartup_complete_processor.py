#!/usr/bin/env python3
"""
K-Startup 첨부파일 및 요약 처리 스크립트
상세페이지에서 첨부파일 URL 추출 및 AI 요약 생성
"""
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client
import logging
import json
import re

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class KStartupProcessor:
    def __init__(self):
        """초기화"""
        # Supabase 연결
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            logging.error("환경변수가 설정되지 않았습니다.")
            sys.exit(1)
            
        self.supabase: Client = create_client(url, key)
        
        # 요청 헤더
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        logging.info("=== K-Startup 첨부파일 처리 시작 ===")
    
    def get_unprocessed_items(self, limit=50):
        """처리 대상 조회"""
        try:
            # 첨부파일이 없거나 요약이 없는 항목 조회
            result = self.supabase.table('kstartup_complete').select(
                'id',
                'announcement_id', 
                'biz_pbanc_nm',
                'detl_pg_url',
                'pbanc_ctnt',
                'aply_trgt_ctnt',
                'pbanc_ntrp_nm',
                'pbanc_rcpt_end_dt',
                'attachment_urls',
                'bsns_sumry',
                'summary'
            ).or_(
                'attachment_urls.is.null',
                'attachment_urls.eq.[]'
            ).limit(limit).execute()
            
            return result.data
        except Exception as e:
            logging.error(f"데이터 조회 오류: {e}")
            return []
    
    def extract_attachments(self, detail_url):
        """상세페이지에서 첨부파일 URL 추출"""
        try:
            # 상세페이지 요청
            response = requests.get(detail_url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                logging.warning(f"페이지 접속 실패: {detail_url}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            attachments = []
            
            # 1. 첨부파일 영역 찾기 (다양한 패턴)
            file_sections = soup.find_all(['div', 'ul', 'dl'], class_=re.compile(r'file|attach|download', re.I))
            
            for section in file_sections:
                # 파일 링크 찾기
                links = section.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    file_name = link.get_text(strip=True) or link.get('title', '') or link.get('alt', '')
                    
                    # 파일 다운로드 링크 패턴
                    if any(pat in href.lower() for pat in ['download', 'file', 'attach', '.pdf', '.hwp', '.doc', '.xlsx', '.ppt']):
                        file_url = urljoin(detail_url, href)
                        
                        # 파일 정보 추출
                        attachment = {
                            'name': file_name[:200] if file_name else '첨부파일',
                            'url': file_url,
                            'type': self.get_file_type(file_name)
                        }
                        
                        # 중복 제거
                        if attachment not in attachments:
                            attachments.append(attachment)
                            logging.info(f"  📎 첨부파일 발견: {attachment['name'][:50]}...")
            
            # 2. onclick 이벤트에서 다운로드 함수 찾기
            onclick_links = soup.find_all('a', onclick=True)
            for link in onclick_links:
                onclick = link.get('onclick', '')
                if 'download' in onclick.lower() or 'file' in onclick.lower():
                    # 파일 ID나 경로 추출 시도
                    match = re.search(r"['\"]([^'\"]*\.(pdf|hwp|doc|docx|xlsx|ppt|pptx|zip))['\"]", onclick, re.I)
                    if match:
                        file_path = match.group(1)
                        file_url = urljoin(detail_url, file_path)
                        file_name = link.get_text(strip=True) or os.path.basename(file_path)
                        
                        attachment = {
                            'name': file_name[:200],
                            'url': file_url,
                            'type': self.get_file_type(file_name)
                        }
                        
                        if attachment not in attachments:
                            attachments.append(attachment)
                            logging.info(f"  📎 첨부파일 발견(onclick): {attachment['name'][:50]}...")
            
            # 3. iframe 내 문서 확인
            iframes = soup.find_all('iframe', src=True)
            for iframe in iframes:
                src = iframe.get('src', '')
                if any(ext in src.lower() for ext in ['.pdf', '.hwp', '.doc']):
                    file_url = urljoin(detail_url, src)
                    file_name = os.path.basename(src) or '임베디드 문서'
                    
                    attachment = {
                        'name': file_name[:200],
                        'url': file_url,
                        'type': self.get_file_type(file_name)
                    }
                    
                    if attachment not in attachments:
                        attachments.append(attachment)
                        logging.info(f"  📎 임베디드 문서 발견: {attachment['name'][:50]}...")
            
            return attachments
            
        except Exception as e:
            logging.error(f"첨부파일 추출 오류 ({detail_url}): {e}")
            return []
    
    def get_file_type(self, filename):
        """파일 타입 추출"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        if '.pdf' in filename_lower:
            return 'pdf'
        elif '.hwp' in filename_lower or '.hwpx' in filename_lower:
            return 'hwp'
        elif '.doc' in filename_lower or '.docx' in filename_lower:
            return 'doc'
        elif '.xls' in filename_lower or '.xlsx' in filename_lower:
            return 'excel'
        elif '.ppt' in filename_lower or '.pptx' in filename_lower:
            return 'ppt'
        elif '.zip' in filename_lower or '.rar' in filename_lower:
            return 'archive'
        else:
            return 'other'
    
    def generate_summary(self, item):
        """AI 스타일 요약 생성"""
        try:
            # 기본 정보 추출
            title = item.get('biz_pbanc_nm', '')
            org = item.get('pbanc_ntrp_nm', '')
            target = item.get('aply_trgt_ctnt', '')
            content = item.get('pbanc_ctnt', '')
            end_date = item.get('pbanc_rcpt_end_dt', '')
            
            # 해시태그 생성
            hashtags = []
            
            # 주관기관 기반 태그
            if org:
                if '창업진흥원' in org:
                    hashtags.append('#창업진흥원')
                elif '중소벤처기업부' in org or '중기부' in org:
                    hashtags.append('#중기부')
                elif '과학기술' in org or '과기' in org:
                    hashtags.append('#과기부')
                elif '지자체' in org or '시청' in org or '도청' in org:
                    hashtags.append('#지자체')
                else:
                    # 기관명을 짧게 해시태그로
                    org_tag = org.split()[0] if org else ''
                    if org_tag and len(org_tag) <= 10:
                        hashtags.append(f'#{org_tag}')
            
            # 지원 대상 기반 태그
            if target:
                if '스타트업' in target or '창업' in target:
                    hashtags.append('#스타트업')
                if '청년' in target:
                    hashtags.append('#청년창업')
                if '여성' in target:
                    hashtags.append('#여성창업')
                if '기술' in target or 'IT' in target or '테크' in target:
                    hashtags.append('#기술창업')
                if '소셜' in target or '사회' in target:
                    hashtags.append('#소셜벤처')
                if '글로벌' in target or '해외' in target:
                    hashtags.append('#글로벌')
            
            # 제목 기반 태그
            if title:
                if '투자' in title or 'IR' in title:
                    hashtags.append('#투자유치')
                if '엑셀러' in title or '액셀러' in title:
                    hashtags.append('#액셀러레이팅')
                if '멘토링' in title:
                    hashtags.append('#멘토링')
                if '교육' in title or '아카데미' in title:
                    hashtags.append('#창업교육')
                if '경진대회' in title or '공모전' in title:
                    hashtags.append('#공모전')
                if '지원금' in title or '보조금' in title:
                    hashtags.append('#지원금')
            
            # 중복 제거 및 상위 5개만
            hashtags = list(dict.fromkeys(hashtags))[:5]
            
            # 요약 생성
            summary_parts = []
            
            # 제목
            summary_parts.append(f"📋 {title}")
            
            # 주관기관
            if org:
                summary_parts.append(f"🏢 주관: {org}")
            
            # 지원대상
            if target:
                target_short = target[:100] + '...' if len(target) > 100 else target
                summary_parts.append(f"👥 대상: {target_short}")
            
            # 마감일
            if end_date:
                summary_parts.append(f"📅 마감: {end_date}")
            
            # 핵심 내용 (간단히)
            if content:
                # 첫 100자만 추출
                content_preview = content[:100].strip()
                if content_preview:
                    summary_parts.append(f"💡 {content_preview}...")
            
            # 해시태그
            if hashtags:
                summary_parts.append(f"🏷️ {' '.join(hashtags)}")
            
            summary = '\n'.join(summary_parts)
            
            return {
                'summary': summary,
                'hashtags': ' '.join(hashtags)
            }
            
        except Exception as e:
            logging.error(f"요약 생성 오류: {e}")
            return {
                'summary': f"📋 {item.get('biz_pbanc_nm', '제목 없음')}",
                'hashtags': '#K-Startup'
            }
    
    def update_item(self, item_id, attachments, summary_data):
        """데이터베이스 업데이트"""
        try:
            update_data = {
                'attachment_urls': attachments,
                'attachment_count': len(attachments),
                'summary': summary_data['summary'],
                'bsns_sumry': summary_data['summary'],  # 기존 컬럼 호환
                'hash_tags': summary_data['hashtags'],
                'attachment_processing_status': {
                    'processed': True,
                    'processed_at': datetime.now().isoformat(),
                    'attachment_found': len(attachments) > 0
                },
                'updated_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table('kstartup_complete').update(
                update_data
            ).eq('id', item_id).execute()
            
            return result.data is not None
            
        except Exception as e:
            logging.error(f"DB 업데이트 오류: {e}")
            return False
    
    def process(self):
        """메인 처리 프로세스"""
        try:
            # 처리 대상 조회
            items = self.get_unprocessed_items(limit=30)  # 한 번에 30개씩
            
            if not items:
                logging.info("처리할 항목이 없습니다.")
                return
            
            logging.info(f"처리 대상: {len(items)}개")
            
            success_count = 0
            attachment_found_count = 0
            error_count = 0
            
            for idx, item in enumerate(items, 1):
                try:
                    logging.info(f"\n[{idx}/{len(items)}] 처리 중: {item['biz_pbanc_nm'][:50]}...")
                    
                    # 1. 첨부파일 추출
                    attachments = []
                    if item.get('detl_pg_url'):
                        attachments = self.extract_attachments(item['detl_pg_url'])
                        if attachments:
                            attachment_found_count += 1
                            logging.info(f"  ✅ 첨부파일 {len(attachments)}개 발견")
                    
                    # 2. 요약 생성
                    summary_data = self.generate_summary(item)
                    
                    # 3. DB 업데이트
                    if self.update_item(item['id'], attachments, summary_data):
                        success_count += 1
                        logging.info(f"  ✅ 업데이트 완료")
                    else:
                        error_count += 1
                        logging.error(f"  ❌ 업데이트 실패")
                    
                    # Rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    error_count += 1
                    logging.error(f"  ❌ 처리 오류: {e}")
                    continue
            
            # 결과 요약
            logging.info("\n" + "="*50)
            logging.info("=== 처리 결과 ===")
            logging.info(f"✅ 성공: {success_count}개")
            logging.info(f"📎 첨부파일 발견: {attachment_found_count}개")
            logging.info(f"❌ 오류: {error_count}개")
            logging.info(f"📊 전체: {len(items)}개")
            
            return success_count > 0
            
        except Exception as e:
            logging.error(f"처리 중 오류: {e}")
            return False

if __name__ == "__main__":
    processor = KStartupProcessor()
    success = processor.process()
    sys.exit(0 if success else 1)
