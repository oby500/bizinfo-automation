# services/ai/openai_service.py
"""
GPT-4o AI 서비스

담당 기능:
1. 신청서 생성 (공고 분석 + 회사 분석 + 스타일 → 신청서 텍스트)

모델: gpt-4o
가격: Input $2.5/1M tokens, Output $10/1M tokens
"""

from openai import OpenAI
from typing import Dict, Any, Optional, List
import json
import logging
import os
from datetime import datetime

# 프롬프트 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.prompts import GENERATE_APPLICATION_PROMPT, STYLE_GUIDES

logger = logging.getLogger(__name__)


class OpenAIService:
    """GPT-4o AI 서비스"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 로드)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"

        # 토큰 가격 (USD per 1M tokens)
        self.input_price = 2.50
        self.output_price = 10.00

        logger.info(f"OpenAI service initialized with model: {self.model}")

    def generate_application(
        self,
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any],
        style: str = "balanced",
        target_length: int = 2500
    ) -> Dict[str, Any]:
        """
        신청서 생성

        Args:
            announcement_analysis: 공고 분석 결과 (Claude)
            company_analysis: 회사 분석 결과 (Claude)
            style: 작성 스타일 (data, story, balanced, aggressive, conservative)
            target_length: 목표 글자 수 (기본 2500자)

        Returns:
            {
                "content": "신청서 전체 텍스트 (2000-3000자)",
                "sections": [
                    {
                        "title": "1. 기술력",
                        "content": "...",
                        "word_count": 500,
                        "tables": 2
                    },
                    ...
                ],
                "statistics": {
                    "total_words": 2550,
                    "total_tables": 5,
                    "total_sections": 6
                },
                "_metadata": {
                    "model": "gpt-4o",
                    "style": "balanced",
                    "input_tokens": 2000,
                    "output_tokens": 1200,
                    "cost_usd": 0.017,
                    "cost_krw": 24
                }
            }
        """
        try:
            logger.info(f"Starting application generation with GPT-4o (style: {style})")

            # 스타일 가이드 가져오기
            if style not in STYLE_GUIDES:
                raise ValueError(f"Invalid style: {style}. Must be one of {list(STYLE_GUIDES.keys())}")

            style_guide = STYLE_GUIDES[style]

            # JSON 직렬화
            announcement_json = json.dumps(announcement_analysis, ensure_ascii=False, indent=2)
            company_json = json.dumps(company_analysis, ensure_ascii=False, indent=2)
            style_guide_json = json.dumps(style_guide, ensure_ascii=False, indent=2)

            # 프롬프트 생성
            prompt = GENERATE_APPLICATION_PROMPT.format(
                announcement_analysis=announcement_json,
                company_analysis=company_json,
                style_guide=style_guide_json,
                target_length=target_length
            )

            logger.debug(f"Prompt length: {len(prompt)} characters")

            # GPT-4o API 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 정부지원사업 신청서 작성 전문가입니다. 과거 100개 이상의 선정된 신청서를 작성했습니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,  # 창의적인 작성을 위해 적절한 temperature
                max_tokens=4096,
                response_format={"type": "json_object"}  # JSON 응답 강제
            )

            # 응답 파싱
            application_text = response.choices[0].message.content
            logger.debug(f"Response length: {len(application_text)} characters")

            # JSON 파싱
            application_json = json.loads(application_text)

            # 토큰 사용량 및 비용 계산
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost_usd = self._calculate_cost(input_tokens, output_tokens)
            cost_krw = int(cost_usd * 1400)

            # 메타데이터 추가
            application_json["_metadata"] = {
                "model": self.model,
                "style": style,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 4),
                "cost_krw": cost_krw,
                "generated_at": datetime.now().isoformat()
            }

            logger.info(f"Application generated. Tokens: {input_tokens}+{output_tokens}, Cost: ${cost_usd:.4f}")

            return application_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response as JSON: {str(e)}")
            raise ValueError(f"GPT 응답을 JSON으로 파싱할 수 없습니다: {str(e)}")

        except Exception as e:
            logger.error(f"Application generation failed: {str(e)}")
            raise

    def generate_multiple_applications(
        self,
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any],
        styles: List[str],
        target_length: int = 2500
    ) -> Dict[str, Dict[str, Any]]:
        """
        여러 스타일의 신청서 동시 생성 (Standard, Premium)

        Args:
            announcement_analysis: 공고 분석 결과
            company_analysis: 회사 분석 결과
            styles: 생성할 스타일 리스트 (예: ["data", "balanced", "story"])
            target_length: 목표 글자 수

        Returns:
            {
                "data": {...},
                "balanced": {...},
                "story": {...}
            }
        """
        try:
            logger.info(f"Generating {len(styles)} applications: {styles}")

            results = {}
            total_cost_usd = 0.0

            for style in styles:
                logger.info(f"Generating application for style: {style}")

                # 각 스타일별 생성
                app = self.generate_application(
                    announcement_analysis=announcement_analysis,
                    company_analysis=company_analysis,
                    style=style,
                    target_length=target_length
                )

                results[style] = app
                total_cost_usd += app["_metadata"]["cost_usd"]

            logger.info(f"All applications generated. Total cost: ${total_cost_usd:.4f}")

            return results

        except Exception as e:
            logger.error(f"Multiple application generation failed: {str(e)}")
            raise

    def generate_tier_applications(
        self,
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any],
        tier: str,
        recommended_style: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        티어별 신청서 생성

        Args:
            announcement_analysis: 공고 분석 결과
            company_analysis: 회사 분석 결과
            tier: "basic" | "standard" | "premium"
            recommended_style: AI 추천 스타일 (Standard, Premium에서 사용)

        Returns:
            티어별 생성 개수:
            - basic: 1개 (balanced)
            - standard: 3개 (recommended + 2개)
            - premium: 5개 (전체)
        """
        try:
            logger.info(f"Generating applications for tier: {tier}")

            if tier == "basic":
                # Basic: balanced 1개만
                styles = ["balanced"]

            elif tier == "standard":
                # Standard: 추천 스타일 + 2개 추가
                if not recommended_style:
                    recommended_style = "balanced"

                # 추천 스타일 제외하고 2개 선택
                all_styles = ["data", "story", "balanced", "aggressive", "conservative"]
                other_styles = [s for s in all_styles if s != recommended_style]
                selected = [recommended_style] + other_styles[:2]
                styles = selected

            elif tier == "premium":
                # Premium: 전체 5개
                styles = ["data", "story", "balanced", "aggressive", "conservative"]

            else:
                raise ValueError(f"Invalid tier: {tier}")

            logger.info(f"Generating {len(styles)} styles for {tier}: {styles}")

            # 다중 생성
            results = self.generate_multiple_applications(
                announcement_analysis=announcement_analysis,
                company_analysis=company_analysis,
                styles=styles
            )

            return results

        except Exception as e:
            logger.error(f"Tier application generation failed: {str(e)}")
            raise

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

    service = OpenAIService()

    # 예시 데이터 (Claude 분석 결과)
    announcement_analysis = {
        "자격요건": [
            {"항목": "업종", "내용": "제조업", "필수여부": True},
            {"항목": "매출액", "내용": "1,000억원 이하", "필수여부": True}
        ],
        "평가기준": [
            {"항목": "기술력", "배점": 40, "세부기준": ["특허", "인증", "R&D"]},
            {"항목": "사업성", "배점": 30, "세부기준": ["시장성", "경쟁력"]},
            {"항목": "실행력", "배점": 30, "세부기준": ["팀 구성", "예산"]}
        ]
    }

    company_analysis = {
        "강점분석": [
            {
                "강점": "특허 2건 보유",
                "대응평가기준": "기술력 > 특허/인증",
                "예상기여": "8-10점"
            }
        ],
        "최종전략": {
            "추천스타일": "data",
            "강조내용": ["특허", "정밀도"]
        }
    }

    # 단일 스타일 생성
    result = service.generate_application(
        announcement_analysis=announcement_analysis,
        company_analysis=company_analysis,
        style="balanced"
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 티어별 생성
    tier_result = service.generate_tier_applications(
        announcement_analysis=announcement_analysis,
        company_analysis=company_analysis,
        tier="standard",
        recommended_style="data"
    )

    print(f"\n생성된 스타일 개수: {len(tier_result)}")
    for style, app in tier_result.items():
        print(f"  - {style}: {app['statistics']['total_words']}자")
