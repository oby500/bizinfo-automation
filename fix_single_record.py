#!/usr/bin/env python
# -*- coding: utf-8 -*-

from supabase import create_client
import os
from dotenv import load_dotenv
import json

def fix_single_record():
    """KS_174787 레코드만 수정"""
    
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
                ('iso-8859-1', 'euc-kr'),
                ('iso-8859-1', 'utf-8'),
                ('cp1252', 'euc-kr'),
                ('cp1252', 'utf-8'),
                ('latin1', 'euc-kr'),
                ('latin1', 'utf-8')
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

    # KS_174787 레코드 가져오기
    result = supabase.table('kstartup_complete').select('id,announcement_id,attachment_urls').eq('announcement_id', 'KS_174787').execute()
    
    if not result.data:
        print("레코드를 찾을 수 없음")
        return
    
    record = result.data[0]
    print(f"레코드 ID: {record['id']}")
    print(f"공고 ID: {record['announcement_id']}")
    
    attachment_urls = record.get('attachment_urls')
    if not attachment_urls:
        print("첨부파일 없음")
        return
    
    # JSON 문자열인 경우 파싱
    if isinstance(attachment_urls, str):
        try:
            attachment_urls = json.loads(attachment_urls)
        except Exception as e:
            print(f"JSON 파싱 실패: {e}")
            return
    
    print("수정 전:")
    updated = False
    for i, att in enumerate(attachment_urls):
        print(f"{i+1}. {att.get('display_filename', 'N/A')}")
        
        # display_filename 수정
        original_display = att.get('display_filename', '')
        fixed_display = fix_korean_encoding(original_display)
        if fixed_display != original_display:
            att['display_filename'] = fixed_display
            updated = True
            
        # original_filename 수정
        original_filename = att.get('original_filename', '')
        fixed_filename = fix_korean_encoding(original_filename)
        if fixed_filename != original_filename:
            att['original_filename'] = fixed_filename
            updated = True
    
    if updated:
        print("\n수정 후:")
        for i, att in enumerate(attachment_urls):
            print(f"{i+1}. {att.get('display_filename', 'N/A')}")
        
        # DB 업데이트
        try:
            update_result = supabase.table('kstartup_complete').update({
                'attachment_urls': attachment_urls
            }).eq('id', record['id']).execute()
            
            print(f"\n✅ 업데이트 성공: {len(update_result.data)}개 레코드")
            
            # 확인
            verify_result = supabase.table('kstartup_complete').select('attachment_urls').eq('id', record['id']).execute()
            if verify_result.data:
                verify_attachment = verify_result.data[0]['attachment_urls']
                if isinstance(verify_attachment, str):
                    verify_attachment = json.loads(verify_attachment)
                print("\n검증 결과:")
                for i, att in enumerate(verify_attachment):
                    print(f"{i+1}. {att.get('display_filename', 'N/A')}")
                    
        except Exception as e:
            print(f"❌ 업데이트 실패: {e}")
    else:
        print("수정할 내용이 없음")

if __name__ == "__main__":
    fix_single_record()