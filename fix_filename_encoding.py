#!/usr/bin/env python
# -*- coding: utf-8 -*-

from supabase import create_client
import os
from dotenv import load_dotenv
import json

def fix_filename_encoding():
    """첨부파일의 깨진 한글 파일명을 수정"""
    
    load_dotenv()
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if not url or not key:
        print('환경변수 오류')
        return

    supabase = create_client(url, key)

    def fix_korean_encoding(corrupted_text):
        """깨진 한글을 복구하는 함수"""
        if not corrupted_text:
            return corrupted_text
            
        try:
            # 여러 인코딩 복구 시도
            encodings = [
                ('iso-8859-1', 'utf-8'),
                ('iso-8859-1', 'euc-kr'),
                ('cp1252', 'utf-8'),
                ('cp1252', 'euc-kr'),
                ('latin1', 'utf-8'),
                ('latin1', 'euc-kr')
            ]
            
            for from_enc, to_enc in encodings:
                try:
                    # 잘못 디코딩된 문자를 올바른 인코딩으로 복구
                    fixed = corrupted_text.encode(from_enc).decode(to_enc)
                    # 한글이 포함되어 있는지 확인
                    if any('\uac00' <= char <= '\ud7af' for char in fixed):
                        return fixed
                except:
                    continue
            
            # 복구 실패 시 원본 반환
            return corrupted_text
            
        except Exception as e:
            print(f"인코딩 복구 실패: {e}")
            return corrupted_text

    # K-Startup 테이블의 모든 레코드 처리
    print("K-Startup 테이블 첨부파일 인코딩 수정 시작...")
    
    # 먼저 총 개수 확인
    count_result = supabase.table('kstartup_complete').select('announcement_id').execute()
    total_count = len(count_result.data) if count_result.data else 0
    print(f"총 {total_count}개 레코드 처리")
    
    # 페이지별로 처리
    page_size = 100
    processed = 0
    fixed_count = 0
    
    for offset in range(0, total_count, page_size):
        result = supabase.table('kstartup_complete').select('id,announcement_id,attachment_urls').range(offset, offset + page_size - 1).execute()
        
        for record in result.data:
            attachment_urls = record.get('attachment_urls')
            
            if attachment_urls and isinstance(attachment_urls, list):
                updated = False
                
                for att in attachment_urls:
                    original_display = att.get('display_filename', '')
                    original_filename = att.get('original_filename', '')
                    
                    # 깨진 문자 패턴 확인
                    corruption_patterns = ['º', 'À', '³', 'â', 'µ', 'µ', '¿', '¹', 'ºñ', 'Ã', '¢', '¾', '÷', 'Æ', 'Ð', 'Å', '°', 'Á', 'ö', 'ÀÏ', '¹', 'Ý', '»', 'ç', 'À', 'ü', 'ÀÎ', 'Å', '¥', 'º', '£', 'ÀÌ', 'Æ', 'Ã', '¸', 'ð', 'Áý', '°', 'ø', 'ï']
                    
                    display_needs_fix = any(pattern in original_display for pattern in corruption_patterns)
                    filename_needs_fix = any(pattern in original_filename for pattern in corruption_patterns)
                    
                    if display_needs_fix:
                        fixed_display = fix_korean_encoding(original_display)
                        if fixed_display != original_display:
                            att['display_filename'] = fixed_display
                            updated = True
                            
                    if filename_needs_fix:
                        fixed_filename = fix_korean_encoding(original_filename)
                        if fixed_filename != original_filename:
                            att['original_filename'] = fixed_filename
                            updated = True
                
                # 수정된 경우 DB 업데이트
                if updated:
                    try:
                        supabase.table('kstartup_complete').update({
                            'attachment_urls': attachment_urls
                        }).eq('id', record['id']).execute()
                        
                        fixed_count += 1
                        print(f"✅ 수정: {record['announcement_id']}")
                        
                    except Exception as e:
                        print(f"❌ 업데이트 실패 {record['announcement_id']}: {e}")
            
            processed += 1
            
        print(f"진행상황: {processed}/{total_count} ({processed/total_count*100:.1f}%)")
    
    print(f"\n✅ K-Startup 테이블 처리 완료: {fixed_count}개 레코드 수정")
    
    # BizInfo 테이블도 동일하게 처리
    print("\nBizInfo 테이블 첨부파일 인코딩 수정 시작...")
    
    count_result = supabase.table('bizinfo_complete').select('id').execute()
    total_count = len(count_result.data) if count_result.data else 0
    print(f"총 {total_count}개 레코드 처리")
    
    processed = 0
    fixed_count = 0
    
    for offset in range(0, total_count, page_size):
        result = supabase.table('bizinfo_complete').select('id,pblanc_id,attachment_urls').range(offset, offset + page_size - 1).execute()
        
        for record in result.data:
            attachment_urls = record.get('attachment_urls')
            
            if attachment_urls and isinstance(attachment_urls, list):
                updated = False
                
                for att in attachment_urls:
                    original_display = att.get('display_filename', '')
                    original_filename = att.get('original_filename', '')
                    
                    # 깨진 문자 패턴 확인
                    corruption_patterns = ['º', 'À', '³', 'â', 'µ', 'µ', '¿', '¹', 'ºñ', 'Ã', '¢', '¾', '÷', 'Æ', 'Ð', 'Å', '°', 'Á', 'ö', 'ÀÏ', '¹', 'Ý', '»', 'ç', 'À', 'ü', 'ÀÎ', 'Å', '¥', 'º', '£', 'ÀÌ', 'Æ', 'Ã', '¸', 'ð', 'Áý', '°', 'ø', 'ï']
                    
                    display_needs_fix = any(pattern in original_display for pattern in corruption_patterns)
                    filename_needs_fix = any(pattern in original_filename for pattern in corruption_patterns)
                    
                    if display_needs_fix:
                        fixed_display = fix_korean_encoding(original_display)
                        if fixed_display != original_display:
                            att['display_filename'] = fixed_display
                            updated = True
                            
                    if filename_needs_fix:
                        fixed_filename = fix_korean_encoding(original_filename)
                        if fixed_filename != original_filename:
                            att['original_filename'] = fixed_filename
                            updated = True
                
                # 수정된 경우 DB 업데이트
                if updated:
                    try:
                        supabase.table('bizinfo_complete').update({
                            'attachment_urls': attachment_urls
                        }).eq('id', record['id']).execute()
                        
                        fixed_count += 1
                        print(f"✅ 수정: {record['pblanc_id']}")
                        
                    except Exception as e:
                        print(f"❌ 업데이트 실패 {record['pblanc_id']}: {e}")
            
            processed += 1
            
        print(f"진행상황: {processed}/{total_count} ({processed/total_count*100:.1f}%)")
    
    print(f"\n✅ BizInfo 테이블 처리 완료: {fixed_count}개 레코드 수정")
    print("\n🎉 모든 테이블의 첨부파일 인코딩 수정 완료!")

if __name__ == "__main__":
    fix_filename_encoding()