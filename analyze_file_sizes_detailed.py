#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
로컬 PDF 파일 용량 분석
2025-09-10 09:30 실행
- 다운로드한 원본 파일
- HWP 변환 파일
- 평균 및 이상치 분석
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from pathlib import Path
import statistics
import json
from datetime import datetime

def analyze_pdf_sizes():
    """PDF 파일 용량 상세 분석"""
    
    print("="*70)
    print("📊 PDF 파일 용량 분석")
    print(f"🕐 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 분석할 폴더들
    folders = {
        'downloads': Path(r'E:\gov-support-automation\downloads'),
        'converted': Path(r'E:\gov-support-automation\converted'),
        'kstartup': Path(r'E:\gov-support-automation\downloads\kstartup'),
        'bizinfo': Path(r'E:\gov-support-automation\downloads\bizinfo')
    }
    
    all_files = []
    stats_by_folder = {}
    
    # 각 폴더별 파일 수집
    for folder_name, folder_path in folders.items():
        if not folder_path.exists():
            print(f"⚠️ {folder_name} 폴더 없음: {folder_path}")
            continue
            
        folder_files = []
        
        # PDF 파일 찾기 (재귀적)
        for pdf_file in folder_path.rglob('*.pdf'):
            size = pdf_file.stat().st_size
            folder_files.append({
                'path': str(pdf_file),
                'name': pdf_file.name,
                'size': size,
                'size_mb': round(size / (1024*1024), 2),
                'folder': folder_name
            })
        
        # HWP 변환 파일도 체크
        for hwp_file in folder_path.rglob('*.hwp'):
            size = hwp_file.stat().st_size
            folder_files.append({
                'path': str(hwp_file),
                'name': hwp_file.name,
                'size': size,
                'size_mb': round(size / (1024*1024), 2),
                'folder': folder_name,
                'type': 'hwp'
            })
            
        # HWPX 파일
        for hwpx_file in folder_path.rglob('*.hwpx'):
            size = hwpx_file.stat().st_size
            folder_files.append({
                'path': str(hwpx_file),
                'name': hwpx_file.name,
                'size': size,
                'size_mb': round(size / (1024*1024), 2),
                'folder': folder_name,
                'type': 'hwpx'
            })
        
        all_files.extend(folder_files)
        stats_by_folder[folder_name] = folder_files
        
        print(f"\n📁 {folder_name}: {len(folder_files)}개 파일")
    
    if not all_files:
        print("\n❌ 분석할 파일이 없습니다.")
        return
    
    # 전체 통계
    sizes_mb = [f['size_mb'] for f in all_files]
    
    print("\n" + "="*70)
    print("📊 전체 통계")
    print("="*70)
    print(f"총 파일 수: {len(all_files)}개")
    print(f"총 용량: {sum(sizes_mb):.2f} MB ({sum(sizes_mb)/1024:.2f} GB)")
    print(f"평균 용량: {statistics.mean(sizes_mb):.2f} MB")
    print(f"중앙값: {statistics.median(sizes_mb):.2f} MB")
    
    if len(sizes_mb) > 1:
        print(f"표준편차: {statistics.stdev(sizes_mb):.2f} MB")
    
    # 이상치 탐지 (IQR 방법)
    sorted_sizes = sorted(sizes_mb)
    q1 = sorted_sizes[len(sorted_sizes)//4]
    q3 = sorted_sizes[3*len(sorted_sizes)//4]
    iqr = q3 - q1
    
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    print(f"\n📈 사분위수:")
    print(f"Q1 (25%): {q1:.2f} MB")
    print(f"Q3 (75%): {q3:.2f} MB")
    print(f"IQR: {iqr:.2f} MB")
    print(f"정상 범위: {max(0, lower_bound):.2f} ~ {upper_bound:.2f} MB")
    
    # 이상치 찾기
    outliers = [f for f in all_files if f['size_mb'] < lower_bound or f['size_mb'] > upper_bound]
    normal_files = [f for f in all_files if lower_bound <= f['size_mb'] <= upper_bound]
    
    print(f"\n🎯 이상치 분석:")
    print(f"이상치 파일: {len(outliers)}개")
    print(f"정상 파일: {len(normal_files)}개")
    
    if outliers:
        print("\n📌 특이한 파일들 (이상치):")
        # 가장 큰 파일 5개
        largest = sorted(outliers, key=lambda x: x['size_mb'], reverse=True)[:5]
        for f in largest:
            print(f"  • {f['name'][:50]}: {f['size_mb']} MB")
        
        # 가장 작은 파일 5개
        if len(outliers) > 5:
            smallest = sorted(outliers, key=lambda x: x['size_mb'])[:5]
            print("\n  가장 작은 파일들:")
            for f in smallest:
                print(f"  • {f['name'][:50]}: {f['size_mb']} MB")
    
    # 정상 파일만의 평균
    if normal_files:
        normal_sizes = [f['size_mb'] for f in normal_files]
        print(f"\n✅ 이상치 제외 통계:")
        print(f"정상 파일 평균: {statistics.mean(normal_sizes):.2f} MB")
        print(f"정상 파일 중앙값: {statistics.median(normal_sizes):.2f} MB")
        print(f"정상 파일 총 용량: {sum(normal_sizes):.2f} MB")
    
    # 파일 타입별 통계
    pdf_files = [f for f in all_files if not f.get('type')]
    hwp_files = [f for f in all_files if f.get('type') == 'hwp']
    hwpx_files = [f for f in all_files if f.get('type') == 'hwpx']
    
    print(f"\n📄 파일 타입별:")
    if pdf_files:
        pdf_sizes = [f['size_mb'] for f in pdf_files]
        print(f"PDF: {len(pdf_files)}개, 평균 {statistics.mean(pdf_sizes):.2f} MB")
    if hwp_files:
        hwp_sizes = [f['size_mb'] for f in hwp_files]
        print(f"HWP: {len(hwp_files)}개, 평균 {statistics.mean(hwp_sizes):.2f} MB")
    if hwpx_files:
        hwpx_sizes = [f['size_mb'] for f in hwpx_files]
        print(f"HWPX: {len(hwpx_files)}개, 평균 {statistics.mean(hwpx_sizes):.2f} MB")
    
    # 크기 분포
    print(f"\n📊 크기 분포:")
    ranges = [
        (0, 0.5, "0~500KB"),
        (0.5, 1, "500KB~1MB"),
        (1, 2, "1~2MB"),
        (2, 5, "2~5MB"),
        (5, 10, "5~10MB"),
        (10, 20, "10~20MB"),
        (20, float('inf'), "20MB 이상")
    ]
    
    for min_size, max_size, label in ranges:
        count = len([f for f in all_files if min_size <= f['size_mb'] < max_size])
        if count > 0:
            percentage = (count / len(all_files)) * 100
            print(f"{label:15} : {count:4}개 ({percentage:5.1f}%) {'█' * int(percentage/2)}")
    
    # 결과 저장
    result = {
        'timestamp': datetime.now().isoformat(),
        'total_files': len(all_files),
        'total_size_mb': sum(sizes_mb),
        'average_size_mb': statistics.mean(sizes_mb),
        'median_size_mb': statistics.median(sizes_mb),
        'normal_average_mb': statistics.mean(normal_sizes) if normal_files else 0,
        'outliers_count': len(outliers),
        'normal_range': {
            'min': max(0, lower_bound),
            'max': upper_bound
        }
    }
    
    with open('file_size_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*70)
    print("💾 분석 결과가 file_size_analysis.json에 저장되었습니다.")
    print("="*70)

if __name__ == "__main__":
    analyze_pdf_sizes()