#!/usr/bin/env python3
"""
시간대 처리 수정 스크립트
모든 수집기에서 명시적으로 UTC를 사용하도록 수정
"""

import os
import re
from pathlib import Path

def fix_timezone_in_file(filepath):
    """파일에서 datetime.now()를 datetime.utcnow()로 변경"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 수정 필요 여부 확인
    if 'datetime.now()' not in content:
        return False
    
    # 백업 파일 생성
    backup_path = filepath + '.timezone_backup'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # datetime.now()를 datetime.utcnow()로 변경
    # 단, 출력 메시지나 로그용은 제외
    patterns = [
        (r'datetime\.now\(\)\.isoformat\(\)', r'datetime.utcnow().isoformat()'),
        (r"ann\['created_at'\] = datetime\.now\(\)", r"ann['created_at'] = datetime.utcnow()"),
        (r"ann\['updated_at'\] = datetime\.now\(\)", r"ann['updated_at'] = datetime.utcnow()"),
        (r"'updt_dt': datetime\.now\(\)", r"'updt_dt': datetime.utcnow()"),
    ]
    
    modified = False
    for pattern, replacement in patterns:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            modified = True
    
    if modified:
        # import 문 확인 및 추가
        if 'from datetime import' in content and 'datetime' in content:
            # datetime이 이미 import 되어있으면 utcnow 사용 가능
            pass
        
        # 수정된 내용 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ {filepath}: datetime.now() → datetime.utcnow() 변경 완료")
        return True
    
    # 변경사항 없으면 백업 파일 삭제
    os.remove(backup_path)
    return False

def main():
    """메인 함수"""
    print("=" * 60)
    print("⏰ 시간대 처리 수정 스크립트")
    print("=" * 60)
    
    # 수정 대상 파일들
    target_files = [
        'scripts/kstartup_daily_collector.py',
        'scripts/kstartup_daily_collector_fixed.py',
        'scripts/kstartup_daily_collector_new.py',
        'scripts/bizinfo_complete_processor.py',
        'scripts/bizinfo_excel_collector.py',
    ]
    
    modified_count = 0
    
    for filepath in target_files:
        if os.path.exists(filepath):
            if fix_timezone_in_file(filepath):
                modified_count += 1
        else:
            print(f"⚠️ {filepath}: 파일이 존재하지 않음")
    
    print("\n" + "=" * 60)
    print(f"✅ 총 {modified_count}개 파일 수정 완료")
    print("\n권장사항:")
    print("1. 수정된 파일들을 테스트 환경에서 확인")
    print("2. GitHub Actions에서 UTC 시간대 명시적 설정 추가")
    print("3. 로컬 테스트 시에도 UTC 기준으로 작동하도록 확인")
    print("=" * 60)

if __name__ == "__main__":
    main()