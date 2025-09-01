#!/usr/bin/env python3
"""
첨부파일 수집 테스트 - 파일 타입 감지 확인
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from dotenv import load_dotenv
from supabase import create_client
import json

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

def test_specific_announcement(announcement_id):
    """특정 공고의 첨부파일 타입 확인"""
    print(f"\n{'='*70}")
    print(f"📋 공고 {announcement_id} 첨부파일 타입 확인")
    print(f"{'='*70}")
    
    # 데이터베이스에서 해당 공고 조회
    result = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, attachment_urls, attachment_count')\
        .eq('announcement_id', announcement_id)\
        .execute()
    
    if not result.data:
        print(f"❌ 공고 {announcement_id}를 찾을 수 없습니다.")
        return
    
    record = result.data[0]
    print(f"📌 공고명: {record.get('biz_pbanc_nm', 'No Title')}")
    print(f"📎 첨부파일 수: {record.get('attachment_count', 0)}개")
    
    # attachment_urls 파싱
    attachment_urls = record.get('attachment_urls')
    if not attachment_urls:
        print("   첨부파일 없음")
        return
    
    try:
        if isinstance(attachment_urls, str):
            attachments = json.loads(attachment_urls)
        else:
            attachments = attachment_urls
    except:
        print("   ⚠️ 첨부파일 정보 파싱 실패")
        return
    
    # 파일 타입별 분류
    type_counts = {}
    file_list = {}
    
    for i, att in enumerate(attachments, 1):
        file_type = att.get('type', 'UNKNOWN')
        file_name = att.get('text', att.get('display_filename', '파일명 없음'))
        file_ext = att.get('file_extension', '')
        
        # 타입별 카운트
        type_counts[file_type] = type_counts.get(file_type, 0) + 1
        
        # 타입별 파일 리스트
        if file_type not in file_list:
            file_list[file_type] = []
        file_list[file_type].append({
            'name': file_name,
            'ext': file_ext,
            'url': att.get('url', '')[:80] + '...' if len(att.get('url', '')) > 80 else att.get('url', '')
        })
    
    # 결과 출력
    print(f"\n📊 파일 타입 분석:")
    print(f"   전체: {len(attachments)}개")
    for file_type, count in sorted(type_counts.items()):
        print(f"   - {file_type}: {count}개")
    
    print(f"\n📂 파일 상세:")
    for file_type, files in sorted(file_list.items()):
        print(f"\n   [{file_type}] ({len(files)}개)")
        for f in files[:3]:  # 각 타입별로 최대 3개만 출력
            print(f"      • {f['name']}")
            if f['ext']:
                print(f"        확장자: .{f['ext']}")
        if len(files) > 3:
            print(f"      ... 외 {len(files)-3}개")
    
    # HWP/HWPX 파일 유무 확인
    hwp_count = type_counts.get('HWP', 0) + type_counts.get('HWPX', 0)
    if hwp_count > 0:
        print(f"\n✅ 변환 대상 HWP 파일: {hwp_count}개")
    else:
        print(f"\n❌ 변환 대상 HWP 파일 없음 (처리 스킵)")
    
    return type_counts

def test_recent_announcements():
    """최근 공고들의 파일 타입 분포 확인"""
    print(f"\n{'='*70}")
    print(f"📊 최근 공고 첨부파일 타입 분포")
    print(f"{'='*70}")
    
    # 최근 10개 공고 조회
    result = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, attachment_urls, attachment_count')\
        .gt('attachment_count', 0)\
        .order('created_at', desc=True)\
        .limit(10)\
        .execute()
    
    if not result.data:
        print("첨부파일이 있는 공고가 없습니다.")
        return
    
    total_counts = {}
    total_files = 0
    
    for record in result.data:
        announcement_id = record['announcement_id']
        attachment_urls = record.get('attachment_urls')
        
        if not attachment_urls:
            continue
        
        try:
            if isinstance(attachment_urls, str):
                attachments = json.loads(attachment_urls)
            else:
                attachments = attachment_urls
        except:
            continue
        
        # 타입별 카운트
        for att in attachments:
            file_type = att.get('type', 'UNKNOWN')
            total_counts[file_type] = total_counts.get(file_type, 0) + 1
            total_files += 1
    
    # 결과 출력
    print(f"\n📈 전체 통계 (최근 10개 공고)")
    print(f"   총 첨부파일: {total_files}개")
    print(f"\n   타입별 분포:")
    for file_type, count in sorted(total_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_files * 100) if total_files > 0 else 0
        print(f"   - {file_type}: {count}개 ({percentage:.1f}%)")
    
    # HWP 비율
    hwp_total = total_counts.get('HWP', 0) + total_counts.get('HWPX', 0)
    hwp_percentage = (hwp_total / total_files * 100) if total_files > 0 else 0
    print(f"\n   📝 HWP/HWPX 파일: {hwp_total}개 ({hwp_percentage:.1f}%)")

def main():
    """메인 실행"""
    print("="*70)
    print("🔍 첨부파일 타입 감지 테스트")
    print("="*70)
    
    # 특정 문제가 있던 공고 테스트
    test_specific_announcement("KS_174648")
    test_specific_announcement("KS_173508")
    
    # 최근 공고들 통계
    test_recent_announcements()
    
    print("\n" + "="*70)
    print("✅ 테스트 완료")
    print("="*70)
    
    print("\n💡 다음 단계:")
    print("1. 타입이 'FILE'로 표시된 항목들은 재수집이 필요합니다")
    print("2. HWP/HWPX 타입만 PDF 변환 대상입니다")
    print("3. PDF/IMAGE 타입은 변환 없이 스킵됩니다")

if __name__ == "__main__":
    main()