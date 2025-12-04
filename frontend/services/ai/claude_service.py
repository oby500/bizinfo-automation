# services/ai/claude_service.py
"""
Claude Sonnet 4.5 AI 서비스 (Token Optimized)

담당 기능:
1. 공고문 분석 (Y → 자격요건, 평가기준, 작성전략)
2. 회사 분석 (Y + Z → 강점, 약점, 차별화)
3. 스타일 추천 (분석 결과 → 최적 스타일)

모델: claude-sonnet-4-5-20250929
가격: Input $3/1M tokens, Output $15/1M tokens
최적화: metadata.sections 기반 중요 섹션만 추출 (53.1% 토큰 절감)
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
        print("=" * 80)
        print("DEBUG: claude_service.analyze_announcement() called!")
        print("=" * 80)
        try:
            logger.info("Starting announcement analysis with Claude")

            # parsed_info 타입 확인 및 JSON 파싱
            if isinstance(parsed_info, str):
                logger.info("parsed_info is string, parsing JSON...")
                try:
                    parsed_info = json.loads(parsed_info)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse parsed_info as JSON: {e}")
                    parsed_info = {}

            logger.info(f"parsed_info type: {type(parsed_info)}, keys: {list(parsed_info.keys()) if isinstance(parsed_info, dict) else 'N/A'}")

            # parsed_info에서 metadata의 sections 추출
            metadata = parsed_info.get("metadata", {})
            sections = metadata.get("sections", [])

            # full_text를 줄 단위로 분리
            lines = full_text.split('\n') if full_text else []
            total_lines = len(lines)

            logger.info(f"Full text: {len(full_text)} chars, {total_lines} lines")

            # 중요 섹션 추출 (critical 및 high importance)
            important_sections = []
            extracted_texts = []

            for section in sections:
                importance = section.get("i", "")
                if importance in ["critical", "high"]:
                    line_range = section.get("l", "")
                    category = section.get("c", "")
                    keywords = section.get("k", [])

                    # 메타데이터 저장
                    important_sections.append({
                        "category": category,
                        "importance": importance,
                        "keywords": keywords,
                        "line_range": line_range
                    })

                    # line_range 파싱하여 실제 텍스트 추출 (예: "1-22" → lines[0:22])
                    if line_range and "-" in line_range:
                        try:
                            start, end = map(int, line_range.split("-"))
                            if 1 <= start <= total_lines and 1 <= end <= total_lines:
                                # 줄 번호는 1-based, Python 인덱스는 0-based
                                section_text = '\n'.join(lines[start-1:end])
                                extracted_texts.append(f"[{category or 'section'}]\n{section_text}")
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Failed to parse line range '{line_range}': {e}")
                            continue

            sections_str = json.dumps(important_sections, ensure_ascii=False, indent=2)

            # 추출된 텍스트 결합 (토큰 최적화)
            optimized_text = '\n\n'.join(extracted_texts) if extracted_texts else full_text[:5000]

            original_length = len(full_text)
            optimized_length = len(optimized_text)
            reduction_pct = (1 - optimized_length / original_length) * 100 if original_length > 0 else 0

            logger.info(f"Token optimization: {len(important_sections)} important sections extracted")
            logger.info(f"Text reduction: {original_length} → {optimized_length} chars ({reduction_pct:.1f}% reduced)")

            # 프롬프트 생성 (optimized_text 사용)
            prompt = ANALYZE_ANNOUNCEMENT_PROMPT.format(
                full_text=optimized_text,
                simple_summary=simple_summary or "(없음)",
                detailed_summary=detailed_summary or "(없음)",
                parsed_info_content_map=sections_str
            )

            logger.debug(f"Prompt length: {len(prompt)} characters")

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16384,  # 상세한 JSON 응답을 위해 증가
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

            # 토큰 사용량 먼저 로깅 (JSON 파싱 전에 확인)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = self._calculate_cost(input_tokens, output_tokens)
            cost_krw = int(cost_usd * 1400)  # 1 USD = 1400 KRW

            # 🔍 토큰 사용량 상세 로깅
            logger.info(f"=" * 80)
            logger.info(f"Claude Token Usage:")
            logger.info(f"  Input tokens:  {input_tokens:,}")
            logger.info(f"  Output tokens: {output_tokens:,} / {16384:,} (max)")
            logger.info(f"  Used: {output_tokens / 16384 * 100:.1f}%")
            logger.info(f"  Response length: {len(analysis_text):,} chars")
            logger.info(f"  Cost: ${cost_usd:.4f} (₩{cost_krw:,})")
            logger.info(f"=" * 80)

            # JSON 추출 (```json ... ``` 제거)
            analysis_json = self._extract_json(analysis_text)

            # ⭐ 필수 필드 검증 (과제목록, 필수정보)
            if "과제목록" not in analysis_json:
                logger.warning("⚠️ AI did not return '과제목록' field! Adding empty array.")
                analysis_json["과제목록"] = []

            if "필수정보" not in analysis_json:
                logger.warning("⚠️ AI did not return '필수정보' field! Adding default values.")
                analysis_json["필수정보"] = [
                    "회사명", "설립연도", "대표자명",
                    "주요 사업 내용", "매출액", "직원 수", "기술력 증빙",
                    "특허 보유 현황", "재무 상태", "사업 목적"
                ]
            elif len(analysis_json["필수정보"]) < 10:
                logger.warning(f"⚠️ AI returned only {len(analysis_json['필수정보'])} items in '필수정보' (expected ≥10)")

            # 과제목록 필드 타입 검증
            if not isinstance(analysis_json["과제목록"], list):
                logger.error(f"⚠️ '과제목록' is not a list! Type: {type(analysis_json['과제목록'])}")
                analysis_json["과제목록"] = []

            # 필수정보 필드 타입 검증
            if not isinstance(analysis_json["필수정보"], list):
                logger.error(f"⚠️ '필수정보' is not a list! Type: {type(analysis_json['필수정보'])}")
                analysis_json["필수정보"] = [
                    "회사명", "설립연도", "대표자명",
                    "주요 사업 내용", "매출액", "직원 수", "기술력 증빙",
                    "특허 보유 현황", "재무 상태", "사업 목적"
                ]

            # 과제목록 로깅
            logger.info(f"✅ 과제목록: {len(analysis_json['과제목록'])}개 과제 감지")
            if len(analysis_json["과제목록"]) > 0:
                for task in analysis_json["과제목록"]:
                    logger.info(f"   - 과제 {task.get('task_number')}: {task.get('task_name')}")

            # 필수정보 로깅
            logger.info(f"✅ 필수정보: {len(analysis_json['필수정보'])}개 항목")

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
                max_tokens=16384,  # 상세한 JSON 응답을 위해 증가 (공고분석과 동일)
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

    def _repair_truncated_json(self, json_str: str) -> str:
        """
        잘린(truncated) JSON을 복구하는 근본적 해결 로직

        Claude API가 max_tokens 한도에 도달하거나 응답이 중간에 잘렸을 때,
        Unterminated string, unclosed brackets 등의 오류를 복구합니다.

        Args:
            json_str: 잘린 JSON 문자열

        Returns:
            복구된 JSON 문자열
        """
        import re

        if not json_str:
            return json_str

        repaired = json_str.rstrip()

        # 1. 미완성 문자열 닫기 (따옴표 개수 체크)
        quote_count = 0
        in_escape = False
        last_quote_pos = -1

        for i, char in enumerate(repaired):
            if in_escape:
                in_escape = False
                continue
            if char == '\\':
                in_escape = True
                continue
            if char == '"':
                quote_count += 1
                last_quote_pos = i

        # 따옴표가 홀수면 문자열이 안 닫힌 것
        if quote_count % 2 == 1:
            # 이스케이프 안된 백슬래시로 끝나면 제거
            if repaired.endswith('\\') and not repaired.endswith('\\\\'):
                repaired = repaired[:-1]
            # 닫는 따옴표 추가
            repaired += '"'
            logger.info(f"[JSON복구] 미완성 문자열 닫기 완료 (위치: {last_quote_pos})")

        # 2. trailing comma 제거 (JSON에서 허용되지 않음)
        repaired = re.sub(r',\s*$', '', repaired)
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

        # 3. 미완성 키-값 쌍 정리
        # "key": 로 끝나면 null 추가
        repaired = re.sub(r'("[\w_]+"\s*:\s*)$', r'\1null', repaired)
        # "key": " 로 끝나면 빈 문자열로 닫기
        repaired = re.sub(r'("[\w_]+"\s*:\s*")$', r'\1"', repaired)

        # 4. 미완성 배열/객체 닫기
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')

        # 먼저 배열 닫기, 그 다음 객체 닫기
        if open_brackets > 0:
            repaired += ']' * open_brackets
            logger.info(f"[JSON복구] 미완성 배열 {open_brackets}개 닫기 완료")
        if open_braces > 0:
            repaired += '}' * open_braces
            logger.info(f"[JSON복구] 미완성 객체 {open_braces}개 닫기 완료")

        return repaired

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Claude 응답에서 JSON 추출 (강화된 에러 복구 로직)

        Args:
            text: Claude 응답 텍스트 (```json ... ``` 포함 가능)

        Returns:
            파싱된 JSON 딕셔너리
        """
        import re

        # ```json ... ``` 제거 (마지막 ``` 찾기 개선)
        if "```json" in text:
            start = text.find("```json") + 7
            # 마지막 ```를 찾아야 함
            end = text.rfind("```")
            if end > start:
                json_str = text[start:end].strip()
            else:
                json_str = text[start:].strip()
        elif "```" in text:
            # ```만 있는 경우
            start = text.find("```") + 3
            end = text.rfind("```")
            if end > start:
                json_str = text[start:end].strip()
            else:
                json_str = text[start:].strip()
        else:
            # 마크다운 코드 블록이 없는 경우
            json_str = text.strip()

        try:
            # 1단계: 기본 JSON 파싱 시도
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 파싱 1차 실패 (위치: {e.pos}): {str(e)}")

            # 에러 위치 주변 컨텍스트 로깅
            error_pos = e.pos if e.pos else 0
            context_start = max(0, error_pos - 100)
            context_end = min(len(json_str), error_pos + 100)
            logger.error(f"에러 위치 주변 컨텍스트:\n{json_str[context_start:context_end]}")

            try:
                # 1.5단계: 잘린 JSON 복구 시도 (Unterminated string 등)
                logger.info("[근본해결] 잘린(truncated) JSON 복구 시도 중...")
                repaired_json = self._repair_truncated_json(json_str)
                if repaired_json != json_str:
                    logger.info(f"[근본해결] JSON 복구 완료 - 원본: {len(json_str)}자, 복구: {len(repaired_json)}자")
                    try:
                        result = json.loads(repaired_json)
                        logger.info("[근본해결] 복구된 JSON 파싱 성공!")
                        return result
                    except json.JSONDecodeError as repair_error:
                        logger.warning(f"[근본해결] 복구된 JSON도 파싱 실패: {str(repair_error)}")
                        # 복구 시도 후에도 실패하면 기존 로직으로 진행
                        pass

                # 2단계: JSON 복구 시도 - 이스케이프 문제 해결
                logger.info("JSON 복구 시도 중 (멀티라인 문자열 이스케이프)...")
                fixed_json = json_str

                # 전략: JSON 키-값 쌍에서 값 부분의 문자열을 찾아서 이스케이프 처리
                # "key": "value" 패턴 매칭 (value는 멀티라인 가능)
                def fix_string_value(match):
                    key = match.group(1)  # 키 이름
                    value = match.group(2)  # 값 (따옴표 포함)

                    # 값이 문자열인 경우 (따옴표로 시작)
                    if value.startswith('"'):
                        # 문자열 내용 추출 (시작/끝 따옴표 제외)
                        try:
                            # 이미 올바르게 이스케이프된 경우 그대로 반환
                            json.loads(value)
                            return match.group(0)
                        except:
                            # 이스케이프 필요
                            string_content = value[1:-1] if value.endswith('"') else value[1:]

                            # 백슬래시를 먼저 이스케이프 (다른 이스케이프를 방해하지 않도록)
                            string_content = string_content.replace('\\', '\\\\')
                            # 그 다음 따옴표 이스케이프
                            string_content = string_content.replace('"', '\\"')
                            # 개행 문자 이스케이프
                            string_content = string_content.replace('\n', '\\n')
                            # 탭 문자 이스케이프
                            string_content = string_content.replace('\t', '\\t')
                            # 캐리지 리턴 이스케이프
                            string_content = string_content.replace('\r', '\\r')

                            return f'"{key}": "{string_content}"'

                    return match.group(0)

                # 패턴: "키": "값" (값은 멀티라인 가능, non-greedy)
                # re.DOTALL을 사용하여 .이 개행 문자도 매칭하도록
                fixed_json = re.sub(
                    r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*?"?)',
                    fix_string_value,
                    fixed_json,
                    flags=re.DOTALL
                )

                # trailing comma 제거 (JSON에서 허용되지 않음)
                fixed_json = re.sub(r',(\s*[}\]])', r'\1', fixed_json)

                return json.loads(fixed_json)

            except json.JSONDecodeError as e2:
                logger.warning(f"JSON 복구 2차 실패: {str(e2)}")

                try:
                    # 3단계: 주석 제거 시도
                    lines = []
                    for line in fixed_json.split('\n'):
                        # // 주석 제거
                        if '//' in line:
                            line = line[:line.index('//')]
                        lines.append(line)

                    cleaned_json = '\n'.join(lines)
                    return json.loads(cleaned_json)

                except Exception as e3:
                    # 최종 실패 - 상세한 에러 로깅
                    logger.error("=" * 80)
                    logger.error("JSON 파싱 최종 실패")
                    logger.error("=" * 80)
                    logger.error(f"원본 응답 길이: {len(text)} 문자")
                    logger.error(f"추출된 JSON 길이: {len(json_str)} 문자")
                    logger.error(f"원본 응답 (처음 500자):\n{text[:500]}")
                    logger.error(f"추출된 JSON (처음 1000자):\n{json_str[:1000]}")
                    logger.error(f"추출된 JSON (마지막 500자):\n{json_str[-500:]}")

                    # 최종 에러 발생
                    raise ValueError(
                        f"Claude 응답에서 JSON파싱 실패: {str(e)}\n"
                        f"에러 위치: line {e.lineno if hasattr(e, 'lineno') else 'N/A'}, "
                        f"column {e.colno if hasattr(e, 'colno') else 'N/A'}, "
                        f"char {e.pos if e.pos else 'N/A'}"
                    )

    def analyze_applications_for_upgrade(
        self,
        applications: list[Dict[str, Any]],
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Standard 티어: 3개 신청서 분석 → 1개 업그레이드 추천

        Args:
            applications: 3개 기본 신청서 (data, story, balanced)
            announcement_analysis: 공고 분석 결과
            company_analysis: 회사 분석 결과

        Returns:
            {
                "best_application_index": 1,
                "upgrade_strategy": {
                    "strengths": [...],
                    "weaknesses": [...],
                    "improvements": [...]
                },
                "upgrade_prompt": "...",
                "_metadata": {...}
            }
        """
        try:
            logger.info("Starting Standard tier application analysis for upgrade")

            # 신청서 요약
            apps_summary = []
            for i, app in enumerate(applications):
                apps_summary.append({
                    "index": i,
                    "style": app.get("style", "unknown"),
                    "content_preview": app.get("content", "")[:500]  # 첫 500자만
                })

            # 프롬프트 생성
            prompt = f"""당신은 정부 지원사업 신청서 전문가입니다.

아래 3개의 신청서를 분석하고, **가장 우수한 1개**를 선택한 뒤, 그것을 더욱 개선할 전략을 제시하세요.

## 공고 분석
{json.dumps(announcement_analysis, ensure_ascii=False, indent=2)}

## 회사 분석
{json.dumps(company_analysis, ensure_ascii=False, indent=2)}

## 3개 신청서
{json.dumps(apps_summary, ensure_ascii=False, indent=2)}

## 요구사항
1. 3개 신청서 중 **가장 우수한 1개**를 선택 (best_application_index: 0, 1, 2)
2. 선택한 신청서의 강점, 약점, 개선 방향을 분석
3. GPT-4o가 업그레이드 생성에 사용할 구체적인 프롬프트 작성

## 출력 형식 (JSON)
```json
{{
  "best_application_index": 1,
  "upgrade_strategy": {{
    "strengths": ["강점 1", "강점 2", "강점 3"],
    "weaknesses": ["약점 1", "약점 2"],
    "improvements": ["개선 방향 1", "개선 방향 2", "개선 방향 3"]
  }},
  "upgrade_prompt": "GPT-4o에게 전달할 구체적인 업그레이드 지침..."
}}
```
"""

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            # 응답 파싱
            analysis_text = response.content[0].text
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

            logger.info(f"Standard tier analysis completed. Tokens: {input_tokens}+{output_tokens}, Cost: ${cost_usd:.4f}")

            return analysis_json

        except Exception as e:
            logger.error(f"Standard tier analysis failed: {str(e)}")
            raise

    def analyze_applications_for_premium(
        self,
        applications: list[Dict[str, Any]],
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Premium 티어: 5개 신청서 분석 → 2개 프리미엄 A/B형 추천

        Args:
            applications: 5개 기본 신청서 (data, story, balanced, aggressive, conservative)
            announcement_analysis: 공고 분석 결과
            company_analysis: 회사 분석 결과

        Returns:
            {
                "premium_a_strategy": {
                    "target": "공격적/혁신적 (스타트업용)",
                    "base_application_index": 3,
                    "key_points": [...],
                    "upgrade_prompt": "..."
                },
                "premium_b_strategy": {
                    "target": "안정적/보수적 (전통기업용)",
                    "base_application_index": 4,
                    "key_points": [...],
                    "upgrade_prompt": "..."
                },
                "_metadata": {...}
            }
        """
        try:
            logger.info("Starting Premium tier application analysis for A/B premium")

            # 신청서 요약
            apps_summary = []
            for i, app in enumerate(applications):
                apps_summary.append({
                    "index": i,
                    "style": app.get("style", "unknown"),
                    "content_preview": app.get("content", "")[:500]
                })

            # 프롬프트 생성
            prompt = f"""당신은 정부 지원사업 신청서 전문가입니다.

아래 5개의 신청서를 분석하고, **2개의 프리미엄 전략**을 제시하세요:
- **Premium A**: 공격적/혁신적 (스타트업, 성장기업용)
- **Premium B**: 안정적/보수적 (전통기업, 안정성 중시용)

## 공고 분석
{json.dumps(announcement_analysis, ensure_ascii=False, indent=2)}

## 회사 분석
{json.dumps(company_analysis, ensure_ascii=False, indent=2)}

## 5개 신청서
{json.dumps(apps_summary, ensure_ascii=False, indent=2)}

## 요구사항
1. Premium A: 가장 공격적이고 혁신적인 신청서 선택 및 개선 전략
2. Premium B: 가장 안정적이고 보수적인 신청서 선택 및 개선 전략
3. 각각에 대해 GPT-4o가 생성에 사용할 간결한 전략 지침 작성

## 출력 형식 (JSON)
**중요**: upgrade_prompt는 200-300자 이내로 핵심 전략만 간결하게 작성하세요.

```json
{{
  "premium_a_strategy": {{
    "target": "공격적/혁신적 (스타트업용)",
    "base_application_index": 3,
    "key_points": ["핵심 전략 1", "핵심 전략 2", "핵심 전략 3"],
    "upgrade_prompt": "GPT-4o 생성 지침: 혁신성 강조, 성장 스토리텔링, 구체적 수치 제시, 미래 비전 명확화 (200-300자)"
  }},
  "premium_b_strategy": {{
    "target": "안정적/보수적 (전통기업용)",
    "base_application_index": 4,
    "key_points": ["핵심 전략 1", "핵심 전략 2", "핵심 전략 3"],
    "upgrade_prompt": "GPT-4o 생성 지침: 안정성 강조, 체계적 접근, 리스크 관리, 실행 가능성 (200-300자)"
  }}
}}
```
"""

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            # 응답 파싱
            analysis_text = response.content[0].text
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

            logger.info(f"Premium tier analysis completed. Tokens: {input_tokens}+{output_tokens}, Cost: ${cost_usd:.4f}")

            return analysis_json

        except Exception as e:
            logger.error(f"Premium tier analysis failed: {str(e)}")
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

    def generate_application(
        self,
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any],
        style: str = "balanced",
        target_length: int = 2500,
        tier: str = "standard"
    ) -> Dict[str, Any]:
        """
        Claude로 신청서 생성 (GPT-4o와 동일한 인터페이스)

        Args:
            announcement_analysis: 공고 분석 결과
            company_analysis: 회사 분석 결과
            style: 작성 스타일 (data, story, balanced, aggressive, conservative)
            target_length: 목표 글자 수 (기본 2500자)
            tier: 결제 티어 (basic, standard, premium)

        Returns:
            {
                "content": "신청서 전체 텍스트",
                "sections": [...],
                "statistics": {...},
                "_metadata": {...}
            }
        """
        try:
            logger.info(f"[Claude] Starting application generation (style: {style}, tier: {tier})")

            # 프롬프트 임포트
            from utils.prompts import STYLE_GUIDES, GENERATE_APPLICATION_PROMPT_STANDARD

            # 스타일 가이드 가져오기
            if style not in STYLE_GUIDES:
                raise ValueError(f"Invalid style: {style}")

            style_guide = STYLE_GUIDES[style]

            # JSON 직렬화
            announcement_json = json.dumps(announcement_analysis, ensure_ascii=False, indent=2)
            company_json = json.dumps(company_analysis, ensure_ascii=False, indent=2)
            style_guide_json = json.dumps(style_guide, ensure_ascii=False, indent=2)

            # 프롬프트 구성
            prompt = GENERATE_APPLICATION_PROMPT_STANDARD.format(
                announcement_analysis=announcement_json,
                company_analysis=company_json,
                style=style,
                style_guide=style_guide_json
            )

            # 시스템 프롬프트 (GPT-4o와 동일)
            system_prompt = """당신은 정부지원사업 선정률 95%를 자랑하는 베테랑 컨설턴트입니다.

## 핵심 인식

⚠️ **신청서 = PPT 발표**입니다. Q&A처럼 객관식 답을 주는게 아닙니다!
"우리는 이런 회사다"라는 것을 **발표**하듯이 풍부하게 설명해야 합니다.

⚠️ **심사위원 = 제반 지식이 없는 사람**입니다!
- 이 업계를 잘 모를 수 있습니다
- 이 기술이 왜 대단한지 모릅니다
- 이 회사가 왜 특별한지 모릅니다
→ **처음 접하는 사람에게 설명하듯** 자세하게 작성하세요!

## 작성 원칙
1. **풍성한 설명 = 높은 점수**: 짧은 글은 "준비가 부족하다"는 인상을 줍니다.
2. **배경 설명 필수**: "왜" 이것이 대단한지, "어떻게" 이것이 가능했는지 맥락을 제공하세요.
3. **스토리텔링**: 딱딱한 팩트 나열이 아닌, 성장 여정과 비전을 그려주세요.
4. **구체적 근거**: 숫자, 날짜, 특허번호, 고객사명 등으로 신뢰를 더하세요.

## 나쁜 예 (탈락 - Q&A식 답변)
> "당사는 특허 3건을 보유하고 있습니다. 박사급 인력 5명입니다."

## 좋은 예 (선정 - PPT 발표)
> "2019년 창업 초기, 저희에게는 오직 '데이터로 세상을 바꾸겠다'는 꿈만 있었습니다. AI 데이터 분석 시장은 당시 연간 3조원 규모였지만, 대부분 해외 솔루션이 독점하고 있었습니다. 우리는 이 시장에서 한국 기업의 경쟁력을 증명하고 싶었습니다.
>
> 5천만원의 작은 자본금으로 시작한 여정이 5년 만에 매출 15억원을 달성하기까지, KAIST AI 대학원 출신 5명의 박사급 연구원들이 밤을 새워가며 개발한 3건의 핵심 특허가 있었습니다."

**기억하세요**: 심사위원은 이 글을 처음 읽습니다. 풍부하게 설명해야 높은 점수를 받습니다!"""

            logger.info(f"[Claude] Prompt length: {len(prompt)} characters")

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16384,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # 응답 파싱
            application_text = response.content[0].text

            # 토큰 사용량 계산
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = self._calculate_cost(input_tokens, output_tokens)
            cost_krw = int(cost_usd * 1400)

            logger.info(f"[Claude] Response length: {len(application_text)} characters")
            logger.info(f"[Claude] Tokens: {input_tokens}+{output_tokens}, Cost: ${cost_usd:.4f} (₩{cost_krw})")

            # JSON 추출
            application_json = self._extract_json(application_text)

            # 통계 계산
            sections = application_json.get("sections", [])
            total_chars = 0
            for section in sections:
                subsections = section.get("subsections", [])
                if subsections:
                    for sub in subsections:
                        total_chars += len(sub.get("content", ""))
                else:
                    total_chars += len(section.get("content", ""))

            # 메타데이터 추가
            application_json["_metadata"] = {
                "model": self.model,
                "style": style,
                "tier": tier,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 4),
                "cost_krw": cost_krw,
                "total_chars": total_chars,
                "generated_at": datetime.now().isoformat()
            }

            logger.info(f"[Claude] Application generated: {total_chars} chars, {len(sections)} sections")

            return application_json

        except Exception as e:
            logger.error(f"[Claude] Application generation failed: {str(e)}")
            raise

    def generate_profile_questions(
        self,
        announcement_id: str,
        announcement_source: str,
        task_info: Optional[Dict[str, Any]] = None,
        required_info_list: Optional[list] = None
    ) -> list:
        """
        회사 정보 수집을 위한 AI 질문 생성 (과제 정보 반영)

        Args:
            announcement_id: 공고 ID
            announcement_source: 공고 출처
            task_info: 선택한 과제 정보 (optional)
            required_info_list: 필수 정보 목록 (optional)

        Returns:
            질문 목록
        """
        try:
            logger.info("[generate_profile_questions] 질문 생성 시작")

            # 시스템 프롬프트 구성
            system_prompt = "당신은 회사 정보를 수집하는 전문 인터뷰어입니다.\n\n"

            if task_info:
                system_prompt += f"**선택한 과제**: {task_info.get('task_name')} (과제 {task_info.get('task_number')})\n"
                system_prompt += f"**과제 설명**: {task_info.get('description', 'N/A')}\n\n"

                if task_info.get('requirements'):
                    system_prompt += "**과제 요구사항**:\n"
                    for req in task_info.get('requirements', {}).values():
                        system_prompt += f"- {req}\n"
                    system_prompt += "\n"

            if required_info_list and len(required_info_list) > 0:
                system_prompt += "**반드시 수집해야 할 정보**:\n"
                for info in required_info_list:
                    system_prompt += f"- {info}\n"
                system_prompt += "\n"

            system_prompt += """
위 정보를 바탕으로 사용자에게 필요한 회사 정보를 수집하기 위한 질문 5-7개를 생성하세요.

**절대 금지 사항:**
- 사업자등록증, 법인등기부등본, 재무제표 등 서류 제출을 요청하지 마세요
- 사업자등록번호를 묻지 마세요
- 우리는 신청서 "내용"만 작성합니다. 서류는 사용자가 직접 제출합니다.

**올바른 질문 예시:**
- "회사명을 알려주세요" (O)
- "주요 사업 분야는 무엇인가요?" (O)
- "이 사업에 지원하시는 목적이나 기대 효과는 무엇인가요?" (O)

**잘못된 질문 예시:**
- "사업자등록증을 제출해주세요" (X)
- "법인등기부등본을 준비해주세요" (X)
- "사업자등록번호가 어떻게 되나요?" (X)

질문은 다음 형식의 JSON 배열로 반환해주세요:
[
  {"question": "회사명을 알려주세요.", "category": "기본정보"},
  {"question": "주요 사업 분야는 무엇인가요?", "category": "사업내용"}
]
"""

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": "질문을 생성해주세요."}
                ]
            )

            # 응답 파싱
            response_text = response.content[0].text
            questions = self._extract_json(response_text)

            if isinstance(questions, dict):
                questions = [questions]  # dict면 list로 변환
            elif not isinstance(questions, list):
                questions = []  # 파싱 실패 시 빈 리스트

            logger.info(f"[generate_profile_questions] 질문 {len(questions)}개 생성 완료")
            return questions

        except Exception as e:
            logger.error(f"[generate_profile_questions] 오류 발생: {str(e)}")
            # 오류 시 기본 질문 반환
            return [
                {"question": "회사명을 알려주세요.", "category": "기본정보"},
                {"question": "주요 사업 분야는 무엇인가요?", "category": "사업내용"},
                {"question": "회사의 강점은 무엇인가요?", "category": "경쟁력"}
            ]

    def profile_chat(
        self,
        announcement_id: str,
        announcement_source: str,
        user_message: str,
        conversation_history: list,
        task_info: Optional[Dict[str, Any]] = None,
        required_info_list: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        회사 정보 수집 대화형 챗봇 (과제 정보 반영)

        Args:
            announcement_id: 공고 ID
            announcement_source: 공고 출처
            user_message: 사용자 메시지
            conversation_history: 대화 기록
            task_info: 선택한 과제 정보 (optional)
            required_info_list: 필수 정보 목록 (optional)

        Returns:
            Dict with ai_response, completion_percentage, extracted_data
        """
        try:
            logger.info("[profile_chat] 챗봇 응답 생성 시작")

            # 시스템 프롬프트 구성
            system_prompt = """당신은 정부지원사업 신청서 작성을 돕는 친절한 AI 어시스턴트입니다.

**중요 원칙:**
1. 사업자등록증, 법인등기부등본 등 서류 제출은 요청하지 마세요. 우리는 신청서 "내용"만 작성합니다.
2. 사용자의 답변에서 관련 정보를 추출하고, 이미 답변한 내용은 다시 묻지 마세요.
3. 한 번에 1-2개의 질문만 하세요. 너무 많은 질문은 사용자를 압도합니다.
4. 사용자가 제공한 정보는 인정하고 감사를 표한 후 다음 질문으로 넘어가세요.
5. 완료 판단: 기업명, 주요사업, 지원동기, 기대효과 등 핵심 정보가 수집되면 완료로 간주하세요.

"""

            if task_info:
                system_prompt += f"**현재 신청 중인 과제:**\n"
                system_prompt += f"- 과제번호: {task_info.get('task_number')}\n"
                system_prompt += f"- 과제명: {task_info.get('task_name')}\n"
                if task_info.get('description'):
                    system_prompt += f"- 과제 설명: {task_info.get('description')}\n"
                system_prompt += "\n"

            if required_info_list and len(required_info_list) > 0:
                system_prompt += "**수집해야 할 핵심 정보** (서류 제출 아님, 텍스트 정보만):\n"
                for info in required_info_list:
                    system_prompt += f"- {info}\n"
                system_prompt += "\n"

            system_prompt += """
**응답 방식:**
- 사용자 답변에서 유용한 정보를 파악하고 다음 질문으로 자연스럽게 이어가세요.
- 5-7번의 질문-답변으로 충분한 정보를 수집하세요.
- 핵심 정보(기업명, 주요사업, 지원동기, 기대효과)가 수집되면 "정보 수집이 완료되었습니다"라고 명확히 알려주세요.
"""

            # 대화 기록을 Claude 메시지 형식으로 변환
            messages = []
            last_role = None
            for msg in conversation_history:
                role = "user" if msg.get("role") == "user" else "assistant"
                # content 또는 message 필드 사용 (프론트엔드 호환성)
                content = msg.get("content") or msg.get("message") or ""

                # 빈 content는 Claude API에서 에러 발생하므로 스킵
                if not content or not content.strip():
                    continue

                # 같은 role이 연속되면 메시지 병합 (Claude API 요구사항)
                if role == last_role and messages:
                    messages[-1]["content"] += "\n" + content.strip()
                else:
                    messages.append({"role": role, "content": content.strip()})
                    last_role = role

            # 현재 사용자 메시지 추가 (빈 문자열 체크)
            current_user_msg = user_message.strip() if user_message else "계속 진행해주세요."

            # 마지막 메시지가 user이면 병합, 아니면 새로 추가
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += "\n" + current_user_msg
            else:
                messages.append({"role": "user", "content": current_user_msg})

            # 메시지가 비어있으면 기본 메시지 추가 (첫 대화 시작)
            if not messages:
                messages.append({"role": "user", "content": "안녕하세요. 신청서 작성을 시작하겠습니다."})

            # 로그로 메시지 확인
            logger.info(f"[profile_chat] messages count: {len(messages)}, roles: {[m['role'] for m in messages]}")

            # Claude API 호출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=system_prompt,
                messages=messages
            )

            ai_response = response.content[0].text

            logger.info(f"[profile_chat] 응답 생성 완료: {ai_response[:100]}...")
            
            # 대화 횟수 기반 진행률 계산 (최대 5회 대화로 60% 달성)
            user_message_count = len([m for m in conversation_history if m.get('role') == 'user']) + 1
            # 각 대화당 12%씩 증가 (5회 = 60%)
            completion_percentage = min(user_message_count * 12, 60)
            
            # AI 응답에 "정보 수집이 완료" 또는 "충분한 정보"가 포함되면 바로 60% 이상으로
            if any(kw in ai_response for kw in ["정보 수집이 완료", "충분한 정보를 수집", "이제 신청서 작성"]):
                completion_percentage = max(completion_percentage, 65)
            
            logger.info(f"[profile_chat] completion_percentage: {completion_percentage}%")
            
            return {
                "ai_response": ai_response,
                "completion_percentage": completion_percentage,
                "extracted_data": {}
            }

        except Exception as e:
            logger.error(f"[profile_chat] 오류 발생: {str(e)}")
            return {
                "ai_response": "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.",
                "completion_percentage": 0,
                "extracted_data": {}
            }

    def generate_applications_by_tier(
        self,
        announcement_analysis: Dict[str, Any],
        company_analysis: Dict[str, Any],
        tier: str = "standard",
        style_recommendation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        티어별로 신청서 생성 (다중 스타일) - AI 라우터 기반

        티어별 제공 글 수:
        - BASIC (4,900원): 1개 (story 고정)
        - STANDARD (8,000원): 3개 (베이스 5개 중 AI 라우터 선택)
        - PREMIUM (15,000원): 5개 (베이스 3개 + 조합 2개, AI 라우터 선택)

        베이스 스타일 (5개): story, data, aggressive, conservative, professional
        조합 스타일 (4개): balanced, strategic, trusted, expert

        Args:
            announcement_analysis: 공고 분석 결과 (스타일추천 포함)
            company_analysis: 회사 분석 결과
            tier: 결제 티어 (basic, standard, premium)
            style_recommendation: AI 라우터 추천 결과 (optional, announcement_analysis에서 추출)

        Returns:
            {
                "applications": [
                    {"style": "data", "content": {...}, "is_recommended": True, "rank": 1},
                    {"style": "professional", "content": {...}, "is_recommended": False, "rank": 2},
                    ...
                ],
                "tier": "standard",
                "total_count": 3,
                "base_styles": ["data", "professional", "story"],
                "combination_styles": [],
                "recommended_style": "data",
                "total_cost_krw": 12000,
                "_metadata": {...}
            }
        """
        from utils.prompts import TIER_STYLES, STYLE_INFO, BASE_STYLES, COMBINATION_STYLES

        try:
            tier_config = TIER_STYLES.get(tier, TIER_STYLES["standard"])

            # AI 라우터 추천 결과 가져오기
            if style_recommendation is None:
                style_recommendation = announcement_analysis.get("스타일추천", {})

            # 티어별 스타일 선택
            selected_base_styles = []
            selected_combination_styles = []

            if tier_config.get("router_enabled", False):
                # AI 라우터 사용: 추천 순위에 따라 선택
                base_rec = style_recommendation.get("베이스추천", {})
                comb_rec = style_recommendation.get("조합추천", {})

                # 베이스 스타일 선택 (추천 순위대로)
                base_count = tier_config.get("base_count", 3)
                for rank in ["1순위", "2순위", "3순위", "4순위", "5순위"]:
                    if len(selected_base_styles) >= base_count:
                        break
                    rec = base_rec.get(rank, {})
                    style = rec.get("스타일")
                    if style and style in BASE_STYLES:
                        selected_base_styles.append(style)

                # 추천이 부족하면 기본 순서로 채움
                for style in BASE_STYLES:
                    if len(selected_base_styles) >= base_count:
                        break
                    if style not in selected_base_styles:
                        selected_base_styles.append(style)

                # 조합 스타일 선택 (프리미엄만)
                comb_count = tier_config.get("combination_count", 0)
                for rank in ["1순위", "2순위", "3순위", "4순위"]:
                    if len(selected_combination_styles) >= comb_count:
                        break
                    rec = comb_rec.get(rank, {})
                    style = rec.get("스타일")
                    if style and style in COMBINATION_STYLES:
                        selected_combination_styles.append(style)

                # 추천이 부족하면 기본 순서로 채움
                for style in COMBINATION_STYLES:
                    if len(selected_combination_styles) >= comb_count:
                        break
                    if style not in selected_combination_styles:
                        selected_combination_styles.append(style)
            else:
                # 라우터 미사용 (BASIC): 고정 스타일
                selected_base_styles = tier_config.get("base_styles", ["story"])[:tier_config.get("base_count", 1)]

            # 최종 생성할 스타일 리스트
            styles_to_generate = selected_base_styles + selected_combination_styles

            logger.info(f"[Claude] Tier: {tier}, Router: {tier_config.get('router_enabled', False)}")
            logger.info(f"[Claude] Base styles: {selected_base_styles}")
            logger.info(f"[Claude] Combination styles: {selected_combination_styles}")
            logger.info(f"[Claude] Total styles to generate: {len(styles_to_generate)}")

            applications = []
            total_input_tokens = 0
            total_output_tokens = 0
            total_cost_usd = 0.0

            # 1순위 스타일 (추천 스타일)
            top_recommended_style = styles_to_generate[0] if styles_to_generate else None

            for rank, style in enumerate(styles_to_generate, 1):
                logger.info(f"[Claude] Generating style {rank}/{len(styles_to_generate)}: {style}")

                try:
                    result = self.generate_application(
                        announcement_analysis=announcement_analysis,
                        company_analysis=company_analysis,
                        style=style,
                        tier=tier
                    )

                    # 스타일 정보 추가
                    style_info = STYLE_INFO.get(style, {})
                    is_recommended = (rank == 1)  # 1순위만 추천
                    is_base_style = style in selected_base_styles
                    is_combination_style = style in selected_combination_styles

                    applications.append({
                        "style": style,
                        "style_name": style_info.get("name", style),
                        "style_icon": style_info.get("icon", "📄"),
                        "style_description": style_info.get("short_desc", ""),
                        "style_type": "base" if is_base_style else "combination",
                        "rank": rank,
                        "content": result,
                        "is_recommended": is_recommended
                    })

                    # 토큰/비용 누적
                    meta = result.get("_metadata", {})
                    total_input_tokens += meta.get("input_tokens", 0)
                    total_output_tokens += meta.get("output_tokens", 0)
                    total_cost_usd += meta.get("cost_usd", 0)

                except Exception as style_error:
                    logger.error(f"[Claude] Failed to generate style '{style}': {str(style_error)}")
                    applications.append({
                        "style": style,
                        "style_name": STYLE_INFO.get(style, {}).get("name", style),
                        "style_type": "base" if style in selected_base_styles else "combination",
                        "rank": rank,
                        "error": str(style_error),
                        "is_recommended": False
                    })

            # 첫 번째 스타일 생성 실패 시 다음 성공한 스타일을 추천으로 설정
            if applications and "error" in applications[0]:
                for app in applications:
                    if "error" not in app:
                        app["is_recommended"] = True
                        top_recommended_style = app["style"]
                        break

            return {
                "applications": applications,
                "tier": tier,
                "tier_description": tier_config.get("description", ""),
                "total_count": len(styles_to_generate),
                "success_count": len([a for a in applications if "error" not in a]),
                "base_styles": selected_base_styles,
                "combination_styles": selected_combination_styles,
                "base_count": len(selected_base_styles),
                "combination_count": len(selected_combination_styles),
                "recommended_style": top_recommended_style,
                "router_enabled": tier_config.get("router_enabled", False),
                "_metadata": {
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_cost_usd": round(total_cost_usd, 4),
                    "total_cost_krw": int(total_cost_usd * 1400),
                    "generated_at": datetime.now().isoformat(),
                    "style_recommendation_used": bool(style_recommendation)
                }
            }

        except Exception as e:
            logger.error(f"[Claude] generate_applications_by_tier failed: {str(e)}")
            raise


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
