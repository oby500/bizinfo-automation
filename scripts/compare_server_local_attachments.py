import os
import json
from collections import defaultdict
from supabase import create_client
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv('E:/gov-support-automation/config/.env')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Supabase 클라이언트 생성
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_id_from_filename(filename):
    """파일명에서 ID 추출"""
    # K-Startup: KS_숫자
    if 'KS_' in filename:
        parts = filename.split('KS_')[1].split('_')[0]
        return f'KS_{parts}'
    # 기업마당: PBLN_숫자
    elif 'PBLN_' in filename:
        # PBLN_000000000114380 형태 추출
        import re
        match = re.search(r'PBLN_\d+', filename)
        if match:
            return match.group()
    return None

def analyze_attachments(source_name, table_name, id_field, download_dir):
    """특정 소스의 첨부파일 비교 분석"""
    print(f"\n{'='*80}")
    print(f"{source_name} 첨부파일 분석")
    print('='*80)
    
    # 1. 서버 데이터 가져오기
    print(f"\n1. 서버 데이터 조회 중...")
    server_data = {}
    
    try:
        # attachment_urls가 있는 레코드만
        result = supabase.table(table_name).select(f'{id_field}, attachment_urls').not_.is_('attachment_urls', 'null').execute()
        
        for row in result.data:
            record_id = row.get(id_field)
            attachment_urls = row.get('attachment_urls', [])
            
            if attachment_urls:
                # dict 형태인 경우 처리
                url_list = []
                if isinstance(attachment_urls, list):
                    for item in attachment_urls:
                        if isinstance(item, dict):
                            # dict에서 URL과 타입 추출
                            url = item.get('url', '')
                            file_type = item.get('type', '')
                            filename = item.get('text', '') or item.get('display_filename', '')
                            url_list.append({
                                'url': url,
                                'type': file_type,
                                'filename': filename
                            })
                        else:
                            # 단순 문자열 URL
                            url_list.append({
                                'url': str(item),
                                'type': 'UNKNOWN',
                                'filename': str(item).split('/')[-1] if '/' in str(item) else str(item)
                            })
                
                if record_id and url_list:
                    server_data[record_id] = url_list
        
        print(f"  - 서버에 첨부파일이 있는 레코드: {len(server_data)}개")
        
    except Exception as e:
        print(f"  - 서버 조회 오류: {e}")
        return
    
    # 2. 로컬 파일 스캔
    print(f"\n2. 로컬 파일 스캔 중...")
    local_files = defaultdict(list)
    
    if os.path.exists(download_dir):
        for filename in os.listdir(download_dir):
            if os.path.isfile(os.path.join(download_dir, filename)):
                record_id = extract_id_from_filename(filename)
                if record_id:
                    # 파일 타입 확인
                    if '.pdf' in filename.lower():
                        file_type = 'PDF'
                    elif '.zip' in filename.lower():
                        file_type = 'ZIP'
                    elif '.hwp' in filename.lower():
                        file_type = 'HWP'
                    elif '.doc' in filename.lower():
                        file_type = 'DOC'
                    elif '.xls' in filename.lower():
                        file_type = 'XLS'
                    elif 'jsessionid' in filename.lower():
                        file_type = 'SESSION'
                    else:
                        file_type = 'OTHER'
                    
                    local_files[record_id].append({
                        'filename': filename,
                        'type': file_type
                    })
    
    print(f"  - 로컬에 파일이 있는 레코드: {len(local_files)}개")
    
    # 3. 비교 분석
    print(f"\n3. 비교 분석...")
    
    # 통계
    total_server_files = 0
    total_local_files = 0
    missing_records = []
    missing_files = []
    type_mismatch = []
    
    # 서버에는 있지만 로컬에 없는 경우
    for record_id, server_urls in server_data.items():
        total_server_files += len(server_urls)
        
        if record_id not in local_files:
            missing_records.append({
                'id': record_id,
                'files': len(server_urls),
                'types': [item['type'] for item in server_urls]
            })
        else:
            # 파일 타입별 비교
            server_types = [item['type'] for item in server_urls]
            local_types = [item['type'] for item in local_files[record_id]]
            
            # 서버에는 있지만 로컬에 없는 타입
            for s_type in server_types:
                if s_type not in local_types and s_type != 'UNKNOWN':
                    missing_files.append({
                        'id': record_id,
                        'missing_type': s_type,
                        'server_types': server_types,
                        'local_types': local_types
                    })
    
    # 로컬 파일 수 계산
    for record_id, files in local_files.items():
        total_local_files += len(files)
    
    # 4. 결과 출력
    print(f"\n4. 분석 결과:")
    print(f"  - 서버 총 첨부파일: {total_server_files}개")
    print(f"  - 로컬 총 파일: {total_local_files}개")
    print(f"  - 완전 누락 레코드: {len(missing_records)}개")
    print(f"  - 부분 누락 파일: {len(missing_files)}개")
    
    # 상세 문제 리스트 (처음 10개만)
    if missing_records:
        print(f"\n  [완전 누락된 레코드] (처음 10개)")
        for item in missing_records[:10]:
            print(f"    - {item['id']}: {item['files']}개 파일 ({', '.join(item['types'])})")
    
    if missing_files:
        print(f"\n  [부분 누락된 파일] (처음 10개)")
        for item in missing_files[:10]:
            print(f"    - {item['id']}: {item['missing_type']} 누락")
            print(f"      서버: {item['server_types']}")
            print(f"      로컬: {item['local_types']}")
    
    # 결과 저장
    return {
        'source': source_name,
        'total_server_files': total_server_files,
        'total_local_files': total_local_files,
        'missing_records': missing_records,
        'missing_files': missing_files,
        'server_records': len(server_data),
        'local_records': len(local_files)
    }

# 메인 실행
if __name__ == "__main__":
    print("서버-로컬 첨부파일 비교 분석 시작...")
    
    results = []
    
    # 1. K-Startup 분석
    ks_result = analyze_attachments(
        source_name="K-Startup",
        table_name="kstartup_complete",
        id_field="ann_no",
        download_dir="E:/gov-support-automation/downloads/kstartup/"
    )
    if ks_result:
        results.append(ks_result)
    
    # 2. 기업마당 분석
    biz_result = analyze_attachments(
        source_name="기업마당",
        table_name="bizinfo_complete",
        id_field="pblanc_no",
        download_dir="E:/gov-support-automation/downloads/bizinfo/"
    )
    if biz_result:
        results.append(biz_result)
    
    # 최종 요약
    print(f"\n{'='*80}")
    print("최종 요약")
    print('='*80)
    
    total_missing_records = 0
    total_missing_files = 0
    
    for result in results:
        print(f"\n{result['source']}:")
        print(f"  - 서버 레코드/파일: {result['server_records']}개 / {result['total_server_files']}개")
        print(f"  - 로컬 레코드/파일: {result['local_records']}개 / {result['total_local_files']}개")
        print(f"  - 완전 누락: {len(result['missing_records'])}개 레코드")
        print(f"  - 부분 누락: {len(result['missing_files'])}개 파일")
        
        total_missing_records += len(result['missing_records'])
        total_missing_files += len(result['missing_files'])
    
    print(f"\n전체 문제:")
    print(f"  - 총 완전 누락 레코드: {total_missing_records}개")
    print(f"  - 총 부분 누락 파일: {total_missing_files}개")
    
    # 결과 JSON 저장
    with open('E:/gov-support-automation/downloads/attachment_comparison_report.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n상세 보고서 저장됨: attachment_comparison_report.json")