#!/usr/bin/env python3
"""
기업마당 첨부파일 크롤러 - 원래 작동하던 방식 복구
8월 8일까지 정상 작동했던 HTTP 크롤링 방식
"""
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse
from supabase import create_client
from datetime import datetime

def extract_file_type(text):
    """파일명에서 확장자 추측"""
    text_lower = text.lower()
    if '.hwp' in text_lower or '한글' in text_lower:
        return 'HWP'
    elif '.pdf' in text_lower:
        return 'PDF'
    elif '.doc' in text_lower or 'word' in text_lower:
        return 'DOCX'
    elif '.xls' in text_lower or 'excel' in text_lower:
        return 'XLSX'
    elif '.zip' in text_lower or '.rar' in text_lower:
        return 'ZIP'
    elif '.png' in text_lower or '.jpg' in text_lower or '.gif' in text_lower:
        return 'IMAGE'
    elif '.ppt' in text_lower:
        return 'PPT'
    else:
        return 'UNKNOWN'

def main():
    print("=" * 60)
    print(" 기업마당 첨부파일 크롤링 (8월 8일 버전 복구)")
    print("=" * 60)
    
    # Supabase 연결
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ 환경변수가 설정되지 않았습니다.")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    # 세션 생성 (쿠키 유지)
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    # 처리 대상 조회 - attachment_urls가 없거나 비어있는 데이터
    print("1. 처리 대상 조회 중...")
    try:
        # attachment_urls가 null이거나 빈 배열인 데이터
        response = supabase.table('bizinfo_complete').select(
            'id', 'pblanc_id', 'pblanc_nm', 'dtl_url', 'bsns_sumry', 'attachment_urls'
        ).or_(
            'attachment_urls.is.null',
            'attachment_urls.eq.[]'
        ).limit(100).execute()
        
        targets = response.data
        
        # 추가로 bsns_sumry가 짧은 것도 포함
        if len(targets) < 100:
            response2 = supabase.table('bizinfo_complete').select(
                'id', 'pblanc_id', 'pblanc_nm', 'dtl_url', 'bsns_sumry', 'attachment_urls'
            ).limit(500).execute()
            
            for item in response2.data:
                # attachment_urls가 없거나 bsns_sumry가 150자 미만
                if (not item.get('attachment_urls') or item.get('attachment_urls') == []) or \
                   (item.get('bsns_sumry') and len(item.get('bsns_sumry', '')) < 150):
                    if item['id'] not in [t['id'] for t in targets]:
                        targets.append(item)
                        if len(targets) >= 100:
                            break
        
        print(f"✅ 처리 대상: {len(targets)}개")
        
    except Exception as e:
        print(f"❌ 데이터 조회 오류: {e}")
        sys.exit(1)
    
    if not targets:
        print("처리할 데이터가 없습니다.")
        return
    
    # 메인 페이지 방문 (세션 쿠키 획득)
    print("\n2. 세션 초기화 중...")
    try:
        main_page = session.get('https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do')
        print(f"✅ 세션 쿠키 획득: {len(session.cookies)}개")
    except:
        print("⚠️ 메인 페이지 접속 실패 (계속 진행)")
    
    success_count = 0
    error_count = 0
    attachment_total = 0
    
    print("\n3. 크롤링 시작...")
    print("-" * 60)
    
    for idx, data in enumerate(targets, 1):
        try:
            pblanc_id = data['pblanc_id']
            pblanc_nm = data['pblanc_nm'][:50] + "..." if len(data['pblanc_nm']) > 50 else data['pblanc_nm']
            dtl_url = data.get('dtl_url')
            
            print(f"\n[{idx}/{len(targets)}] {pblanc_nm}")
            
            if not dtl_url:
                print("  ⚠️ 상세 URL 없음")
                continue
            
            # 상세페이지 접속
            try:
                response = session.get(dtl_url, timeout=15)
                response.encoding = 'utf-8'
                
                if response.status_code != 200:
                    print(f"  ⚠️ HTTP {response.status_code}")
                    error_count += 1
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 첨부파일 정보 추출
                attachments = []
                
                # 방법 1: atchFileId가 있는 모든 링크 찾기
                file_links = soup.find_all('a', href=lambda x: x and 'atchFileId=' in x)
                
                for link in file_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # URL에서 파라미터 추출
                    if 'atchFileId=' in href:
                        # atchFileId 추출
                        atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                        
                        # fileSn 추출 (없으면 0)
                        file_sn = '0'
                        if 'fileSn=' in href:
                            file_sn = href.split('fileSn=')[1].split('&')[0]
                        
                        # 파일 타입 추측
                        file_type = extract_file_type(text)
                        
                        # 직접 다운로드 URL 구성 (세션 없이도 접근 가능)
                        direct_url = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                        
                        attachment = {
                            'url': direct_url,
                            'type': file_type,
                            'safe_filename': f"{pblanc_id}_{len(attachments)+1:02d}.{file_type.lower()}",
                            'display_filename': text or f"첨부파일_{len(attachments)+1}",
                            'original_filename': text,
                            'text': text,
                            'params': {
                                'atchFileId': atch_file_id,
                                'fileSn': file_sn
                            }
                        }
                        
                        # 중복 체크
                        is_duplicate = any(
                            a['params']['atchFileId'] == atch_file_id and 
                            a['params']['fileSn'] == file_sn 
                            for a in attachments
                        )
                        
                        if not is_duplicate:
                            attachments.append(attachment)
                
                # 방법 2: 첨부파일 영역에서 추가 찾기
                if not attachments:
                    file_areas = soup.find_all(['div', 'ul', 'dl'], class_=['file', 'attach', 'download'])
                    for area in file_areas:
                        links = area.find_all('a', href=True)
                        for link in links:
                            href = link.get('href', '')
                            if 'atchFileId=' in href:
                                atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                                file_sn = href.split('fileSn=')[1].split('&')[0] if 'fileSn=' in href else '0'
                                
                                attachments.append({
                                    'url': f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}",
                                    'type': 'UNKNOWN',
                                    'safe_filename': f"{pblanc_id}_{len(attachments)+1:02d}.unknown",
                                    'display_filename': link.get_text(strip=True) or f"첨부파일_{len(attachments)+1}",
                                    'params': {'atchFileId': atch_file_id, 'fileSn': file_sn}
                                })
                
                # 상세 내용 추출 (요약 개선용)
                content_parts = []
                
                # 본문 내용 찾기
                content_areas = soup.find_all(['div', 'td'], class_=['view_cont', 'content', 'board_view'])
                for area in content_areas:
                    text = area.get_text(strip=True)
                    if text and len(text) > 50:
                        content_parts.append(text[:500])
                        break
                
                # 요약 생성/개선
                current_summary = data.get('bsns_sumry', '')
                
                if not current_summary or len(current_summary) < 150:
                    summary_parts = []
                    summary_parts.append(f"📋 {data['pblanc_nm']}")
                    
                    if content_parts:
                        summary_parts.append(f"📝 {content_parts[0][:200]}...")
                    
                    if attachments:
                        file_types = list(set([a['type'] for a in attachments]))
                        summary_parts.append(f"📎 첨부: {', '.join(file_types)} ({len(attachments)}개)")
                    
                    new_summary = "\n".join(summary_parts)
                else:
                    new_summary = current_summary
                    # 첨부파일 정보만 추가
                    if attachments and '📎' not in current_summary:
                        file_types = list(set([a['type'] for a in attachments]))
                        new_summary += f"\n📎 첨부: {', '.join(file_types)} ({len(attachments)}개)"
                
                # DB 업데이트
                update_data = {}
                
                if attachments:
                    update_data['attachment_urls'] = attachments
                    attachment_total += len(attachments)
                
                if len(new_summary) > len(current_summary):
                    update_data['bsns_sumry'] = new_summary
                
                if update_data:
                    result = supabase.table('bizinfo_complete').update(
                        update_data
                    ).eq('id', data['id']).execute()
                    
                    success_count += 1
                    print(f"  ✅ 업데이트 성공 (첨부: {len(attachments)}개, 요약: {len(new_summary)}자)")
                else:
                    print(f"  ⏭️ 이미 처리됨")
                
            except requests.exceptions.RequestException as e:
                print(f"  ❌ HTTP 요청 실패: {e}")
                error_count += 1
            
            # 요청 간격 (서버 부하 방지)
            time.sleep(1)
            
        except Exception as e:
            error_count += 1
            print(f"  ❌ 처리 오류: {e}")
            continue
    
    # 결과 출력
    print("\n" + "=" * 60)
    print(" 크롤링 완료")
    print("=" * 60)
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패: {error_count}개")
    print(f"📎 첨부파일: {attachment_total}개")
    print("=" * 60)

if __name__ == "__main__":
    main()