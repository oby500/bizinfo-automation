#!/usr/bin/env python3
"""
K-Startup 데이터 품질 개선 스크립트 (수정 버전)
- 상세 페이지에서 실제 파일명 추출
- unknown 확장자 문제 해결
- 요약 품질 개선
- 해시태그 정상화
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
from supabase import create_client
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)

class KStartupEnhancer:
    def __init__(self):
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
        
        if not url or not key:
            logging.error("환경변수 설정 필요")
            sys.exit(1)
            
        self.supabase = create_client(url, key)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_data_to_enhance(self, limit=100):
        """개선이 필요한 데이터 조회"""
        logging.info("품질 개선 필요 데이터 조회 중...")
        
        # 1. unknown 확장자를 가진 데이터
        unknown_ext = self.supabase.table('kstartup_complete')\
            .select('*')\
            .like('attachment_urls', '%unknown%')\
            .limit(limit)\
            .execute()
        
        # 2. 품질 낮은 요약 데이터
        poor_summary = self.supabase.table('kstartup_complete')\
            .select('*')\
            .or_('bsns_sumry.like.%모집중%,bsns_sumry.like.%URL복사%,bsns_sumry.like.%홈페이지%')\
            .limit(limit)\
            .execute()
        
        # 3. 해시태그 없는 데이터
        no_hashtag = self.supabase.table('kstartup_complete')\
            .select('*')\
            .or_('hash_tag.is.null,hash_tag.eq.')\
            .limit(limit)\
            .execute()
        
        # 중복 제거하여 병합
        all_ids = set()
        items_to_process = []
        
        for item in (unknown_ext.data or []) + (poor_summary.data or []) + (no_hashtag.data or []):
            if item['id'] not in all_ids:
                all_ids.add(item['id'])
                items_to_process.append(item)
        
        logging.info(f"개선 대상: {len(items_to_process)}개")
        return items_to_process[:limit]
    
    def crawl_detail_page(self, item):
        """상세 페이지에서 실제 첨부파일 정보 추출"""
        try:
            # detl_pg_url이 없으면 생성
            detail_url = item.get('detl_pg_url')
            if not detail_url and item.get('announcement_id'):
                # K-Startup ID에서 실제 ID 추출
                ann_id = item['announcement_id']
                if ann_id.startswith('KS_'):
                    # KS_174371 형식에서 174371 추출
                    real_id = ann_id.split('_')[1] if '_' in ann_id else ann_id
                    detail_url = f"http://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={real_id}&page=1&schStr=&pbancEndYn=Y"
            
            if not detail_url:
                return None
            
            # URL 정리
            if not detail_url.startswith('http'):
                detail_url = f"http://www.k-startup.go.kr{detail_url}"
            
            response = self.session.get(detail_url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = {
                'id': item['id'],
                'attachments': [],
                'content': '',
                'details': {}
            }
            
            # 1. 첨부파일 영역에서 실제 파일명 추출
            # K-Startup은 file_bg 클래스 내의 title 속성에 실제 파일명이 있음
            file_elements = soup.find_all('span', class_='file_bg')
            for idx, elem in enumerate(file_elements, 1):
                title = elem.get('title', '')
                if title:
                    # 실제 파일명과 확장자 추출
                    file_ext = self.extract_extension(title)
                    safe_name = f"KS_{item['announcement_id']}_{idx:02d}.{file_ext}"
                    
                    # 기존 attachment_urls에서 URL 찾기
                    existing_urls = item.get('attachment_urls', [])
                    if idx <= len(existing_urls):
                        url = existing_urls[idx-1].get('url', '')
                        result['attachments'].append({
                            'url': url,
                            'safe_filename': safe_name,
                            'display_filename': title,
                            'original_filename': title
                        })
            
            # 2. 테이블에서 상세 정보 추출
            detail_table = soup.find('table', class_='view_tbl')
            if detail_table:
                rows = detail_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True)
                        value = td.get_text(strip=True)
                        if key and value:
                            result['details'][key] = value
            
            # 3. 본문 내용 추출
            content_area = soup.find('div', class_='view_cont')
            if content_area:
                result['content'] = content_area.get_text(strip=True)[:2000]
            
            return result
            
        except Exception as e:
            logging.error(f"크롤링 오류 (ID: {item['id']}): {e}")
            return None
    
    def extract_extension(self, filename):
        """파일명에서 확장자 추출"""
        if '.' in filename:
            ext = filename.split('.')[-1].lower()
            # 일반적인 문서 확장자 검증
            valid_exts = ['pdf', 'hwp', 'hwpx', 'doc', 'docx', 'xls', 'xlsx', 
                         'ppt', 'pptx', 'zip', 'jpg', 'jpeg', 'png', 'gif']
            if ext in valid_exts:
                return ext
        # 기본값
        return 'pdf'  # K-Startup은 대부분 PDF
    
    def generate_enhanced_summary(self, item, crawled_data):
        """개선된 요약 생성"""
        title = item.get('biz_pbanc_nm', '')
        details = crawled_data.get('details', {}) if crawled_data else {}
        content = crawled_data.get('content', '') if crawled_data else item.get('pbanc_ctnt', '')
        
        # 무의미한 제목 필터링
        invalid_titles = ['모집중', 'URL복사', '홈페이지 바로가기', '모집마감']
        if title in invalid_titles:
            # 실제 제목 찾기
            if details.get('사업명'):
                title = details['사업명']
            elif details.get('공고명'):
                title = details['공고명']
        
        summary_parts = []
        
        # 제목
        if title:
            summary_parts.append(f"📋 {title}")
        
        # 주관기관
        org = item.get('pbanc_ntrp_nm') or details.get('주관기관') or details.get('운영기관')
        if org:
            summary_parts.append(f"🏢 주관: {org}")
        
        # 지원대상
        target = item.get('aply_trgt_ctnt') or details.get('지원대상') or details.get('신청자격')
        if target:
            target_text = target[:100] + "..." if len(target) > 100 else target
            summary_parts.append(f"👥 대상: {target_text}")
        
        # 지원내용
        support = details.get('지원내용') or details.get('사업내용') or details.get('지원규모')
        if support:
            support_text = support[:100] + "..." if len(support) > 100 else support
            summary_parts.append(f"💰 지원: {support_text}")
        
        # 신청기간
        start_date = item.get('pbanc_rcpt_bgng_dt')
        end_date = item.get('pbanc_rcpt_end_dt')
        if end_date:
            summary_parts.append(f"📅 마감: {end_date}")
        elif details.get('신청기간'):
            summary_parts.append(f"📅 기간: {details['신청기간']}")
        
        # 첨부파일 개수
        attach_count = len(crawled_data.get('attachments', [])) if crawled_data else item.get('attachment_count', 0)
        if attach_count > 0:
            summary_parts.append(f"📎 첨부: {attach_count}개")
        
        return '\n'.join(summary_parts) if summary_parts else f"📋 {title}"
    
    def generate_hashtags(self, item, crawled_data):
        """해시태그 생성 (문자열 형식으로)"""
        title = item.get('biz_pbanc_nm', '')
        content = (crawled_data.get('content', '') if crawled_data else item.get('pbanc_ctnt', ''))[:1000]
        org = item.get('pbanc_ntrp_nm', '')
        
        hashtags = []
        
        # 분야별 키워드 매핑
        keyword_map = {
            '창업': '#창업',
            '스타트업': '#스타트업',
            'R&D': '#연구개발',
            '기술': '#기술개발',
            '투자': '#투자유치',
            '수출': '#수출지원',
            '마케팅': '#마케팅',
            '교육': '#교육',
            '멘토링': '#멘토링',
            '컨설팅': '#컨설팅',
            '사업화': '#사업화',
            '시제품': '#시제품제작',
            '특허': '#특허',
            '인증': '#인증지원',
            '자금': '#자금지원',
            '보증': '#보증',
            '대출': '#정책자금',
            'AI': '#인공지능',
            '빅데이터': '#빅데이터',
            '블록체인': '#블록체인',
            '바이오': '#바이오',
            '환경': '#그린뉴딜',
            '에너지': '#에너지',
            '문화': '#문화콘텐츠'
        }
        
        text = (title + ' ' + content + ' ' + org).lower()
        
        for keyword, tag in keyword_map.items():
            if keyword.lower() in text:
                if tag not in hashtags:
                    hashtags.append(tag)
        
        # 기관명 해시태그
        if org and len(org) < 20:
            org_tag = f"#{org.replace(' ', '')}"
            if org_tag not in hashtags:
                hashtags.append(org_tag)
        
        # 기본 태그
        if not hashtags:
            hashtags = ['#정부지원사업', '#K스타트업']
        
        # 최대 5개, 공백으로 구분된 문자열로 반환
        return ' '.join(hashtags[:5])
    
    def process_item(self, item):
        """개별 아이템 처리"""
        try:
            # 상세 페이지 크롤링
            crawled = self.crawl_detail_page(item)
            
            update_data = {}
            
            # 1. 첨부파일 업데이트 (unknown 확장자 수정)
            if crawled and crawled.get('attachments'):
                update_data['attachment_urls'] = crawled['attachments']
                update_data['attachment_count'] = len(crawled['attachments'])
            elif item.get('attachment_urls'):
                # 크롤링 실패시 기존 unknown 파일명만 개선
                fixed_attachments = []
                for idx, att in enumerate(item['attachment_urls'], 1):
                    if isinstance(att, dict):
                        att['safe_filename'] = f"KS_{item['announcement_id']}_{idx:02d}.pdf"
                        att['display_filename'] = att.get('display_filename', f"첨부파일_{idx}")
                        fixed_attachments.append(att)
                if fixed_attachments:
                    update_data['attachment_urls'] = fixed_attachments
            
            # 2. 요약 개선
            enhanced_summary = self.generate_enhanced_summary(item, crawled)
            if enhanced_summary and len(enhanced_summary) > 20:
                update_data['bsns_sumry'] = enhanced_summary
            
            # 3. 해시태그 생성 (문자열 형식)
            hashtags = self.generate_hashtags(item, crawled)
            if hashtags:
                update_data['hash_tag'] = hashtags
            
            # 4. 상세 내용 업데이트
            if crawled and crawled.get('content') and len(crawled['content']) > 100:
                update_data['pbanc_ctnt'] = crawled['content']
            
            # DB 업데이트
            if update_data:
                self.supabase.table('kstartup_complete')\
                    .update(update_data)\
                    .eq('id', item['id'])\
                    .execute()
                
                logging.info(f"✅ ID {item['id']} ({item.get('biz_pbanc_nm', 'Unknown')[:30]}) 개선 완료")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"처리 오류 (ID: {item['id']}): {e}")
            return False
    
    def run(self, limit=100):
        """메인 실행"""
        start_time = time.time()
        
        logging.info("="*60)
        logging.info("   K-Startup 데이터 품질 개선 시작")
        logging.info("="*60)
        
        # 1. 개선 필요 데이터 조회
        items = self.get_data_to_enhance(limit)
        
        if not items:
            logging.info("개선할 데이터가 없습니다.")
            return
        
        # 2. 병렬 처리
        success_count = 0
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.process_item, item): item for item in items}
            
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
                
                if success_count % 10 == 0:
                    logging.info(f"진행 상황: {success_count}/{len(items)}")
        
        # 3. 결과 통계
        elapsed = time.time() - start_time
        
        logging.info("\n" + "="*60)
        logging.info("   처리 완료")
        logging.info("="*60)
        logging.info(f"✅ 개선 완료: {success_count}/{len(items)}개")
        logging.info(f"⏱️ 소요 시간: {elapsed:.1f}초")
        if success_count > 0:
            logging.info(f"📊 평균 속도: {success_count/elapsed:.1f}개/초")
        
        # 4. 개선 후 통계
        self.print_final_stats()
    
    def print_final_stats(self):
        """최종 통계 출력"""
        # unknown 확장자 개수
        unknown_count = self.supabase.table('kstartup_complete')\
            .select('id', count='exact')\
            .like('attachment_urls', '%unknown%')\
            .execute()
        
        # 해시태그 있는 데이터
        with_hashtag = self.supabase.table('kstartup_complete')\
            .select('id', count='exact')\
            .neq('hash_tag', '')\
            .execute()
        
        # 전체 데이터
        total = self.supabase.table('kstartup_complete')\
            .select('id', count='exact')\
            .execute()
        
        logging.info("\n📊 현재 데이터 품질 상태")
        logging.info(f"전체 데이터: {total.count}개")
        logging.info(f"Unknown 확장자 남은 개수: {unknown_count.count}개")
        logging.info(f"해시태그 보유: {with_hashtag.count}개 ({with_hashtag.count/total.count*100:.1f}%)")

if __name__ == "__main__":
    import sys
    
    # 명령줄 인자로 처리 개수 지정 가능
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    
    enhancer = KStartupEnhancer()
    enhancer.run(limit=limit)
