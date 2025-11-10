#!/usr/bin/env python3
"""
Supabase DB → Google Sheets 동기화
STEP 9: 최신 공고를 Google Sheets에 동기화

작성일: 2025-10-28
"""

import os
import sys
import io

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

# Google Sheets API
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Supabase
from supabase import create_client, Client

# 프로젝트 루트 경로 추가
project_root = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(project_root))

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()


class DBToGoogleSheetsSync:
    """Supabase DB → Google Sheets 동기화"""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        spreadsheet_id: Optional[str] = None
    ):
        """
        Args:
            credentials_path: Google 서비스 계정 JSON 파일 경로 (기본값: 프로젝트 루트/credentials.json)
            spreadsheet_id: Google Sheets ID (환경변수 SPREADSHEET_ID 사용 가능)
        """
        # ✅ credentials_path가 None이면 프로젝트 루트 경로 자동 계산
        if credentials_path is None:
            # sync_db_to_google_sheets.py → uploaders → tasks → 0918_task → prefect → pipeline_steps → scripts → gov-support-automation (7단계)
            project_root = Path(__file__).resolve().parents[6]
            credentials_path = str(project_root / "credentials.json")

        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id or os.getenv('SPREADSHEET_ID')

        # Supabase 클라이언트
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_KEY')
        )

        # Google Sheets 서비스
        self.sheets_service = self._init_google_sheets()

        # 통계
        self.stats = {
            'kstartup': {'new': 0, 'duplicate': 0, 'total': 0},
            'bizinfo': {'new': 0, 'duplicate': 0, 'total': 0}
        }

    def _init_google_sheets(self):
        """Google Sheets API 초기화"""
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=credentials)

    def _get_existing_announcement_ids(self, sheet_name: str) -> set:
        """
        Google Sheets에서 기존 공고ID 가져오기

        Args:
            sheet_name: 시트 이름 (공고정리본 or 공고정리본_기업마당)

        Returns:
            set: 기존 공고ID 집합
        """
        try:
            # A열(공고ID) 읽기
            range_name = f"{sheet_name}!A:A"
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            existing_ids = set()
            if 'values' in result:
                # 헤더 제외, 빈 값 제외
                existing_ids = set(
                    row[0] for row in result['values'][1:]
                    if row and row[0]
                )

            print(f"  📋 {sheet_name}: 기존 {len(existing_ids)}개 공고")
            return existing_ids

        except Exception as e:
            print(f"  ⚠️ {sheet_name} 조회 실패 (빈 시트일 수 있음): {e}")
            return set()

    def _fetch_latest_announcements(
        self,
        source: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Supabase에서 최신 공고 조회

        Args:
            source: 'kstartup' or 'bizinfo'
            limit: 조회할 최대 개수

        Returns:
            List[Dict]: 공고 목록
        """
        table_name = f"{source}_complete"

        try:
            # 최근 등록된 순으로 조회 (테이블별 컬럼 이름 다름)
            if source == 'kstartup':
                # K-Startup: announcement_id, biz_pbanc_nm, pbanc_ntrp_nm 등
                response = self.supabase.table(table_name).select(
                    'announcement_id, biz_pbanc_nm, pbanc_ntrp_nm, '
                    'pbanc_rcpt_bgng_dt, pbanc_rcpt_end_dt, detl_pg_url, '
                    'created_at, summary, simple_summary, detailed_summary'
                ).order('created_at', desc=True).limit(limit).execute()

                # 컬럼 이름 표준화
                announcements = []
                for row in (response.data or []):
                    announcements.append({
                        'announcement_id': row.get('announcement_id'),
                        'title': row.get('biz_pbanc_nm'),
                        'organization': row.get('pbanc_ntrp_nm'),
                        'start_date': row.get('pbanc_rcpt_bgng_dt'),
                        'end_date': row.get('pbanc_rcpt_end_dt'),
                        'url': row.get('detl_pg_url'),  # pbanc_url → detl_pg_url
                        'created_at': row.get('created_at'),
                        'summary': row.get('summary'),
                        'simple_summary': row.get('simple_summary'),
                        'detailed_summary': row.get('detailed_summary')
                    })
            else:  # bizinfo
                # BizInfo: pblanc_id, pblanc_nm, mng_inst_nm 등
                response = self.supabase.table(table_name).select(
                    'pblanc_id, pblanc_nm, mng_inst_nm, '
                    'reqst_bgng_ymd, reqst_end_ymd, pblanc_url, '
                    'created_at, summary, simple_summary, detailed_summary'
                ).order('created_at', desc=True).limit(limit).execute()

                # 컬럼 이름 표준화
                announcements = []
                for row in (response.data or []):
                    announcements.append({
                        'announcement_id': row.get('pblanc_id'),
                        'title': row.get('pblanc_nm'),
                        'organization': row.get('mng_inst_nm'),
                        'start_date': row.get('reqst_bgng_ymd'),
                        'end_date': row.get('reqst_end_ymd'),
                        'url': row.get('pblanc_url'),
                        'created_at': row.get('created_at'),
                        'summary': row.get('summary'),
                        'simple_summary': row.get('simple_summary'),
                        'detailed_summary': row.get('detailed_summary')
                    })

            print(f"  📊 {source}: DB에서 {len(announcements)}개 조회")
            return announcements

        except Exception as e:
            print(f"  ❌ {source} DB 조회 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _format_row_for_sheets(
        self,
        announcement: Dict,
        source: str
    ) -> List[str]:
        """
        공고 데이터를 Google Sheets 행 형식으로 변환

        Args:
            announcement: 공고 데이터
            source: 'kstartup' or 'bizinfo'

        Returns:
            List[str]: 행 데이터 (13열)
        """
        # 날짜 포맷 변환
        def format_date(date_str):
            if not date_str:
                return ''
            try:
                # ISO 형식 → YYYY-MM-DD
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            except:
                return str(date_str)

        # 카테고리 ID 매핑 (기본값: 48-기타)
        category_map = {
            '자금지원': '22',
            '정책자금': '23',
            '시설/공간': '24',
            '교육/컨설팅': '25',
            '인력지원': '26',
            '기술개발': '27',
            '해외진출': '28',
            '판로/마케팅': '45',
            '네트워킹': '46',
            '농림축수산업': '47',
        }

        category = announcement.get('category', '')
        category_id = category_map.get(category, '48')

        # 공고ID에서 접두사 제거 (KS_ / PBLN_ 제거)
        ann_id = announcement.get('announcement_id', '')
        if ann_id.startswith('KS_'):
            ann_id = ann_id.replace('KS_', '')
        elif ann_id.startswith('PBLN_'):
            ann_id = ann_id.replace('PBLN_', '')

        # 동기화 실행 시점의 로컬 시간 (월/일/년 시:분:초 형식)
        now = datetime.now()
        sync_time = f'{now.month}/{now.day}/{now.year} {now.hour}:{now.minute:02d}:{now.second:02d}'

        # 행 데이터 (A~M열, 13열)
        row = [
            ann_id,                                            # A: 공고ID (접두사 제거)
            announcement.get('title', ''),                     # B: 공고명
            '',                                                 # C: 빈칸
            announcement.get('organization', ''),              # D: 소관명/수행기관
            '',                                                 # E: 수행기관 (비워둠)
            sync_time,                                         # F: 등록일자 (동기화 시점)
            format_date(announcement.get('start_date')),       # G: 신청시작일
            format_date(announcement.get('end_date')),         # H: 신청종료일
            '',                                                 # I: 지원대상 (비워둠)
            '',                                                 # J: 빈칸
            '',                                                 # K: 빈칸
            announcement.get('url', ''),                       # L: 공고URL
            '케이스타트업' if source == 'kstartup' else '기업마당',  # M: 출처
        ]

        # 추가 열 (있을 경우)
        # N~R: 빈칸 예약
        for _ in range(5):
            row.append('')

        # S: 원본 정보 (2000-2500자 구조화된 정보)
        row.append(announcement.get('summary', ''))

        # T: HTML 공고문 (DB에 없음, step2_s_to_tuv.py가 채움)
        row.append('')

        # U: 간단요약
        row.append(announcement.get('simple_summary', ''))

        # V: 상세요약
        row.append(announcement.get('detailed_summary', ''))

        return row

    def sync_kstartup(self, limit: int = 100) -> Dict[str, int]:
        """
        K-Startup 공고 동기화

        Args:
            limit: 조회할 최대 개수

        Returns:
            Dict: {'new': int, 'duplicate': int, 'total': int}
        """
        print("\n📡 K-Startup 동기화 시작...")

        sheet_name = "공고정리본"

        # 1. 기존 공고ID 조회
        existing_ids = self._get_existing_announcement_ids(sheet_name)

        # 2. DB에서 최신 공고 조회
        announcements = self._fetch_latest_announcements('kstartup', limit)

        # 3. 신규 공고 필터링
        new_rows = []
        duplicate_count = 0

        for ann in announcements:
            ann_id = ann.get('announcement_id', '')

            # 비교를 위해 접두사 제거
            ann_id_without_prefix = ann_id.replace('KS_', '').replace('PBLN_', '')

            if ann_id_without_prefix in existing_ids:
                duplicate_count += 1
                continue

            row = self._format_row_for_sheets(ann, 'kstartup')
            new_rows.append(row)
            existing_ids.add(ann_id_without_prefix)

        print(f"  ✨ 신규: {len(new_rows)}개")
        print(f"  🔄 중복: {duplicate_count}개")

        # 4. Google Sheets에 추가
        if new_rows:
            self._append_to_sheets(sheet_name, new_rows)
        else:
            print(f"  ✅ 추가할 신규 공고 없음")

        self.stats['kstartup'] = {
            'new': len(new_rows),
            'duplicate': duplicate_count,
            'total': len(announcements)
        }

        return self.stats['kstartup']

    def sync_bizinfo(self, limit: int = 100) -> Dict[str, int]:
        """
        BizInfo 공고 동기화

        Args:
            limit: 조회할 최대 개수

        Returns:
            Dict: {'new': int, 'duplicate': int, 'total': int}
        """
        print("\n📰 BizInfo 동기화 시작...")

        sheet_name = "공고정리본_기업마당"

        # 1. 기존 공고ID 조회
        existing_ids = self._get_existing_announcement_ids(sheet_name)

        # 2. DB에서 최신 공고 조회
        announcements = self._fetch_latest_announcements('bizinfo', limit)

        # 3. 신규 공고 필터링
        new_rows = []
        duplicate_count = 0

        for ann in announcements:
            ann_id = ann.get('announcement_id', '')

            # 비교를 위해 접두사 제거
            ann_id_without_prefix = ann_id.replace('KS_', '').replace('PBLN_', '')

            if ann_id_without_prefix in existing_ids:
                duplicate_count += 1
                continue

            row = self._format_row_for_sheets(ann, 'bizinfo')
            new_rows.append(row)
            existing_ids.add(ann_id_without_prefix)

        print(f"  ✨ 신규: {len(new_rows)}개")
        print(f"  🔄 중복: {duplicate_count}개")

        # 4. Google Sheets에 추가
        if new_rows:
            self._append_to_sheets(sheet_name, new_rows)
        else:
            print(f"  ✅ 추가할 신규 공고 없음")

        self.stats['bizinfo'] = {
            'new': len(new_rows),
            'duplicate': duplicate_count,
            'total': len(announcements)
        }

        return self.stats['bizinfo']

    def _append_to_sheets(self, sheet_name: str, rows: List[List[str]]):
        """
        Google Sheets에 행 추가 (2행 아래로 삽입)

        Args:
            sheet_name: 시트 이름
            rows: 추가할 행 목록
        """
        try:
            # 2행부터 아래로 밀기 위해 행 삽입
            sheet_id = self._get_sheet_id(sheet_name)

            requests = [{
                'insertDimension': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'ROWS',
                        'startIndex': 1,  # 2행 (0-based)
                        'endIndex': 1 + len(rows)
                    },
                    'inheritFromBefore': False
                }
            }]

            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={'requests': requests}
            ).execute()

            # 데이터 삽입
            range_name = f"{sheet_name}!A2:V{1 + len(rows)}"
            body = {'values': rows}

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            print(f"  ✅ Google Sheets에 {len(rows)}건 추가 완료")

        except Exception as e:
            print(f"  ❌ Google Sheets 업로드 실패: {e}")
            raise

    def _get_sheet_id(self, sheet_name: str) -> int:
        """
        시트 이름으로 시트 ID 조회

        Args:
            sheet_name: 시트 이름

        Returns:
            int: 시트 ID
        """
        try:
            spreadsheet = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']

            # 시트를 찾지 못한 경우 0 반환 (첫 번째 시트)
            print(f"  ⚠️ 시트 '{sheet_name}' 찾기 실패, 기본값(0) 사용")
            return 0

        except Exception as e:
            print(f"  ⚠️ 시트 ID 조회 실패: {e}, 기본값(0) 사용")
            return 0

    def run(
        self,
        source: str = 'all',
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        동기화 실행

        Args:
            source: 'kstartup', 'bizinfo', 'all'
            limit: 각 소스별 조회 최대 개수

        Returns:
            Dict: 동기화 결과
        """
        print("=" * 80)
        print("🔄 Supabase DB → Google Sheets 동기화")
        print("=" * 80)

        try:
            if source in ['kstartup', 'all']:
                self.sync_kstartup(limit)

            if source in ['bizinfo', 'all']:
                self.sync_bizinfo(limit)

            # 최종 통계
            total_new = self.stats['kstartup']['new'] + self.stats['bizinfo']['new']
            total_duplicate = (
                self.stats['kstartup']['duplicate'] +
                self.stats['bizinfo']['duplicate']
            )

            print("\n" + "=" * 80)
            print("📊 동기화 완료")
            print("=" * 80)
            print(f"✨ 신규 추가: {total_new}개")
            print(f"🔄 중복 제외: {total_duplicate}개")
            print("=" * 80)

            return {
                'success': True,
                'stats': self.stats,
                'total_new': total_new,
                'total_duplicate': total_duplicate
            }

        except Exception as e:
            print(f"\n❌ 동기화 실패: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }


def sync_db_to_google_sheets(
    source: str = 'all',
    limit: int = 100,
    credentials_path: Optional[str] = None,
    spreadsheet_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Supabase DB → Google Sheets 동기화 (Entry Point)

    Args:
        source: 'kstartup', 'bizinfo', 'all'
        limit: 각 소스별 조회 최대 개수
        credentials_path: Google 서비스 계정 JSON 파일 경로 (기본값: 프로젝트 루트/credentials.json)
        spreadsheet_id: Google Sheets ID (환경변수 SPREADSHEET_ID 사용 가능)

    Returns:
        Dict: 동기화 결과
    """
    syncer = DBToGoogleSheetsSync(
        credentials_path=credentials_path,
        spreadsheet_id=spreadsheet_id
    )

    return syncer.run(source=source, limit=limit)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Supabase DB → Google Sheets 동기화")
    parser.add_argument(
        '--source',
        choices=['kstartup', 'bizinfo', 'all'],
        default='all',
        help='동기화할 소스 (기본값: all)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='각 소스별 조회 최대 개수 (기본값: 100)'
    )
    parser.add_argument(
        '--credentials',
        default='credentials.json',
        help='Google 서비스 계정 JSON 파일 경로 (기본값: credentials.json)'
    )
    parser.add_argument(
        '--spreadsheet-id',
        help='Google Sheets ID (환경변수 SPREADSHEET_ID 사용 가능)'
    )

    args = parser.parse_args()

    result = sync_db_to_google_sheets(
        source=args.source,
        limit=args.limit,
        credentials_path=args.credentials,
        spreadsheet_id=args.spreadsheet_id
    )

    sys.exit(0 if result['success'] else 1)
