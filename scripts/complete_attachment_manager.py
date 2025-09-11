#!/usr/bin/env python3
"""
첨부파일 관리자 - 100% 다운로드 성공을 위한 완벽한 관리 스크립트
K-Startup과 BizInfo 첨부파일 다운로드, 검증, 관리 통합
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple
from dotenv import load_dotenv
from supabase import create_client

# 환경변수 로드
load_dotenv()

class CompleteAttachmentManager:
    def __init__(self):
        self.project_root = Path("E:\\gov-support-automation")
        self.downloads_dir = self.project_root / "downloads"
        self.kstartup_dir = self.downloads_dir / "kstartup"
        self.bizinfo_dir = self.downloads_dir / "bizinfo"
        
        # Supabase 연결
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        self.supabase = create_client(url, key) if url and key else None
        
        # 관리 데이터
        self.inventory = {
            'kstartup': {},
            'bizinfo': {},
            'metadata': {
                'last_scan': None,
                'total_files': 0,
                'total_size_mb': 0
            }
        }
    
    def scan_local_files(self) -> Dict:
        """로컬 파일 전체 스캔"""
        print("\n[SCAN] 로컬 파일 스캔 시작...")
        
        # K-Startup 스캔
        kstartup_files = self.scan_directory(self.kstartup_dir, 'kstartup')
        print(f"  K-Startup: {len(kstartup_files)} 파일")
        
        # BizInfo 스캔
        bizinfo_files = self.scan_directory(self.bizinfo_dir, 'bizinfo')
        print(f"  BizInfo: {len(bizinfo_files)} 파일")
        
        # 메타데이터 업데이트
        self.inventory['metadata']['last_scan'] = datetime.now().isoformat()
        self.inventory['metadata']['total_files'] = len(kstartup_files) + len(bizinfo_files)
        
        return self.inventory
    
    def scan_directory(self, directory: Path, source: str) -> Dict:
        """디렉토리 스캔"""
        files = {}
        total_size = 0
        
        if not directory.exists():
            return files
        
        for file_path in directory.glob("*"):
            if file_path.is_file():
                file_info = {
                    'name': file_path.name,
                    'size': file_path.stat().st_size,
                    'size_mb': round(file_path.stat().st_size / (1024*1024), 2),
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    'hash': self.get_file_hash(file_path),
                    'path': str(file_path)
                }
                
                # ID 추출
                record_id = self.extract_id(file_path.name, source)
                if record_id:
                    if record_id not in files:
                        files[record_id] = []
                    files[record_id].append(file_info)
                    total_size += file_info['size']
        
        self.inventory[source] = files
        self.inventory['metadata'][f'{source}_size_mb'] = round(total_size / (1024*1024), 2)
        
        return files
    
    def extract_id(self, filename: str, source: str) -> str:
        """파일명에서 ID 추출"""
        if source == 'kstartup':
            if 'KS_' in filename:
                parts = filename.split('_')
                if len(parts) >= 2:
                    return f"KS_{parts[1]}"
        elif source == 'bizinfo':
            if 'ID_' in filename:
                parts = filename.split('_')
                if len(parts) >= 2:
                    return parts[1]
            elif 'PBLN_' in filename:
                parts = filename.split('_')
                if len(parts) >= 2:
                    return f"PBLN_{parts[1]}"
        return None
    
    def get_file_hash(self, file_path: Path) -> str:
        """파일 해시 계산"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def verify_completeness(self) -> Dict:
        """다운로드 완전성 검증"""
        print("\n[VERIFY] 다운로드 완전성 검증...")
        
        verification = {
            'kstartup': {
                'server_records': 0,
                'local_records': 0,
                'match_rate': 0,
                'missing': []
            },
            'bizinfo': {
                'server_records': 0,
                'local_records': 0,
                'match_rate': 0,
                'missing': []
            }
        }
        
        if not self.supabase:
            print("[ERROR] Supabase 연결 없음")
            return verification
        
        # K-Startup 검증
        try:
            result = self.supabase.table('kstartup_complete')\
                .select('id')\
                .not_.is_('attachment_urls', 'null')\
                .execute()
            
            server_ids = {f"KS_{r['id']}" for r in result.data}
            local_ids = set(self.inventory['kstartup'].keys())
            
            verification['kstartup']['server_records'] = len(server_ids)
            verification['kstartup']['local_records'] = len(local_ids)
            verification['kstartup']['match_rate'] = round(
                len(local_ids) / len(server_ids) * 100 if server_ids else 100, 1
            )
            verification['kstartup']['missing'] = list(server_ids - local_ids)[:10]
            
        except Exception as e:
            print(f"  [ERROR] K-Startup 검증 실패: {e}")
        
        # BizInfo 검증
        try:
            result = self.supabase.table('bizinfo_complete')\
                .select('id')\
                .not_.is_('attachment_urls', 'null')\
                .execute()
            
            server_ids = {str(r['id']) for r in result.data}
            local_ids = set(self.inventory['bizinfo'].keys())
            
            verification['bizinfo']['server_records'] = len(server_ids)
            verification['bizinfo']['local_records'] = len(local_ids)
            verification['bizinfo']['match_rate'] = round(
                len(local_ids) / len(server_ids) * 100 if server_ids else 100, 1
            )
            verification['bizinfo']['missing'] = list(server_ids - local_ids)[:10]
            
        except Exception as e:
            print(f"  [ERROR] BizInfo 검증 실패: {e}")
        
        # 결과 출력
        print(f"\n[K-Startup 검증 결과]")
        print(f"  서버 레코드: {verification['kstartup']['server_records']}")
        print(f"  로컬 레코드: {verification['kstartup']['local_records']}")
        print(f"  매칭률: {verification['kstartup']['match_rate']}%")
        
        print(f"\n[BizInfo 검증 결과]")
        print(f"  서버 레코드: {verification['bizinfo']['server_records']}")
        print(f"  로컬 레코드: {verification['bizinfo']['local_records']}")
        print(f"  매칭률: {verification['bizinfo']['match_rate']}%")
        
        return verification
    
    def find_duplicates(self) -> Dict:
        """중복 파일 찾기"""
        print("\n[DUPLICATE] 중복 파일 검색...")
        
        duplicates = {
            'kstartup': {},
            'bizinfo': {}
        }
        
        # 해시별 파일 그룹화
        for source in ['kstartup', 'bizinfo']:
            hash_map = {}
            for record_id, files in self.inventory[source].items():
                for file_info in files:
                    file_hash = file_info['hash']
                    if file_hash not in hash_map:
                        hash_map[file_hash] = []
                    hash_map[file_hash].append({
                        'id': record_id,
                        'name': file_info['name'],
                        'size': file_info['size_mb']
                    })
            
            # 중복 찾기
            for file_hash, files in hash_map.items():
                if len(files) > 1:
                    duplicates[source][file_hash] = files
        
        # 결과 출력
        ks_dup_count = len(duplicates['kstartup'])
        biz_dup_count = len(duplicates['bizinfo'])
        
        print(f"  K-Startup 중복: {ks_dup_count}개 그룹")
        print(f"  BizInfo 중복: {biz_dup_count}개 그룹")
        
        return duplicates
    
    def generate_statistics(self) -> Dict:
        """통계 생성"""
        print("\n[STATS] 통계 생성...")
        
        stats = {
            'summary': {
                'total_files': self.inventory['metadata']['total_files'],
                'total_size_mb': round(
                    self.inventory['metadata'].get('kstartup_size_mb', 0) +
                    self.inventory['metadata'].get('bizinfo_size_mb', 0), 2
                ),
                'last_scan': self.inventory['metadata']['last_scan']
            },
            'kstartup': {
                'total_files': sum(len(files) for files in self.inventory['kstartup'].values()),
                'unique_records': len(self.inventory['kstartup']),
                'total_size_mb': self.inventory['metadata'].get('kstartup_size_mb', 0),
                'avg_files_per_record': 0
            },
            'bizinfo': {
                'total_files': sum(len(files) for files in self.inventory['bizinfo'].values()),
                'unique_records': len(self.inventory['bizinfo']),
                'total_size_mb': self.inventory['metadata'].get('bizinfo_size_mb', 0),
                'avg_files_per_record': 0
            },
            'file_types': self.analyze_file_types()
        }
        
        # 평균 파일 수 계산
        if stats['kstartup']['unique_records'] > 0:
            stats['kstartup']['avg_files_per_record'] = round(
                stats['kstartup']['total_files'] / stats['kstartup']['unique_records'], 2
            )
        
        if stats['bizinfo']['unique_records'] > 0:
            stats['bizinfo']['avg_files_per_record'] = round(
                stats['bizinfo']['total_files'] / stats['bizinfo']['unique_records'], 2
            )
        
        return stats
    
    def analyze_file_types(self) -> Dict:
        """파일 타입 분석"""
        file_types = {}
        
        for source in ['kstartup', 'bizinfo']:
            for record_id, files in self.inventory[source].items():
                for file_info in files:
                    ext = Path(file_info['name']).suffix.lower()
                    if ext:
                        if ext not in file_types:
                            file_types[ext] = {'count': 0, 'size_mb': 0}
                        file_types[ext]['count'] += 1
                        file_types[ext]['size_mb'] += file_info['size_mb']
        
        # 정렬
        sorted_types = dict(sorted(file_types.items(), 
                                 key=lambda x: x[1]['count'], 
                                 reverse=True))
        
        return sorted_types
    
    def save_inventory(self):
        """인벤토리 저장"""
        inventory_file = self.project_root / "attachment_inventory.json"
        
        # 저장할 데이터 준비 (경로 정보는 제외)
        save_data = {
            'metadata': self.inventory['metadata'],
            'statistics': self.generate_statistics(),
            'verification': self.verify_completeness(),
            'file_count': {
                'kstartup': len(self.inventory['kstartup']),
                'bizinfo': len(self.inventory['bizinfo'])
            }
        }
        
        with open(inventory_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[SAVE] 인벤토리 저장: {inventory_file}")
        
        return save_data
    
    def generate_report(self):
        """최종 보고서 생성"""
        print("\n" + "="*80)
        print("첨부파일 관리 보고서")
        print("="*80)
        
        # 스캔 실행
        self.scan_local_files()
        
        # 통계 생성
        stats = self.generate_statistics()
        
        print(f"\n[전체 현황]")
        print(f"  총 파일 수: {stats['summary']['total_files']:,}개")
        print(f"  총 용량: {stats['summary']['total_size_mb']:,.2f} MB")
        
        print(f"\n[K-Startup]")
        print(f"  파일 수: {stats['kstartup']['total_files']:,}개")
        print(f"  고유 ID: {stats['kstartup']['unique_records']:,}개")
        print(f"  평균 파일/레코드: {stats['kstartup']['avg_files_per_record']}")
        print(f"  총 용량: {stats['kstartup']['total_size_mb']:,.2f} MB")
        
        print(f"\n[BizInfo]")
        print(f"  파일 수: {stats['bizinfo']['total_files']:,}개")
        print(f"  고유 ID: {stats['bizinfo']['unique_records']:,}개")
        print(f"  평균 파일/레코드: {stats['bizinfo']['avg_files_per_record']}")
        print(f"  총 용량: {stats['bizinfo']['total_size_mb']:,.2f} MB")
        
        print(f"\n[파일 타입 TOP 5]")
        for idx, (ext, info) in enumerate(list(stats['file_types'].items())[:5], 1):
            print(f"  {idx}. {ext}: {info['count']:,}개 ({info['size_mb']:.2f} MB)")
        
        # 검증 실행
        verification = self.verify_completeness()
        
        # 인벤토리 저장
        self.save_inventory()
        
        # 100% 성공 확인
        ks_rate = verification['kstartup']['match_rate']
        biz_rate = verification['bizinfo']['match_rate']
        
        if ks_rate >= 100 and biz_rate >= 100:
            print("\n" + "="*80)
            print("✅ 다운로드 100% 성공 확인!")
            print("="*80)
        else:
            print(f"\n⚠️ 추가 다운로드 필요")
            if ks_rate < 100:
                print(f"  K-Startup: {100-ks_rate:.1f}% 누락")
            if biz_rate < 100:
                print(f"  BizInfo: {100-biz_rate:.1f}% 누락")


def main():
    """메인 실행"""
    manager = CompleteAttachmentManager()
    manager.generate_report()


if __name__ == "__main__":
    main()