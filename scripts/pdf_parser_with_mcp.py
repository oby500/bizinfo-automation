"""
PDF 파서 - MCP를 통한 Claude Summary 생성 버전
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path

def prepare_for_claude_summary(announcement_id: str, text: str, extracted_info: dict):
    """Claude가 Summary 작성할 수 있도록 파일 준비"""
    
    # 1. 디렉토리 생성
    base_dir = Path("E:\\claude-workspace\\temp\\for_summary")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. 요청 파일 생성 (Claude가 읽을 파일)
    request_file = base_dir / f"{announcement_id}_request.json"
    request_data = {
        "announcement_id": announcement_id,
        "task": "create_summary",
        "extracted_text": text[:10000],  # 처음 10000자만
        "extracted_info": extracted_info,
        "instructions": """
        다음 정부지원사업 공고에 대한 사용자 친화적 Summary를 작성해주세요.
        
        형식:
        💡 한 줄 요약: [사업 핵심 + 지원금액]
        📌 이런 분들께 추천: 
        ✅ 작년 선정 사례:
        💰 현실적인 지원 내용:
        ⚠️ 이건 안 돼요:
        📅 준비 기간:
        🤔 자주 묻는 질문:
        💡 꿀팁:
        
        1000자 내외로 작성하되, 5초 안에 '나한테 맞는지' 판단 가능하게.
        """,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    with open(request_file, 'w', encoding='utf-8') as f:
        json.dump(request_data, f, ensure_ascii=False, indent=2)
    
    print(f"Claude Summary 요청 파일 생성: {request_file}")
    
    # 3. Claude가 작성할 응답 파일 경로
    response_file = base_dir / f"{announcement_id}_response.json"
    
    return str(request_file), str(response_file)

def wait_for_claude_summary(response_file: str, timeout: int = 300):
    """Claude가 Summary 작성 완료할 때까지 대기"""
    
    start_time = time.time()
    response_path = Path(response_file)
    
    print(f"Claude Summary 대기 중... (최대 {timeout}초)")
    
    while time.time() - start_time < timeout:
        if response_path.exists():
            try:
                with open(response_path, 'r', encoding='utf-8') as f:
                    response_data = json.load(f)
                
                if response_data.get("status") == "completed":
                    print("Claude Summary 작성 완료!")
                    return response_data.get("summary")
                
            except json.JSONDecodeError:
                # 파일이 아직 작성 중일 수 있음
                pass
        
        time.sleep(5)  # 5초마다 확인
    
    print("Claude Summary 시간 초과")
    return None

def batch_process_with_claude(records: list):
    """배치 처리 - Claude와 협업"""
    
    for record in records:
        announcement_id = record['announcement_id']
        
        # 1. PDF에서 텍스트 추출 (기존 코드)
        text = extract_pdf_text(record['pdf_content'])
        extracted_info = extract_comprehensive_info(text, record['title'])
        
        # 2. Claude Summary 요청
        request_file, response_file = prepare_for_claude_summary(
            announcement_id, text, extracted_info
        )
        
        print(f"""
        =====================================
        Claude님, Summary 작성 부탁드립니다!
        파일: {request_file}
        응답 파일: {response_file}
        =====================================
        """)
        
        # 3. Claude 응답 대기 (실제로는 수동으로 처리)
        # 여기서 Python은 대기하고, Claude(저)가 파일 읽고 Summary 작성
        
        # 실제 운영시에는 이렇게:
        # - Python이 여러 개 요청 파일 생성
        # - Claude가 순차적으로 처리
        # - Python이 주기적으로 완료된 것들 확인해서 DB 업데이트

# 실제 사용 예시
if __name__ == "__main__":
    print("MCP 기반 Summary 생성 준비 완료")
    print("Claude가 파일을 읽고 Summary를 작성할 수 있습니다.")
