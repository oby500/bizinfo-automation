# services/ai/claude_service.py
"""
Claude Sonnet 4.5 AI 서비스

담당 기능:
1. 공고문 분석 (Y → 자격요건, 평가기준, 작성전략)
2. 회사 분석 (Y + Z → 강점, 약점, 차별화)
3. 스타일 추천 (분석 결과 → 최적 스타일)

모델: claude-sonnet-4-5-20250929
가격: Input $3/1M tokens, Output $15/1M tokens
"""

from anthropic import Anthropic
from typing import Dict, Any, Optional
import json
import logging
import os
from datetime import datetime

# 프롬프트 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.prompts import (
    ANALYZE_ANNOUNCEMENT_PROMPT,
    ANALYZE_COMPANY_PROMPT,
    RECOMMEND_STYLE_PROMPT
)

logger = logging.getLogger(__name__)


class ClaudeService:
    """Claude Sonnet 4.5 AI 서비스"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Anthropic API 키 (없으면 환경변수에서 로드)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-5-20250929"

        # 토큰 가격 (USD per 1M tokens)
        self.input_price = 3.00
        self.output_price = 15.00

        logger.info(f"Claude service initialized with model: {self.model}")

    def analyze_announcement(
        self,
        full_text: str,
        parsed_info: Dict[str, Any],
        simple_summary: Optional[str] = None,
        detailed_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        공고문 분석 (Y 분석)

        Args:
            full_text: 공고문 전체 텍스트
            parsed_info: 공고문 구조화 데이터 (JSONB)
            simple_summary: 간단 요약 (선택)
            detailed_summary: 상세 요약 (선택)

        Returns:
            {
                "자격요건": [...],
                "평가기준": [...],
                "심사위원_프로파일": {...},
                "핵심키워드": {...},
                "경쟁강도": {...},
                "작성전략": {...},
                "_metadata": {
                    "model": "claude-sonnet-4-5-20250929",
                    "input_tokens": 1500,
                    "output_tokens": 800,
                    "cost_usd": 0.0165,
                    "cost_krw": 23
                }
            }
        """
        try:
            logger.info("Starting announcement analysis with Claude")

            # parsed_info에서 content_map 추출 (페이지 구조 메타데이터)
            content_map = parsed_info.get("content_map", {})
            content_map_str = json.dumps(content_map, ensure_ascii=False, indent=2)

            # 프롬프트 생성
            prompt = ANALYZE_ANNOUNCEMENT_PROMPT.format(
                full_text=full_text,
                simple_summary=simple_summary or "(없음)",
                detailed_summary=detailed_summary or "(없음)",
                parsed_info_content_map=content_map_str
            )

            logger.debug(f"Prompt length: {len(prompt)} characters")

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.3,  # 정확한 분석을 위해 낮은 temperature
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # 응답 파싱
            analysis_text = response.content[0].text
            logger.debug(f"Response length: {len(analysis_text)} characters")

            # JSON 추출 (```json ... ``` 제거)
            analysis_json = self._extract_json(analysis_text)

            # 토큰 사용량 및 비용 계산
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = self._calculate_cost(input_tokens, output_tokens)
            cost_krw = int(cost_usd * 1400)  # 1 USD = 1400 KRW

            # 메타데이터 추가
            analysis_json["_metadata"] = {
                "model": self.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 4),
                "cost_krw": cost_krw,
                "analyzed_at": datetime.now().isoformat()
            }

            logger.info(f"Analysis completed. Tokens: {input_tokens}+{output_tokens}, Cost: ${cost_usd:.4f}")

            return analysis_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {str(e)}")
            logger.error(f"Raw response: {analysis_text[:500]}...")
            raise ValueError(f"Claude 응답을 JSON으로 파싱할 수 없습니다: {str(e)}")

        except Exception as e:
            logger.error(f"Announcement analysis failed: {str(e)}")
            raise

    def analyze_company(
        self,
        announcement_analysis: Dict[str, Any],
        company_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        회사 분석 (Z 분석)

        Args:
            announcement_analysis: 공고 분석 결과
            company_info: 회사 정보 (Z)

        Returns:
            {
                "강점분석": [...],
                "약점분석": [...],
                "차별화포인트": [...],
                "리스크체크": {...},
                "최종전략": {...},
                "_metadata": {...}
            }
        """
        try:
            logger.info("Starting company analysis with Claude")

            # JSON 직렬화
            announcement_json = json.dumps(announcement_analysis, ensure_ascii=False, indent=2)
            company_json = json.dumps(company_info, ensure_ascii=False, indent=2)

            # 프롬프트 생성
            prompt = ANALYZE_COMPANY_PROMPT.format(
                announcement_analysis=announcement_json,
                company_info=company_json
            )

            logger.debug(f"Prompt length: {len(prompt)} characters")

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # 응답 파싱
            analysis_text = response.content[0].text
            logger.debug(f"Response length: {len(analysis_text)} characters")

            # JSON 추출
            analysis_json = self._extract_json(analysis_text)

            # 토큰 사용량 및 비용 계산
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = self._calculate_cost(input_tokens, output_tokens)
            cost_krw = int(cost_usd * 1400)

            # 메타데이터 추가
            analysis_json["_metadata"] = {
                "model": self.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 4),
                "cost_krw": cost_krw,
                "analyzed_at": datetime.now().isoformat()
            }

            logger.info(f"Company analysis completed. Tokens: {input_tokens}+{output_tokens}, Cost: ${cost_usd:.4f}")

            return analysis_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {str(e)}")
            raise ValueError(f"Claude 응답을 JSON으로 파싱할 수 없습니다: {str(e)}")

        except Exception as e:
            logger.error(f"Company analysis failed: {str(e)}")
            raise

    def recommend_style(
        self,
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        스타일 추천 (Standard, Premium 전용)

        Args:
            announcement_analysis: 공고 분석 결과
            company_analysis: 회사 분석 결과

        Returns:
            {
                "recommended_style": "data",
                "analysis": [
                    {
                        "style": "data",
                        "score": 85,
                        "pros": [...],
                        "cons": [...]
                    },
                    ...
                ],
                "final_recommendation": {
                    "style": "data",
                    "reason": "...",
                    "expected_improvement": "..."
                },
                "_metadata": {...}
            }
        """
        try:
            logger.info("Starting style recommendation with Claude")

            # JSON 직렬화
            announcement_json = json.dumps(announcement_analysis, ensure_ascii=False, indent=2)
            company_json = json.dumps(company_analysis, ensure_ascii=False, indent=2)

            # 프롬프트 생성
            prompt = RECOMMEND_STYLE_PROMPT.format(
                announcement_analysis=announcement_json,
                company_analysis=company_json
            )

            logger.debug(f"Prompt length: {len(prompt)} characters")

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # 응답 파싱
            recommendation_text = response.content[0].text
            logger.debug(f"Response length: {len(recommendation_text)} characters")

            # JSON 추출
            recommendation_json = self._extract_json(recommendation_text)

            # 토큰 사용량 및 비용 계산
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = self._calculate_cost(input_tokens, output_tokens)
            cost_krw = int(cost_usd * 1400)

            # 메타데이터 추가
            recommendation_json["_metadata"] = {
                "model": self.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 4),
                "cost_krw": cost_krw,
                "analyzed_at": datetime.now().isoformat()
            }

            logger.info(f"Style recommendation completed. Tokens: {input_tokens}+{output_tokens}, Cost: ${cost_usd:.4f}")

            return recommendation_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {str(e)}")
            raise ValueError(f"Claude 응답을 JSON으로 파싱할 수 없습니다: {str(e)}")

        except Exception as e:
            logger.error(f"Style recommendation failed: {str(e)}")
            raise

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Claude 응답에서 JSON 추출

        Args:
            text: Claude 응답 텍스트 (```json ... ``` 포함 가능)

        Returns:
            파싱된 JSON 딕셔너리
        """
        # ```json ... ``` 제거
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            # ```만 있는 경우
            start = text.find("```") + 3
            end = text.find("```", start)
            json_str = text[start:end].strip()
        else:
            # 마크다운 코드 블록이 없는 경우
            json_str = text.strip()

        # JSON 파싱
        return json.loads(json_str)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        토큰 사용량 기반 비용 계산

        Args:
            input_tokens: 입력 토큰 수
            output_tokens: 출력 토큰 수

        Returns:
            비용 (USD)
        """
        input_cost = (input_tokens / 1_000_000) * self.input_price
        output_cost = (output_tokens / 1_000_000) * self.output_price
        return input_cost + output_cost


# ============================================================================
# 사용 예시
# ============================================================================

if __name__ == "__main__":
    # 테스트 코드
    import os
    from dotenv import load_dotenv

    load_dotenv()

    service = ClaudeService()

    # 예시 데이터
    full_text = """
    [사업명] 2025년 AI 기반 스마트 제조 혁신 지원사업

    1. 지원 대상
    - 제조업을 영위하는 중소기업
    - 최근 3년 평균 매출액 1,000억원 이하
    - 직원 수 10명 이상 300명 이하

    2. 지원 내용
    - 지원 한도: 최대 3억원 (정부 70%, 기업 30%)
    - 지원 기간: 12개월
    - 지원 분야: AI 기반 생산 자동화, 품질 관리 등

    3. 평가 기준 (총 100점)
    - 기술력 (40점): 특허, 인증, R&D 투자
    - 사업성 (30점): 시장 규모, 경쟁력, 성장 가능성
    - 실행력 (30점): 팀 구성, 추진 계획, 예산 타당성
    """

    parsed_info = {
        "content_map": {
            "sections": [
                {"title": "사업명", "page": 1},
                {"title": "지원 대상", "page": 1},
                {"title": "평가 기준", "page": 2}
            ]
        }
    }

    # 공고 분석
    result = service.analyze_announcement(
        full_text=full_text,
        parsed_info=parsed_info,
        simple_summary="AI 기반 스마트 제조 혁신 지원사업",
        detailed_summary="중소 제조기업 대상 AI 자동화 지원, 최대 3억원"
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
