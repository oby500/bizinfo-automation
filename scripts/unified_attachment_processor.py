#!/usr/bin/env python3
"""
통합 첨부파일 처리기 (Unified Attachment Processor)
K-Startup과 BizInfo 모두 처리 가능한 단일 모듈

주요 기능:
- 상세 페이지 크롤링
- 첨부파일 정보 추출 (파일명, URL, 타입, 크기)
- HEAD 요청으로 실제 파일 정보 확인
- 파일 시그니처로 정확한 타입 판별
- 인코딩 문제 자동 처리
- 중복 처리 방지
"""

import os
import sys
import json
import time
import re
import requests
import logging
from datetime import datetime, timedelta
from urllib.parse import unquote, urlparse, urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import List, Dict, Optional, Tuple
from supabase import create_client
from dotenv import load_dotenv

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding='utf-8')

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_filename = f'unified_attachment_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 전역 진행 상황
lock = threading.Lock()
stats = {
    'total': 0,
    'processed': 0,
    'success': 0,
    'error': 0,
    'skip': 0,
    'attachments_found': 0,
    'attachments_updated': 0
}


class UnifiedAttachmentProcessor:
    """통합 첨부파일 처리 클래스"""
    
    def __init__(self, source_type: str = 'auto'):
        """
        초기화
        
        Args:
            source_type: 'kstartup', 'bizinfo', 또는 'auto' (자동 감지)
        """
        self.source_type = source_type
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Supabase 연결
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            raise ValueError("SUPABASE_URL과 SUPABASE_KEY 환경변수가 필요합니다")
        
        self.supabase = create_client(url, key)
        
    def get_file_signature(self, url: str, max_bytes: int = 1024) -> Optional[bytes]:
        """파일의 처음 부분을 다운로드하여 시그니처 확인"""
        try:
            # Range 헤더로 부분 다운로드
            headers = {'Range': f'bytes=0-{max_bytes}'}
            response = self.session.get(url, headers=headers, timeout=10, stream=True)
            
            if response.status_code in [200, 206]:
                return response.content[:max_bytes]
        except Exception as e:
            logger.debug(f"시그니처 확인 실패: {url} - {e}")
        
        return None
    
    def detect_file_type(self, content: bytes) -> str:
        """파일 시그니처로 타입 판별"""
        signatures = {
            # 문서 파일
            b'%PDF': 'PDF',
            b'\xd0\xcf\x11\xe0': 'DOC',  # MS Office
            b'PK\x03\x04': 'ZIP',  # ZIP 기반 (DOCX, XLSX, PPTX, ZIP 등)
            b'HWP Document': 'HWP',
            b'{\rtf': 'RTF',  # Rich Text Format
            
            # 이미지 파일
            b'\x89PNG': 'PNG',
            b'\xff\xd8\xff': 'JPG',
            b'GIF87a': 'GIF',
            b'GIF89a': 'GIF',
            b'BM': 'BMP',
            b'II\x2a\x00': 'TIFF',  # Little-endian
            b'MM\x00\x2a': 'TIFF',  # Big-endian
            b'RIFF': 'WEBP',  # WebP 이미지
            
            # 압축 파일
            b'Rar!': 'RAR',
            b'7z\xbc\xaf': '7Z',
            b'\x1f\x8b': 'GZ',  # GZIP
            b'BZh': 'BZ2',  # BZIP2
            b'\x50\x4b\x03\x04': 'ZIP',  # 일반 ZIP
            b'\x50\x4b\x05\x06': 'ZIP',  # 빈 ZIP
            b'\x50\x4b\x07\x08': 'ZIP',  # Spanned ZIP
            
            # 동영상 파일
            b'\x00\x00\x00\x14ftypM4V': 'MP4',
            b'\x00\x00\x00\x18ftypmp4': 'MP4',
            b'\x00\x00\x00\x20ftypM4V': 'M4V',
            b'\x1a\x45\xdf\xa3': 'MKV',  # Matroska
            b'RIFF': 'AVI',  # AVI (RIFF 기반)
            b'FLV': 'FLV',  # Flash Video
            
            # 오디오 파일
            b'ID3': 'MP3',
            b'\xff\xfb': 'MP3',  # MP3 without ID3
            b'OggS': 'OGG',
            b'fLaC': 'FLAC',
            b'FORM': 'AIFF',
            
            # 웹 파일
            b'<?xml': 'XML',
            b'<html': 'HTML',
            b'<!DOCTYPE': 'HTML',
            b'<HTML': 'HTML',
            b'<!doctype': 'HTML',
            
            # 실행 파일
            b'MZ': 'EXE',  # Windows executable
            b'\x7fELF': 'ELF',  # Linux executable
            b'\xca\xfe\xba\xbe': 'CLASS',  # Java class
            b'\xfe\xed\xfa': 'MACH-O',  # Mac executable
        }
        
        # 시그니처 체크
        for sig, file_type in signatures.items():
            if content.startswith(sig):
                # ZIP 기반 파일 세분화
                if file_type == 'ZIP':
                    # Office 2007+ 파일들
                    if b'word/' in content or b'docProps' in content:
                        return 'DOCX'
                    elif b'xl/' in content or b'worksheets' in content:
                        return 'XLSX'
                    elif b'ppt/' in content or b'slides' in content:
                        return 'PPTX'
                    # 한컴 오피스
                    elif b'mimetype' in content[:100]:
                        if b'hwp+zip' in content[:200]:
                            return 'HWPX'
                        elif b'hcell' in content[:200]:
                            return 'CELL'
                        elif b'hshow' in content[:200]:
                            return 'SHOW'
                    # JAR 파일
                    elif b'META-INF/' in content[:100]:
                        return 'JAR'
                    # APK 파일
                    elif b'AndroidManifest.xml' in content[:1000]:
                        return 'APK'
                    return 'ZIP'
                
                # RIFF 기반 파일 구분
                elif file_type == 'WEBP':
                    if content[8:12] == b'WEBP':
                        return 'WEBP'
                    elif content[8:12] == b'AVI ':
                        return 'AVI'
                    elif content[8:12] == b'WAVE':
                        return 'WAV'
                
                return file_type
        
        # HWP 추가 체크 (구버전)
        if b'HWP' in content[:1000] or b'Hwp' in content[:1000]:
            return 'HWP'
        
        # CSV 체크 (콤마로 구분된 텍스트)
        try:
            text = content[:500].decode('utf-8')
            if text.count(',') > 5 and '\n' in text:
                return 'CSV'
            # JSON 체크
            if text.strip().startswith(('{', '[')):
                import json
                try:
                    json.loads(text)
                    return 'JSON'
                except:
                    pass
            # 일반 텍스트
            return 'TXT'
        except:
            pass
        
        return 'UNKNOWN'
    
    def extract_filename_from_header(self, headers: dict) -> Optional[str]:
        """응답 헤더에서 파일명 추출"""
        disposition = headers.get('Content-Disposition', '')
        if not disposition:
            return None
        
        filename = None
        
        # filename*=UTF-8'' 형식 (RFC 5987)
        if "filename*=" in disposition:
            match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.IGNORECASE)
            if match:
                filename = unquote(match.group(1))
        
        # filename="..." 형식
        if not filename and 'filename=' in disposition:
            match = re.search(r'filename="?([^";\\n]+)"?', disposition, re.IGNORECASE)
            if match:
                filename = match.group(1)
                # 인코딩 처리
                try:
                    # UTF-8 확인
                    filename.encode('utf-8')
                except:
                    # Latin-1 → UTF-8 변환
                    try:
                        filename = filename.encode('latin-1').decode('utf-8')
                    except:
                        # EUC-KR → UTF-8 변환
                        try:
                            filename = filename.encode('latin-1').decode('euc-kr')
                        except:
                            pass
        
        return filename
    
    def get_file_info_from_url(self, url: str) -> Dict:
        """URL에서 파일 정보 추출 (Content-Type 우선)"""
        info = {
            'url': url,
            'name': None,
            'type': 'UNKNOWN',
            'size': None,
            'content_type': None,
            'error': None
        }
        
        try:
            # HEAD 요청으로 메타데이터 확인
            response = self.session.head(url, timeout=10, allow_redirects=True)
            
            # 1단계: Content-Type 헤더를 최우선으로 체크
            content_type = response.headers.get('Content-Type', '').lower()
            info['content_type'] = content_type  # 디버깅용 저장
            
            # 확장된 MIME 타입 매핑 (더 많은 변형 포함)
            mime_to_type = {
                # 문서 - 가장 일반적인 것들
                'application/pdf': 'PDF',
                'application/x-pdf': 'PDF',
                'application/x-hwp': 'HWP',
                'application/haansoft-hwp': 'HWP',
                'application/hwp': 'HWP',
                'application/x-hwpml': 'HWPX',
                'application/msword': 'DOC',
                'application/vnd.openxmlformats-officedocument.wordprocessingml': 'DOCX',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
                'application/vnd.ms-excel': 'XLS',
                'application/vnd.openxmlformats-officedocument.spreadsheetml': 'XLSX',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
                'application/vnd.ms-powerpoint': 'PPT',
                'application/vnd.openxmlformats-officedocument.presentationml': 'PPTX',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
                'text/plain': 'TXT',
                'text/csv': 'CSV',
                'application/csv': 'CSV',
                'application/xml': 'XML',
                'text/xml': 'XML',
                'application/json': 'JSON',
                'text/json': 'JSON',
                'text/html': 'HTML',
                'application/rtf': 'RTF',
                'text/rtf': 'RTF',
                
                # 이미지
                'image/jpeg': 'JPG',
                'image/jpg': 'JPG',
                'image/pjpeg': 'JPG',  # Progressive JPEG
                'image/png': 'PNG',
                'image/x-png': 'PNG',
                'image/gif': 'GIF',
                'image/bmp': 'BMP',
                'image/x-ms-bmp': 'BMP',
                'image/tiff': 'TIFF',
                'image/x-tiff': 'TIFF',
                'image/webp': 'WEBP',
                'image/svg+xml': 'SVG',
                'image/svg': 'SVG',
                'image/x-icon': 'ICO',
                'image/vnd.microsoft.icon': 'ICO',
                
                # 압축
                'application/zip': 'ZIP',
                'application/x-zip-compressed': 'ZIP',
                'application/x-zip': 'ZIP',
                'multipart/x-zip': 'ZIP',
                'application/x-rar-compressed': 'RAR',
                'application/vnd.rar': 'RAR',
                'application/x-rar': 'RAR',
                'application/x-7z-compressed': '7Z',
                'application/x-tar': 'TAR',
                'application/gzip': 'GZ',
                'application/x-gzip': 'GZ',
                'application/x-bzip2': 'BZ2',
                'application/x-bzip': 'BZ2',
                'application/x-xz': 'XZ',
                
                # 동영상
                'video/mp4': 'MP4',
                'video/x-m4v': 'MP4',
                'video/x-msvideo': 'AVI',
                'video/avi': 'AVI',
                'video/x-matroska': 'MKV',
                'video/quicktime': 'MOV',
                'video/x-quicktime': 'MOV',
                'video/webm': 'WEBM',
                'video/x-flv': 'FLV',
                'video/x-ms-wmv': 'WMV',
                'video/mpeg': 'MPEG',
                
                # 오디오
                'audio/mpeg': 'MP3',
                'audio/mp3': 'MP3',
                'audio/wav': 'WAV',
                'audio/x-wav': 'WAV',
                'audio/wave': 'WAV',
                'audio/flac': 'FLAC',
                'audio/x-flac': 'FLAC',
                'audio/aac': 'AAC',
                'audio/ogg': 'OGG',
                'audio/vorbis': 'OGG',
                'audio/x-ms-wma': 'WMA',
                'audio/mp4': 'M4A',
                'audio/x-m4a': 'M4A',
            }
            
            # Content-Type으로 정확한 타입 판별
            if content_type:
                # charset 제거 (예: "application/pdf; charset=utf-8" → "application/pdf")
                content_type_clean = content_type.split(';')[0].strip()
                
                # 정확한 매칭 시도
                if content_type_clean in mime_to_type:
                    info['type'] = mime_to_type[content_type_clean]
                else:
                    # 부분 매칭으로 폴백
                    for mime, file_type in mime_to_type.items():
                        if mime in content_type:
                            info['type'] = file_type
                            break
            
                # 일반적인 패턴으로 추가 판별
                if info['type'] == 'UNKNOWN':
                    if 'pdf' in content_type:
                        info['type'] = 'PDF'
                    elif 'hwp' in content_type or 'haansoft' in content_type:
                        info['type'] = 'HWP'
                    elif 'word' in content_type:
                        info['type'] = 'DOCX' if 'openxml' in content_type else 'DOC'
                    elif 'excel' in content_type or 'spreadsheet' in content_type:
                        info['type'] = 'XLSX' if 'openxml' in content_type else 'XLS'
                    elif 'powerpoint' in content_type or 'presentation' in content_type:
                        info['type'] = 'PPTX' if 'openxml' in content_type else 'PPT'
                    elif 'image/' in content_type:
                        info['type'] = 'IMAGE'
                    elif 'video/' in content_type:
                        info['type'] = 'VIDEO'
                    elif 'audio/' in content_type:
                        info['type'] = 'AUDIO'
                    elif 'text/' in content_type:
                        info['type'] = 'TXT'
                    elif 'application/octet-stream' in content_type:
                        # 바이너리 스트림인 경우 확장자나 시그니처로 판단 필요
                        info['type'] = 'BINARY'
            
            # 2단계: 파일명 추출 및 확장자 체크
            filename = self.extract_filename_from_header(response.headers)
            if filename:
                info['name'] = filename
                
                # Content-Type이 불명확한 경우 확장자로 보완
                if info['type'] in ['UNKNOWN', 'BINARY']:
                    ext = filename.split('.')[-1].upper() if '.' in filename else ''
                    
                    # 지원하는 모든 확장자
                    ext_to_type = {
                        # 문서
                        'PDF': 'PDF', 'HWP': 'HWP', 'HWPX': 'HWPX', 'DOC': 'DOC', 'DOCX': 'DOCX',
                        'XLS': 'XLS', 'XLSX': 'XLSX', 'PPT': 'PPT', 'PPTX': 'PPTX',
                        'TXT': 'TXT', 'RTF': 'RTF', 'CSV': 'CSV', 'XML': 'XML', 'JSON': 'JSON',
                        'HTML': 'HTML', 'HTM': 'HTML', 'CELL': 'CELL', 'SHOW': 'SHOW',
                        # 이미지
                        'JPG': 'JPG', 'JPEG': 'JPG', 'PNG': 'PNG', 'GIF': 'GIF', 'BMP': 'BMP',
                        'TIFF': 'TIFF', 'TIF': 'TIFF', 'WEBP': 'WEBP', 'SVG': 'SVG', 'ICO': 'ICO',
                        # 압축
                        'ZIP': 'ZIP', 'RAR': 'RAR', '7Z': '7Z', 'TAR': 'TAR', 'GZ': 'GZ',
                        'BZ2': 'BZ2', 'XZ': 'XZ', 'ARJ': 'ARJ', 'CAB': 'CAB', 'ISO': 'ISO',
                        # 동영상
                        'MP4': 'MP4', 'AVI': 'AVI', 'MKV': 'MKV', 'MOV': 'MOV', 'WMV': 'WMV',
                        'FLV': 'FLV', 'WEBM': 'WEBM', 'M4V': 'MP4', 'MPG': 'MPEG', 'MPEG': 'MPEG',
                        # 오디오
                        'MP3': 'MP3', 'WAV': 'WAV', 'FLAC': 'FLAC', 'AAC': 'AAC', 'OGG': 'OGG',
                        'WMA': 'WMA', 'M4A': 'M4A', 'AIFF': 'AIFF', 'APE': 'APE',
                    }
                    
                    if ext in ext_to_type:
                        info['type'] = ext_to_type[ext]
            
            # 파일 크기
            content_length = response.headers.get('Content-Length')
            if content_length:
                info['size'] = int(content_length)
            
            # 3단계: 여전히 UNKNOWN이면 파일 시그니처로 정확한 타입 확인
            if info['type'] in ['UNKNOWN', 'BINARY']:
                content = self.get_file_signature(url)
                if content:
                    detected_type = self.detect_file_type(content)
                    if detected_type != 'UNKNOWN':
                        info['type'] = detected_type
            
            # 파일명이 없으면 URL에서 추출
            if not info['name']:
                parsed_url = urlparse(url)
                path_parts = parsed_url.path.split('/')
                if path_parts and path_parts[-1]:
                    info['name'] = unquote(path_parts[-1])
            
        except Exception as e:
            info['error'] = str(e)
            logger.debug(f"파일 정보 추출 실패: {url} - {e}")
        
        return info
    
    def extract_kstartup_attachments(self, detail_url: str) -> List[Dict]:
        """K-Startup 상세 페이지에서 첨부파일 추출"""
        attachments = []
        
        try:
            response = self.session.get(detail_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 첨부파일 영역 찾기 (여러 패턴 시도)
            patterns = [
                soup.find_all('a', {'class': re.compile('file|attach|download', re.I)}),
                soup.find_all('a', href=re.compile(r'\.(pdf|hwp|doc|docx|xls|xlsx|ppt|pptx|zip)', re.I)),
                soup.select('.file-list a, .attach-list a, .download-list a'),
                soup.find_all('a', text=re.compile(r'\.(pdf|hwp|doc|docx|xls|xlsx|ppt|pptx|zip)', re.I))
            ]
            
            found_links = set()
            for links in patterns:
                for link in links:
                    href = link.get('href')
                    if href and href not in found_links:
                        found_links.add(href)
                        
                        # 절대 URL로 변환
                        file_url = urljoin(detail_url, href)
                        
                        # 파일 정보 추출
                        file_info = self.get_file_info_from_url(file_url)
                        
                        # 링크 텍스트에서 파일명 힌트
                        if not file_info['name']:
                            link_text = link.get_text(strip=True)
                            if link_text and not link_text.startswith('http'):
                                file_info['name'] = link_text
                        
                        attachments.append(file_info)
            
        except Exception as e:
            logger.error(f"K-Startup 첨부파일 추출 실패: {detail_url} - {e}")
        
        return attachments
    
    def extract_bizinfo_attachments(self, detail_url: str) -> List[Dict]:
        """BizInfo 상세 페이지에서 첨부파일 추출"""
        attachments = []
        
        try:
            response = self.session.get(detail_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # BizInfo 특유의 첨부파일 구조
            # 1. div.file_name에서 정확한 파일명
            file_divs = soup.find_all('div', class_='file_name')
            for div in file_divs:
                filename = div.get_text(strip=True)
                # 다운로드 링크 찾기
                parent = div.parent
                if parent:
                    link = parent.find('a', href=True)
                    if link:
                        file_url = urljoin(detail_url, link['href'])
                        file_info = self.get_file_info_from_url(file_url)
                        if filename:
                            file_info['name'] = filename
                        attachments.append(file_info)
            
            # 2. viewer.do 형식 링크
            viewer_links = soup.find_all('a', href=re.compile(r'viewer\.do\?', re.I))
            for link in viewer_links:
                file_url = urljoin(detail_url, link['href'])
                file_info = self.get_file_info_from_url(file_url)
                
                # title 속성에서 파일명
                if link.get('title'):
                    file_info['name'] = link['title']
                elif not file_info['name']:
                    file_info['name'] = link.get_text(strip=True)
                
                attachments.append(file_info)
            
            # 3. 일반 다운로드 링크
            download_links = soup.find_all('a', href=re.compile(r'download|fileDown', re.I))
            for link in download_links:
                file_url = urljoin(detail_url, link['href'])
                if not any(att['url'] == file_url for att in attachments):
                    file_info = self.get_file_info_from_url(file_url)
                    if not file_info['name']:
                        file_info['name'] = link.get_text(strip=True)
                    attachments.append(file_info)
            
        except Exception as e:
            logger.error(f"BizInfo 첨부파일 추출 실패: {detail_url} - {e}")
        
        return attachments
    
    def process_record(self, record: Dict) -> bool:
        """단일 레코드 처리"""
        try:
            record_id = record.get('id')
            announcement_id = record.get('announcement_id') or record.get('pblanc_sn')
            detail_url = record.get('pblanc_url') or record.get('detl_pg_url')
            
            if not detail_url:
                logger.debug(f"상세 URL 없음: ID {record_id}")
                return False
            
            # 이미 처리된 경우 스킵
            if record.get('attachment_processing_status') == 'completed':
                existing_urls = record.get('attachment_urls')
                if existing_urls:
                    try:
                        parsed = json.loads(existing_urls) if isinstance(existing_urls, str) else existing_urls
                        if isinstance(parsed, list) and len(parsed) > 0:
                            with lock:
                                stats['skip'] += 1
                            return False
                    except:
                        pass
            
            # 소스 타입 자동 감지
            if self.source_type == 'auto':
                if 'k-startup' in detail_url.lower():
                    source = 'kstartup'
                elif 'bizinfo' in detail_url.lower():
                    source = 'bizinfo'
                else:
                    # 테이블명으로 판단
                    source = 'kstartup' if 'KS_' in str(announcement_id) else 'bizinfo'
            else:
                source = self.source_type
            
            # 첨부파일 추출
            if source == 'kstartup':
                attachments = self.extract_kstartup_attachments(detail_url)
            else:
                attachments = self.extract_bizinfo_attachments(detail_url)
            
            # 결과 저장
            update_data = {
                'attachment_urls': json.dumps(attachments, ensure_ascii=False),
                'attachment_processing_status': 'completed' if attachments else 'no_attachments',
                'attachment_processed_at': datetime.now().isoformat(),
                'attachment_count': len(attachments)
            }
            
            # 테이블 선택
            table_name = 'kstartup_complete' if source == 'kstartup' else 'bizinfo_complete'
            
            # 업데이트
            self.supabase.table(table_name).update(update_data).eq('id', record_id).execute()
            
            with lock:
                stats['success'] += 1
                if attachments:
                    stats['attachments_found'] += len(attachments)
                    stats['attachments_updated'] += 1
            
            logger.info(f"처리 완료: ID {record_id} - {len(attachments)}개 첨부파일")
            return True
            
        except Exception as e:
            logger.error(f"레코드 처리 실패: {record.get('id')} - {e}")
            with lock:
                stats['error'] += 1
            return False
    
    def process_batch(self, source: str = 'both', mode: str = 'daily', max_workers: int = 5):
        """배치 처리"""
        logger.info(f"배치 처리 시작: source={source}, mode={mode}")
        
        # 처리할 레코드 조회
        records = []
        
        if source in ['kstartup', 'both']:
            query = self.supabase.table('kstartup_complete').select('*')
            
            # 처리 안 된 것 우선
            query = query.is_('attachment_processing_status', None)
            
            if mode == 'daily':
                # 최근 7일
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                query = query.gte('created_at', week_ago)
            
            result = query.limit(1000).execute()
            if result.data:
                records.extend(result.data)
                logger.info(f"K-Startup: {len(result.data)}개 레코드")
        
        if source in ['bizinfo', 'both']:
            query = self.supabase.table('bizinfo_complete').select('*')
            
            # 처리 안 된 것 우선
            query = query.is_('attachment_processing_status', None)
            
            if mode == 'daily':
                # 최근 7일
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                query = query.gte('created_at', week_ago)
            
            result = query.limit(1000).execute()
            if result.data:
                records.extend(result.data)
                logger.info(f"BizInfo: {len(result.data)}개 레코드")
        
        if not records:
            logger.info("처리할 레코드가 없습니다")
            return
        
        stats['total'] = len(records)
        logger.info(f"총 {len(records)}개 레코드 처리 시작")
        
        # 병렬 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for record in records:
                future = executor.submit(self.process_record, record)
                futures.append(future)
            
            # 진행 상황 모니터링
            for future in as_completed(futures):
                with lock:
                    stats['processed'] += 1
                    if stats['processed'] % 10 == 0:
                        logger.info(f"진행: {stats['processed']}/{stats['total']} "
                                  f"(성공: {stats['success']}, 실패: {stats['error']}, "
                                  f"스킵: {stats['skip']})")
        
        # 최종 보고
        logger.info("="*60)
        logger.info("📊 처리 완료 보고서")
        logger.info("="*60)
        logger.info(f"총 레코드: {stats['total']}개")
        logger.info(f"처리 완료: {stats['processed']}개")
        logger.info(f"성공: {stats['success']}개")
        logger.info(f"실패: {stats['error']}개")
        logger.info(f"스킵: {stats['skip']}개")
        logger.info(f"발견된 첨부파일: {stats['attachments_found']}개")
        logger.info(f"업데이트된 레코드: {stats['attachments_updated']}개")
        logger.info("="*60)


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='통합 첨부파일 처리기')
    parser.add_argument('--source', choices=['kstartup', 'bizinfo', 'both'], 
                       default='both', help='처리할 소스')
    parser.add_argument('--mode', choices=['daily', 'full'], 
                       default='daily', help='처리 모드')
    parser.add_argument('--workers', type=int, default=5, 
                       help='병렬 처리 워커 수')
    
    args = parser.parse_args()
    
    # 처리기 실행
    processor = UnifiedAttachmentProcessor(source_type='auto')
    processor.process_batch(
        source=args.source,
        mode=args.mode,
        max_workers=args.workers
    )


if __name__ == '__main__':
    main()