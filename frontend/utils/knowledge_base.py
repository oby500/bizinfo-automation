"""
Knowledge Base 검색 API
========================

프로젝트 문서 검색 및 조회

사용법:
    from utils.knowledge_base import kb

    # 키워드 검색
    docs = kb.search("writing_analysis")

    # 타입별 검색
    bugs = kb.by_type("bug_report")

    # 최근 문서
    recent = kb.recent(days=7)

    # 특정 문서
    doc = kb.get("KB_PROJECT_DOCS_MASTER_README")
"""

import os
from datetime import timedelta
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv("E:/gov-support-automation/.env")

from supabase import create_client

# 한국시간 유틸리티
import sys
sys.path.insert(0, 'E:/gov-support-automation/frontend')
from utils.korean_time import now


class KnowledgeBase:
    """Knowledge Base 검색 클래스"""

    def __init__(self):
        self.supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        self.table = 'kb_documents'

    def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        status: str = "active",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """키워드로 문서 검색

        Args:
            query: 검색 키워드
            doc_type: 문서 타입 필터
            status: 상태 필터 (active/archived/deprecated)
            limit: 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        qb = self.supabase.table(self.table).select(
            'doc_id, filename, relative_path, doc_type, title, size_bytes, status, updated_at'
        )

        # 상태 필터
        if status:
            qb = qb.eq('status', status)

        # 타입 필터
        if doc_type:
            qb = qb.eq('doc_type', doc_type)

        # 키워드 검색 (제목 또는 파일명)
        if query:
            qb = getattr(qb, 'or')(f"title.ilike.%{query}%,filename.ilike.%{query}%")

        qb = qb.order('updated_at', desc=True).limit(limit)

        return qb.execute().data

    def by_type(
        self,
        doc_type: str,
        status: str = "active",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """타입별 문서 조회

        Args:
            doc_type: 문서 타입 (bug_report, operation_log, guide 등)
            status: 상태 필터
            limit: 최대 결과 수

        Returns:
            문서 리스트
        """
        return self.search("", doc_type=doc_type, status=status, limit=limit)

    def recent(
        self,
        days: int = 7,
        doc_type: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """최근 업데이트된 문서 조회

        Args:
            days: 최근 N일
            doc_type: 문서 타입 필터
            limit: 최대 결과 수

        Returns:
            최근 문서 리스트
        """
        cutoff = (now() - timedelta(days=days)).isoformat()

        qb = self.supabase.table(self.table).select(
            'doc_id, filename, relative_path, doc_type, title, updated_at'
        ).eq('status', 'active').gte('updated_at', cutoff)

        if doc_type:
            qb = qb.eq('doc_type', doc_type)

        qb = qb.order('updated_at', desc=True).limit(limit)

        return qb.execute().data

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """특정 문서 조회

        Args:
            doc_id: 문서 ID

        Returns:
            문서 정보 또는 None
        """
        result = self.supabase.table(self.table).select('*').eq('doc_id', doc_id).execute()
        return result.data[0] if result.data else None

    def get_by_filename(self, filename: str) -> List[Dict[str, Any]]:
        """파일명으로 문서 조회

        Args:
            filename: 파일명 (부분 일치)

        Returns:
            문서 리스트
        """
        return self.supabase.table(self.table).select('*').ilike(
            'filename', f'%{filename}%'
        ).execute().data

    def summary(self) -> Dict[str, Any]:
        """전체 통계 요약

        Returns:
            타입별 문서 수 및 총 개수
        """
        result = self.supabase.table(self.table).select(
            'doc_type'
        ).eq('status', 'active').execute()

        type_counts = {}
        for row in result.data:
            t = row['doc_type']
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total": len(result.data),
            "by_type": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
            "checked_at": now().isoformat()
        }

    def list_types(self) -> List[str]:
        """사용 가능한 문서 타입 목록

        Returns:
            타입 리스트
        """
        summary = self.summary()
        return list(summary['by_type'].keys())

    # ========== 저장 기능 ==========

    def save(
        self,
        title: str,
        content: str,
        doc_type: str = "operation_log",
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """새 문서를 서버에 저장

        Args:
            title: 문서 제목
            content: 문서 내용
            doc_type: 문서 타입 (operation_log, bug_report, guide 등)
            filename: 파일명 (없으면 자동 생성)

        Returns:
            저장된 문서 정보
        """
        from utils.korean_time import now, format_datetime

        # 파일명 자동 생성
        if not filename:
            date_str = format_datetime(fmt="%Y%m%d_%H%M%S")
            filename = f"{doc_type}_{date_str}.md"

        # doc_id 생성
        doc_id = f"KB_SERVER_{filename.replace('.md', '').replace(' ', '_')}"

        data = {
            "doc_id": doc_id,
            "filename": filename,
            "relative_path": f"SERVER/{filename}",
            "doc_type": doc_type,
            "title": title,
            "content": content,
            "size_bytes": len(content.encode('utf-8')),
            "status": "active",
            "scanned_at": now().isoformat()
        }

        result = self.supabase.table(self.table).upsert(data).execute()

        if result.data:
            print(f"[OK] 저장 완료: {doc_id}")
            return result.data[0]
        else:
            print(f"[FAIL] 저장 실패")
            return {}

    def save_operation_log(self, title: str, content: str) -> Dict[str, Any]:
        """작업 로그 저장 (단축 메서드)"""
        return self.save(title, content, doc_type="operation_log")

    def save_bug_report(self, title: str, content: str) -> Dict[str, Any]:
        """버그 리포트 저장 (단축 메서드)"""
        return self.save(title, content, doc_type="bug_report")

    def read_content(self, doc_id: str) -> Optional[str]:
        """문서 내용 읽기

        Args:
            doc_id: 문서 ID

        Returns:
            문서 content 또는 None
        """
        doc = self.get(doc_id)
        if doc and doc.get('content'):
            return doc['content']
        return None

    def read_recent_logs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """최근 작업 로그 내용까지 읽기

        Returns:
            최근 operation_log 문서 (content 포함)
        """
        result = self.supabase.table(self.table).select(
            'doc_id, title, content, created_at'
        ).eq('doc_type', 'operation_log').eq('status', 'active').order(
            'created_at', desc=True
        ).limit(limit).execute()

        return result.data


# 싱글톤 인스턴스
kb = KnowledgeBase()


# CLI 테스트
if __name__ == "__main__":
    print("=" * 50)
    print("Knowledge Base 테스트")
    print("=" * 50)

    # 요약
    print("\n[1] 전체 요약")
    summary = kb.summary()
    print(f"    총 문서: {summary['total']}개")
    print(f"    타입 수: {len(summary['by_type'])}개")

    # 검색 테스트
    print("\n[2] 검색 테스트: 'bug'")
    results = kb.search("bug", limit=5)
    for doc in results:
        print(f"    - {doc['filename']}: {doc['title'][:40]}...")

    # 타입별 조회
    print("\n[3] 버그 리포트 조회")
    bugs = kb.by_type("bug_report", limit=5)
    for doc in bugs:
        print(f"    - {doc['filename']}")

    # 최근 문서
    print("\n[4] 최근 7일 문서")
    recent = kb.recent(days=7, limit=5)
    for doc in recent:
        print(f"    - {doc['filename']}")

    print("\n" + "=" * 50)
    print("테스트 완료!")
    print("=" * 50)
