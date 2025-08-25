# 기업마당 vs K-Startup 첨부파일 수집 방식 비교 분석

## 📊 핵심 차이점 비교표

| 구분 | 기업마당 (BizInfo) ✅ | K-Startup ❌ | 개선 필요사항 |
|------|-------------------|------------|--------------|
| **파일 타입 감지** | 파일 시그니처 기반 | 단순 'FILE' 고정 | 시그니처 감지 도입 필요 |
| **실제 확장자 확인** | 바이너리 헤더 분석 | 없음 | 파일 헤더 읽기 구현 |
| **파일명 추출** | Content-Disposition 헤더 | 링크 텍스트만 | HTTP 헤더 분석 추가 |
| **타입 분류** | HWP, PDF, DOCX 등 15종 | FILE 단일 타입 | 세분화된 타입 체계 |
| **안전 파일명** | ID+순번+확장자 | ID+순번만 | 실제 확장자 포함 |
| **중복 처리** | URL 기반 Set 관리 | URL 중복 체크 | ✅ 동일 |
| **오류 복구** | 3회 재시도 + 폴백 | 단순 continue | 재시도 로직 필요 |

## 🔍 상세 분석

### 1. 기업마당 방식 (바람직한 방식) ✅

```python
# 파일 시그니처로 실제 타입 감지
def get_file_type_by_signature(url, session=None):
    # 파일의 처음 1024바이트만 다운로드
    headers = {'Range': 'bytes=0-1024'}
    response = session.get(url, headers=headers, timeout=10, stream=True)
    content = response.content[:1024]
    
    # 바이너리 시그니처로 정확한 타입 판단
    if content[:4] == b'%PDF':
        return 'PDF'
    elif content[:2] == b'PK':  # ZIP 기반 (DOCX, XLSX 등)
        if b'word/' in full_content[:2000]:
            return 'DOCX'
        elif b'xl/' in full_content[:2000]:
            return 'XLSX'
    elif content[:4] == b'\xd0\xcf\x11\xe0':  # MS Office 구형
        return 'HWP' or 'DOC'
```

**장점:**
- ✅ 정확한 파일 타입 감지 (바이너리 레벨)
- ✅ 확장자 위장 파일도 정확히 식별
- ✅ 최소한의 데이터만 다운로드 (Range 헤더)
- ✅ 15가지 파일 타입 구분

### 2. K-Startup 현재 방식 ❌

```python
# 단순히 FILE 타입으로만 처리
attachment = {
    'url': full_url,
    'text': filename,
    'type': 'FILE',  # ❌ 모든 파일이 FILE
    'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",  # ❌ 확장자 없음
}
```

**문제점:**
- ❌ 모든 파일이 'FILE' 타입
- ❌ 실제 파일 형식 알 수 없음
- ❌ 안전 파일명에 확장자 없음
- ❌ 파일 다운로드 시 타입 추측 불가

## 🛠️ K-Startup 개선 방안

### 1단계: 파일 시그니처 감지 추가

```python
def get_kstartup_file_type(url, session):
    """K-Startup 파일의 실제 타입 감지"""
    try:
        # Range 헤더로 처음 1KB만 다운로드
        headers = {'Range': 'bytes=0-1024'}
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code in [200, 206]:
            content = response.content[:1024]
            
            # 파일 시그니처 체크
            if content[:4] == b'%PDF':
                return 'PDF'
            elif content[:8] == b'HWP Document':
                return 'HWP'
            elif b'PK' in content[:2]:
                # Office 2007+ 문서
                full_resp = session.get(url, timeout=15)
                if b'word/' in full_resp.content[:5000]:
                    return 'DOCX'
                elif b'xl/' in full_resp.content[:5000]:
                    return 'XLSX'
                elif b'ppt/' in full_resp.content[:5000]:
                    return 'PPTX'
                else:
                    return 'ZIP'
            
        # Content-Disposition 헤더에서 파일명 추출
        if 'content-disposition' in response.headers:
            filename = extract_filename_from_header(response.headers['content-disposition'])
            return guess_type_from_filename(filename)
            
    except Exception:
        return 'FILE'  # 폴백
```

### 2단계: 향상된 첨부파일 구조

```python
def extract_attachments_improved(page_url, announcement_id):
    """개선된 K-Startup 첨부파일 추출"""
    attachments = []
    
    # 기존 추출 로직...
    for link in download_links:
        url = urljoin(page_url, link.get('href'))
        text = link.get_text(strip=True)
        
        # 파일 타입 감지 (기업마당 방식)
        file_type = get_kstartup_file_type(url, session)
        
        # 확장자 결정
        extension = file_type.lower() if file_type != 'FILE' else 'bin'
        
        # 개선된 첨부파일 정보
        attachment = {
            'url': url,
            'type': file_type,  # 실제 타입
            'text': text,
            'original_filename': text,
            'display_filename': text or f'첨부파일_{len(attachments)+1}',
            'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}.{extension}",
            'file_size': None,  # 추후 추가 가능
            'mime_type': get_mime_type(file_type),
            'params': extract_params_from_url(url)
        }
        
        attachments.append(attachment)
```

### 3단계: 파일 타입별 처리

```python
FILE_TYPE_INFO = {
    'HWP': {'ext': 'hwp', 'mime': 'application/x-hwp', 'icon': '📄'},
    'PDF': {'ext': 'pdf', 'mime': 'application/pdf', 'icon': '📕'},
    'DOCX': {'ext': 'docx', 'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'icon': '📘'},
    'XLSX': {'ext': 'xlsx', 'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'icon': '📊'},
    'PPTX': {'ext': 'pptx', 'mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'icon': '📑'},
    'ZIP': {'ext': 'zip', 'mime': 'application/zip', 'icon': '📦'},
    'JPG': {'ext': 'jpg', 'mime': 'image/jpeg', 'icon': '🖼️'},
    'PNG': {'ext': 'png', 'mime': 'image/png', 'icon': '🖼️'},
}
```

## 📈 예상 개선 효과

### 현재 K-Startup 데이터
```json
{
    "url": "https://www.k-startup.go.kr/afile/fileDownload/...",
    "type": "FILE",
    "text": "사업계획서",
    "safe_filename": "KS_173687_01"
}
```

### 개선 후 (기업마당 방식 적용)
```json
{
    "url": "https://www.k-startup.go.kr/afile/fileDownload/...",
    "type": "HWP",
    "text": "사업계획서",
    "original_filename": "2025년_창업지원_사업계획서.hwp",
    "safe_filename": "KS_173687_01.hwp",
    "file_size": 1024576,
    "mime_type": "application/x-hwp",
    "detected_by": "signature",
    "confidence": 0.99
}
```

## 🔧 구현 우선순위

1. **[HIGH]** 파일 시그니처 감지 함수 추가
2. **[HIGH]** 파일 타입별 확장자 매핑
3. **[MEDIUM]** Content-Disposition 헤더 파싱
4. **[MEDIUM]** 파일 크기 정보 수집
5. **[LOW]** MIME 타입 정보 추가
6. **[LOW]** 파일 아이콘 시각화

## 📊 기대 효과

- **정확도**: 파일 타입 정확도 99% 이상
- **활용성**: 파일별 적절한 처리 가능
- **검색성**: 타입별 필터링 가능
- **다운로드**: 올바른 확장자로 저장
- **통계**: 파일 타입별 분석 가능

## 💡 추가 개선 아이디어

1. **파일 크기 제한**: 대용량 파일 감지 및 경고
2. **악성 파일 체크**: 바이러스 스캔 API 연동
3. **썸네일 생성**: 이미지/PDF 미리보기
4. **압축 파일 분석**: ZIP 내부 파일 목록
5. **버전 관리**: 동일 파일의 버전 추적

---
*기업마당의 견고한 파일 처리 방식을 K-Startup에 적용하면 데이터 품질이 크게 향상될 것입니다.*