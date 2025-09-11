import os
import json
import re
from collections import defaultdict
from supabase import create_client
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv('E:/gov-support-automation/config/.env')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Supabase 클라이언트 생성
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_urls_from_attachment(attachment_urls):
    """attachment_urls에서 실제 URL과 타입 추출"""
    urls = []
    if isinstance(attachment_urls, list):
        for item in attachment_urls:
            if isinstance(item, dict):
                url = item.get('url', '')
                file_type = item.get('type', item.get('file_extension', ''))
                filename = item.get('display_filename', item.get('text', ''))
                urls.append({
                    'url': url,
                    'type': file_type.upper() if file_type else 'UNKNOWN',
                    'filename': filename
                })
            else:
                urls.append({
                    'url': str(item),
                    'type': 'UNKNOWN',
                    'filename': str(item).split('/')[-1] if '/' in str(item) else str(item)
                })
    return urls

def analyze_kstartup():
    """K-Startup 첨부파일 분석"""
    print("\n" + "="*80)
    print("K-Startup 첨부파일 분석")
    print("="*80)
    
    # 서버 데이터 가져오기
    print("\n1. 서버 데이터 조회 중...")
    server_data = {}
    
    try:
        result = supabase.table('kstartup_complete').select('announcement_id, attachment_urls').not_.is_('attachment_urls', 'null').execute()
        
        for row in result.data:
            ann_id = row.get('announcement_id')
            if ann_id:
                urls = extract_urls_from_attachment(row.get('attachment_urls', []))
                if urls:
                    server_data[ann_id] = urls
        
        print(f"  - 서버에 첨부파일이 있는 레코드: {len(server_data)}개")
        
    except Exception as e:
        print(f"  - 서버 조회 오류: {e}")
        return None
    
    # 로컬 파일 스캔
    print("\n2. 로컬 파일 스캔 중...")
    local_files = defaultdict(list)
    download_dir = "E:/gov-support-automation/downloads/kstartup/"
    
    if os.path.exists(download_dir):
        for filename in os.listdir(download_dir):
            if os.path.isfile(os.path.join(download_dir, filename)):
                # KS_숫자 형태 추출
                match = re.search(r'KS_(\d+)', filename)
                if match:
                    ann_id = f"KS_{match.group(1)}"
                    
                    # 파일 타입 확인
                    file_type = 'OTHER'
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
                    
                    local_files[ann_id].append({
                        'filename': filename,
                        'type': file_type
                    })
    
    print(f"  - 로컬에 파일이 있는 레코드: {len(local_files)}개")
    
    # 비교 분석
    print("\n3. 비교 분석...")
    
    total_server_files = sum(len(urls) for urls in server_data.values())
    total_local_files = sum(len(files) for files in local_files.values())
    missing_completely = []  # 완전히 누락
    missing_partially = []   # 부분 누락
    
    for ann_id, server_urls in server_data.items():
        if ann_id not in local_files:
            missing_completely.append({
                'id': ann_id,
                'files': len(server_urls),
                'types': [u['type'] for u in server_urls]
            })
        else:
            # 타입별 비교
            server_types = [u['type'] for u in server_urls]
            local_types = [f['type'] for f in local_files[ann_id]]
            
            for s_type in server_types:
                if s_type != 'UNKNOWN' and s_type not in local_types:
                    missing_partially.append({
                        'id': ann_id,
                        'missing_type': s_type,
                        'server_count': len(server_urls),
                        'local_count': len(local_files[ann_id])
                    })
                    break
    
    print(f"\n결과:")
    print(f"  - 서버 총 파일: {total_server_files}개")
    print(f"  - 로컬 총 파일: {total_local_files}개")
    print(f"  - 완전 누락: {len(missing_completely)}개 레코드")
    print(f"  - 부분 누락: {len(missing_partially)}개 레코드")
    
    if missing_completely[:5]:
        print(f"\n  [완전 누락 예시] (처음 5개)")
        for item in missing_completely[:5]:
            print(f"    {item['id']}: {item['files']}개 ({', '.join(item['types'])})")
    
    if missing_partially[:5]:
        print(f"\n  [부분 누락 예시] (처음 5개)")
        for item in missing_partially[:5]:
            print(f"    {item['id']}: {item['missing_type']} 누락 (서버 {item['server_count']}개/로컬 {item['local_count']}개)")
    
    return {
        'source': 'K-Startup',
        'server_records': len(server_data),
        'local_records': len(local_files),
        'server_files': total_server_files,
        'local_files': total_local_files,
        'missing_completely': missing_completely,
        'missing_partially': missing_partially
    }

def analyze_bizinfo():
    """기업마당 첨부파일 분석 (ID 기반)"""
    print("\n" + "="*80)
    print("기업마당 첨부파일 분석")
    print("="*80)
    
    # 서버 데이터 가져오기 (ID 기반)
    print("\n1. 서버 데이터 조회 중...")
    server_data = {}
    id_to_pblanc = {}  # ID -> PBLN 매핑
    
    try:
        result = supabase.table('bizinfo_complete').select('id, pblanc_no, attachment_urls').not_.is_('attachment_urls', 'null').execute()
        
        for row in result.data:
            record_id = str(row.get('id'))
            pblanc_no = row.get('pblanc_no')
            urls = extract_urls_from_attachment(row.get('attachment_urls', []))
            
            if urls:
                server_data[record_id] = {
                    'pblanc_no': pblanc_no,
                    'urls': urls
                }
                
                # PBLN 번호가 URL에 있는지 확인
                for url_info in urls:
                    url = url_info.get('url', '')
                    match = re.search(r'PBLN_\d+', url)
                    if match:
                        id_to_pblanc[record_id] = match.group()
                        break
        
        print(f"  - 서버에 첨부파일이 있는 레코드: {len(server_data)}개")
        
    except Exception as e:
        print(f"  - 서버 조회 오류: {e}")
        return None
    
    # 로컬 파일 스캔
    print("\n2. 로컬 파일 스캔 중...")
    local_files = defaultdict(list)
    pbln_to_files = defaultdict(list)  # PBLN -> 파일 매핑
    download_dir = "E:/gov-support-automation/downloads/bizinfo/"
    
    if os.path.exists(download_dir):
        for filename in os.listdir(download_dir):
            if os.path.isfile(os.path.join(download_dir, filename)):
                # PBLN_숫자 형태 추출
                match = re.search(r'PBLN_\d+', filename)
                if match:
                    pbln_no = match.group()
                    
                    # 파일 타입 확인
                    file_type = 'OTHER'
                    if '.pdf' in filename.lower():
                        file_type = 'PDF'
                    elif '.zip' in filename.lower():
                        file_type = 'ZIP'
                    elif '.hwp' in filename.lower():
                        file_type = 'HWP'
                    
                    pbln_to_files[pbln_no].append({
                        'filename': filename,
                        'type': file_type
                    })
    
    # ID와 PBLN 매칭
    for record_id, pbln_no in id_to_pblanc.items():
        if pbln_no in pbln_to_files:
            local_files[record_id] = pbln_to_files[pbln_no]
    
    print(f"  - 로컬에 파일이 있는 레코드: {len(local_files)}개")
    print(f"  - 로컬 PBLN별 파일: {len(pbln_to_files)}개")
    
    # 비교 분석
    print("\n3. 비교 분석...")
    
    total_server_files = sum(len(d['urls']) for d in server_data.values())
    total_local_files = sum(len(files) for files in local_files.values())
    missing_completely = []
    missing_partially = []
    
    for record_id, data in server_data.items():
        pbln_no = id_to_pblanc.get(record_id, data['pblanc_no'])
        
        if record_id not in local_files:
            # PBLN으로도 찾아보기
            if pbln_no and pbln_no in pbln_to_files:
                local_files[record_id] = pbln_to_files[pbln_no]
            else:
                missing_completely.append({
                    'id': record_id,
                    'pbln': pbln_no,
                    'files': len(data['urls']),
                    'types': [u['type'] for u in data['urls']]
                })
        else:
            # 타입별 비교
            server_types = [u['type'] for u in data['urls']]
            local_types = [f['type'] for f in local_files[record_id]]
            
            for s_type in server_types:
                if s_type != 'UNKNOWN' and s_type not in local_types:
                    missing_partially.append({
                        'id': record_id,
                        'pbln': pbln_no,
                        'missing_type': s_type,
                        'server_count': len(data['urls']),
                        'local_count': len(local_files[record_id])
                    })
                    break
    
    print(f"\n결과:")
    print(f"  - 서버 총 파일: {total_server_files}개")
    print(f"  - 로컬 총 파일: {total_local_files}개")
    print(f"  - 완전 누락: {len(missing_completely)}개 레코드")
    print(f"  - 부분 누락: {len(missing_partially)}개 레코드")
    
    # 예시 출력
    if missing_completely[:5]:
        print(f"\n  [완전 누락 예시] (처음 5개)")
        for item in missing_completely[:5]:
            print(f"    ID {item['id']} (PBLN: {item['pbln']}): {item['files']}개 ({', '.join(item['types'])})")
    
    if missing_partially[:5]:
        print(f"\n  [부분 누락 예시] (처음 5개)")
        for item in missing_partially[:5]:
            print(f"    ID {item['id']} (PBLN: {item['pbln']}): {item['missing_type']} 누락")
    
    # PBLN_000000000114380 특별 확인
    print(f"\n  [PBLN_000000000114380 확인]")
    for record_id, data in server_data.items():
        if '114380' in str(data.get('pblanc_no', '')) or '114380' in str(id_to_pblanc.get(record_id, '')):
            print(f"    ID {record_id}: 서버에 {len(data['urls'])}개 파일")
            for url_info in data['urls']:
                print(f"      - {url_info['type']}: {url_info['filename'][:50]}")
            
            if record_id in local_files:
                print(f"    로컬: {len(local_files[record_id])}개 파일")
                for f in local_files[record_id]:
                    print(f"      - {f['type']}: {f['filename'][:50]}")
            else:
                print(f"    로컬: 파일 없음 (누락)")
    
    return {
        'source': '기업마당',
        'server_records': len(server_data),
        'local_records': len(local_files),
        'server_files': total_server_files,
        'local_files': total_local_files,
        'missing_completely': missing_completely,
        'missing_partially': missing_partially
    }

# 메인 실행
if __name__ == "__main__":
    print("정확한 서버-로컬 첨부파일 비교 분석 시작...")
    
    results = []
    
    # K-Startup 분석
    ks_result = analyze_kstartup()
    if ks_result:
        results.append(ks_result)
    
    # 기업마당 분석
    biz_result = analyze_bizinfo()
    if biz_result:
        results.append(biz_result)
    
    # 최종 요약
    print("\n" + "="*80)
    print("최종 요약")
    print("="*80)
    
    for result in results:
        print(f"\n{result['source']}:")
        print(f"  서버: {result['server_records']}개 레코드, {result['server_files']}개 파일")
        print(f"  로컬: {result['local_records']}개 레코드, {result['local_files']}개 파일")
        print(f"  문제: 완전 누락 {len(result['missing_completely'])}개, 부분 누락 {len(result['missing_partially'])}개")
    
    # JSON 저장
    report_data = []
    for result in results:
        report_data.append({
            'source': result['source'],
            'statistics': {
                'server_records': result['server_records'],
                'server_files': result['server_files'],
                'local_records': result['local_records'],
                'local_files': result['local_files'],
                'missing_completely_count': len(result['missing_completely']),
                'missing_partially_count': len(result['missing_partially'])
            },
            'missing_completely': result['missing_completely'][:20],  # 처음 20개만
            'missing_partially': result['missing_partially'][:20]     # 처음 20개만
        })
    
    with open('E:/gov-support-automation/downloads/accurate_comparison_report.json', 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n상세 보고서 저장: accurate_comparison_report.json")