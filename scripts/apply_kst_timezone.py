#!/usr/bin/env python3
"""
KST(UTC+9) 시간대 적용 스크립트
모든 수집기에서 한국 시간을 사용하도록 수정
"""

import os
import re
from pathlib import Path

def add_kst_function(content):
    """KST 시간 생성 함수 추가"""
    kst_function = '''
def get_kst_time():
    """한국 시간(KST) 반환"""
    from datetime import datetime, timedelta
    utc_now = datetime.utcnow()
    kst_now = utc_now + timedelta(hours=9)
    return kst_now
'''
    
    # 이미 함수가 있는지 확인
    if 'def get_kst_time' in content:
        return content
    
    # import 문 다음에 함수 추가
    lines = content.split('\n')
    import_section_end = 0
    
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith('import') and not line.startswith('from'):
            if i > 0 and (lines[i-1].startswith('import') or lines[i-1].startswith('from')):
                import_section_end = i
                break
    
    if import_section_end > 0:
        lines.insert(import_section_end, kst_function)
        return '\n'.join(lines)
    
    return content

def fix_kstartup_collector(filepath):
    """K-Startup 수집기 수정"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 백업 생성
    backup_path = filepath + '.kst_backup'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # KST 함수 추가
    content = add_kst_function(content)
    
    # datetime import 확인 및 추가
    if 'from datetime import' in content:
        if 'timedelta' not in content:
            content = content.replace('from datetime import datetime', 
                                    'from datetime import datetime, timedelta')
    
    # datetime.now() 대체
    replacements = [
        # K-Startup 수집기 패턴
        (r"ann\['created_at'\] = datetime\.now\(\)\.isoformat\(\)",
         "ann['created_at'] = get_kst_time().isoformat()"),
        (r"ann\['updated_at'\] = datetime\.now\(\)\.isoformat\(\)",
         "ann['updated_at'] = get_kst_time().isoformat()"),
        # 로그 출력용은 제외
        (r"datetime\.now\(\)\.isoformat\(\)(?!.*print)",
         "get_kst_time().isoformat()"),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] {filepath}: KST 시간대 적용 완료")
    return True

def fix_bizinfo_collector(filepath):
    """BizInfo 수집기 수정"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 백업 생성
    backup_path = filepath + '.kst_backup'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # KST 함수 추가
    content = add_kst_function(content)
    
    # datetime import 확인 및 추가
    if 'from datetime import' in content:
        if 'timedelta' not in content:
            content = content.replace('from datetime import datetime', 
                                    'from datetime import datetime, timedelta')
    
    # datetime.now() 대체
    replacements = [
        # BizInfo 패턴
        (r"'updt_dt': datetime\.now\(\)\.isoformat\(\)",
         "'updt_dt': get_kst_time().isoformat()"),
        (r"'created_at': datetime\.now\(\)\.isoformat\(\)",
         "'created_at': get_kst_time().isoformat()"),
        (r"'updated_at': datetime\.now\(\)\.isoformat\(\)",
         "'updated_at': get_kst_time().isoformat()"),
        # D-day 계산용은 KST 사용
        (r"datetime\.now\(\)(?=.*days_left)",
         "get_kst_time()"),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] {filepath}: KST 시간대 적용 완료")
    return True

def main():
    """메인 함수"""
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("KST(UTC+9) 시간대 적용 스크립트")
    print("=" * 60)
    
    # K-Startup 수집기들
    kstartup_files = [
        'scripts/kstartup_daily_collector.py',
        'scripts/kstartup_daily_collector_fixed.py',
        'scripts/kstartup_daily_collector_new.py',
    ]
    
    # BizInfo 수집기들
    bizinfo_files = [
        'scripts/bizinfo_complete_processor.py',
        'scripts/bizinfo_excel_collector.py',
    ]
    
    print("\nK-Startup 수집기 수정:")
    for filepath in kstartup_files:
        if os.path.exists(filepath):
            fix_kstartup_collector(filepath)
        else:
            print(f"[WARNING] {filepath}: 파일이 존재하지 않음")
    
    print("\nBizInfo 수집기 수정:")
    for filepath in bizinfo_files:
        if os.path.exists(filepath):
            fix_bizinfo_collector(filepath)
        else:
            print(f"[WARNING] {filepath}: 파일이 존재하지 않음")
    
    print("\n" + "=" * 60)
    print("[COMPLETE] KST 시간대 적용 완료!")
    print("\n주요 변경사항:")
    print("- datetime.now() -> get_kst_time() (UTC+9)")
    print("- 모든 타임스탬프가 한국 시간 기준으로 저장됩니다")
    print("\n주의사항:")
    print("- Supabase는 여전히 UTC로 표시되지만 실제 값은 KST입니다")
    print("- 데이터 조회 시 시간대 변환이 필요할 수 있습니다")
    print("=" * 60)

if __name__ == "__main__":
    main()