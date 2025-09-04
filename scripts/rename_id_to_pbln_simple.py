#!/usr/bin/env python3
"""
BizInfo 파일명 ID → PBLN 형식 변환
ID_xxxx_filename.ext → PBLN_000000000xxxx_filename.ext
"""
import os
import sys
import re
import shutil

# 다운로드 경로
DOWNLOAD_BASE = 'downloads'
BIZINFO_DIR = os.path.join(DOWNLOAD_BASE, 'bizinfo')

def rename_files():
    """ID 형식 파일명을 PBLN 형식으로 변환"""
    if not os.path.exists(BIZINFO_DIR):
        print(f"❌ 폴더가 존재하지 않습니다: {BIZINFO_DIR}")
        return
    
    renamed_count = 0
    error_count = 0
    
    print(f"🔧 파일명 변환 시작: {BIZINFO_DIR}")
    
    for filename in os.listdir(BIZINFO_DIR):
        if filename.startswith('ID_'):
            try:
                # ID_pbln_id_title_number.ext → PBLN_000000000pbln_id_title_number.ext
                match = re.match(r'ID_(\d+)_(.+)', filename)
                if match:
                    pbln_id = match.group(1)
                    rest_of_name = match.group(2)
                    
                    # PBLN 형식으로 변환 (12자리로 패딩)
                    new_filename = f"PBLN_{pbln_id.zfill(12)}_{rest_of_name}"
                    
                    old_path = os.path.join(BIZINFO_DIR, filename)
                    new_path = os.path.join(BIZINFO_DIR, new_filename)
                    
                    # 파일명 변경
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        renamed_count += 1
                        print(f"  ✅ {filename} → {new_filename}")
                    else:
                        print(f"  ⚠️ 이미 존재: {new_filename}")
                else:
                    print(f"  ❌ 패턴 불일치: {filename}")
                    
            except Exception as e:
                error_count += 1
                print(f"  ❌ 변환 실패: {filename} - {str(e)}")
    
    print(f"\n📊 변환 완료:")
    print(f"  ✅ 성공: {renamed_count}개")
    print(f"  ❌ 오류: {error_count}개")

def main():
    """메인 실행"""
    print("=" * 70)
    print("🔧 BizInfo 파일명 PBLN 형식 변환")
    print("=" * 70)
    
    rename_files()
    
    print("=" * 70)
    print("🎉 파일명 변환 작업 완료!")
    print("=" * 70)

if __name__ == "__main__":
    main()