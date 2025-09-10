#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5MB 이상 대용량 파일 상세 분석
2025-09-10 10:30 실행
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from pathlib import Path
from datetime import datetime

def analyze_large_files():
    """5MB 이상 파일 상세 분석"""
    
    print("="*70)
    print("📊 5MB 이상 대용량 파일 분석")
    print(f"🕐 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 분석할 폴더들
    folders = {
        'downloads': Path(r'E:\gov-support-automation\downloads'),
        'converted': Path(r'E:\gov-support-automation\converted'),
        'kstartup': Path(r'E:\gov-support-automation\downloads\kstartup'),
        'bizinfo': Path(r'E:\gov-support-automation\downloads\bizinfo')
    }
    
    large_files = []
    size_5mb = 5 * 1024 * 1024  # 5MB in bytes
    
    # 각 폴더에서 대용량 파일 찾기
    for folder_name, folder_path in folders.items():
        if not folder_path.exists():
            continue
            
        # 모든 파일 확인 (PDF, HWP, HWPX 등)
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    if size >= size_5mb:
                        large_files.append({
                            'path': str(file_path),
                            'name': file_path.name,
                            'size': size,
                            'size_mb': round(size / (1024*1024), 2),
                            'folder': folder_name,
                            'extension': file_path.suffix.lower()
                        })
                except:
                    continue
    
    # 크기순 정렬
    large_files.sort(key=lambda x: x['size'], reverse=True)
    
    # 통계
    print(f"\n📈 5MB 이상 파일 총 {len(large_files)}개 발견")
    print("="*70)
    
    if large_files:
        total_size = sum(f['size_mb'] for f in large_files)
        print(f"총 용량: {total_size:.2f} MB ({total_size/1024:.2f} GB)")
        print(f"평균 크기: {total_size/len(large_files):.2f} MB")
        
        # 크기별 분포
        ranges = [
            (5, 10, "5-10MB"),
            (10, 20, "10-20MB"),
            (20, 30, "20-30MB"),
            (30, 40, "30-40MB"),
            (40, float('inf'), "40MB 이상")
        ]
        
        print("\n📊 크기 분포:")
        print("-"*50)
        for min_size, max_size, label in ranges:
            count = len([f for f in large_files if min_size <= f['size_mb'] < max_size])
            if count > 0:
                size_sum = sum(f['size_mb'] for f in large_files if min_size <= f['size_mb'] < max_size)
                print(f"{label:12} : {count:3}개 파일, 총 {size_sum:8.2f} MB")
        
        # 확장자별 통계
        print("\n📄 파일 타입별:")
        print("-"*50)
        extensions = {}
        for f in large_files:
            ext = f['extension'] or 'no_ext'
            if ext not in extensions:
                extensions[ext] = {'count': 0, 'size': 0}
            extensions[ext]['count'] += 1
            extensions[ext]['size'] += f['size_mb']
        
        for ext, data in sorted(extensions.items(), key=lambda x: x[1]['size'], reverse=True):
            print(f"{ext:8} : {data['count']:3}개, 총 {data['size']:8.2f} MB")
        
        # 상위 20개 파일 목록
        print("\n🔝 가장 큰 파일 Top 20:")
        print("-"*70)
        print(f"{'크기(MB)':>10} | {'파일명':50}")
        print("-"*70)
        
        for i, f in enumerate(large_files[:20], 1):
            name = f['name'][:50] + '...' if len(f['name']) > 50 else f['name']
            print(f"{f['size_mb']:10.2f} | {name}")
        
        # 중복 파일 체크
        print("\n🔍 동일 크기 파일 (중복 가능성):")
        print("-"*70)
        size_groups = {}
        for f in large_files:
            size = f['size']
            if size not in size_groups:
                size_groups[size] = []
            size_groups[size].append(f['name'])
        
        duplicates_found = False
        for size, names in size_groups.items():
            if len(names) > 1:
                duplicates_found = True
                size_mb = round(size / (1024*1024), 2)
                print(f"\n{size_mb} MB ({len(names)}개):")
                for name in names[:5]:  # 최대 5개만 표시
                    print(f"  - {name[:60]}")
                if len(names) > 5:
                    print(f"  ... 외 {len(names)-5}개")
        
        if not duplicates_found:
            print("중복 파일 없음")
    
    print("\n" + "="*70)
    print(f"📌 총 {len(large_files)}개 대용량 파일 (5MB 이상)")
    print("="*70)

if __name__ == "__main__":
    analyze_large_files()