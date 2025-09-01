#!/usr/bin/env python
# -*- coding: utf-8 -*-

from supabase import create_client
import os
from dotenv import load_dotenv
import json

def check_attachment_corruption():
    load_dotenv()
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if not url or not key:
        print('환경변수 오류')
        return

    supabase = create_client(url, key)

    # KS_174787 레코드 확인
    try:
        result = supabase.table('kstartup_complete').select('announcement_id,attachment_urls').eq('announcement_id', 'KS_174787').execute()

        if result.data:
            record = result.data[0]
            print(f"공고ID: {record['announcement_id']}")
            print("="*50)
            
            attachment_urls = record.get('attachment_urls')
            if attachment_urls:
                if isinstance(attachment_urls, str):
                    try:
                        attachment_urls = json.loads(attachment_urls)
                    except Exception as e:
                        print(f"JSON 파싱 실패: {e}")
                        print(f"Raw data: {repr(attachment_urls)}")
                        return
                
                print("첨부파일 데이터:")
                for i, att in enumerate(attachment_urls):
                    print(f"{i+1}.")
                    for key, value in att.items():
                        print(f"  {key}: {repr(value)}")
                    print()
            else:
                print("첨부파일 없음")
        else:
            print("레코드를 찾을 수 없음")
            
        # 추가로 최근 10개 레코드의 첨부파일 상태도 확인
        print("\n" + "="*50)
        print("최근 10개 레코드의 첨부파일 문제 확인:")
        print("="*50)
        
        recent_result = supabase.table('kstartup_complete').select('announcement_id,attachment_urls').order('created_at', desc=True).limit(10).execute()
        
        corrupted_count = 0
        for record in recent_result.data:
            attachment_urls = record.get('attachment_urls')
            if attachment_urls and isinstance(attachment_urls, list):
                has_corruption = False
                for att in attachment_urls:
                    filename = att.get('display_filename', '')
                    # 깨진 문자 패턴 확인
                    corruption_patterns = ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'ð', 'þ', 'ï', '¿', '½', 'Ã', 'Â', 'º', 'À', '³', 'Ê', 'Æ']
                    if any(pattern in filename for pattern in corruption_patterns):
                        has_corruption = True
                        break
                
                if has_corruption:
                    corrupted_count += 1
                    print(f"문제 발견: {record['announcement_id']}")
        
        print(f"\n최근 10개 중 {corrupted_count}개에서 문자 깨짐 발견")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_attachment_corruption()