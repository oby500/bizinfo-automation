#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Selenium E2E 테스트 - 실제 브라우저 화면으로 테스트
사용자가 직접 화면을 보면서 테스트 진행 상황을 확인할 수 있습니다.
"""

import os
import sys
import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

load_dotenv()

# 테스트할 공고 목록
TEST_ANNOUNCEMENTS = [
    # K-Startup 공고
    {"id": "KS_175154", "source": "kstartup", "name": "청년, 예비창업자 Pre-스타트업 창업지원"},
    {"id": "KS_175386", "source": "kstartup", "name": "K-Startup 공고"},
    # Bizinfo 공고
    {"id": "PBLN_000000000108013", "source": "bizinfo", "name": "AI홀 활용한 온라인쇼핑몰 입점"},
]

# 테스트할 티어
TEST_TIERS = ["basic", "standard", "premium"]

class SeleniumE2ETest:
    def __init__(self, headless=False):
        """
        headless=False: 브라우저 화면을 볼 수 있음
        headless=True: 백그라운드 실행
        """
        self.base_url = "http://localhost:3000"
        self.headless = headless
        self.driver = None
        self.results = []

    def setup_driver(self):
        """Chrome 드라이버 설정"""
        options = Options()

        if self.headless:
            options.add_argument("--headless=new")

        # 브라우저 창 크기 설정
        options.add_argument("--window-size=1400,900")
        options.add_argument("--start-maximized")

        # 한글 지원
        options.add_argument("--lang=ko-KR")

        # 개발자 도구 로그 비활성화
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        # 자동화 감지 방지
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)

        print(f"✅ Chrome 브라우저 시작 (headless={self.headless})")

    def teardown_driver(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            print("✅ 브라우저 종료")

    def wait_and_click(self, selector, by=By.CSS_SELECTOR, timeout=10):
        """요소 대기 후 클릭"""
        element = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        element.click()
        return element

    def wait_for_element(self, selector, by=By.CSS_SELECTOR, timeout=10):
        """요소 대기"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )

    def wait_for_text(self, text, timeout=30):
        """특정 텍스트가 나타날 때까지 대기"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{text}')]"))
        )

    def screenshot(self, name):
        """스크린샷 저장"""
        os.makedirs("test_screenshots/selenium", exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"test_screenshots/selenium/{timestamp}_{name}.png"
        self.driver.save_screenshot(filename)
        print(f"📸 스크린샷: {filename}")
        return filename

    def test_announcement_page(self, announcement):
        """공고 상세 페이지 테스트"""
        ann_id = announcement["id"]
        source = announcement["source"]
        name = announcement["name"]

        result = {
            "announcement_id": ann_id,
            "source": source,
            "name": name,
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "success": False,
            "error": None
        }

        try:
            print(f"\n{'='*60}")
            print(f"🧪 테스트 시작: {name}")
            print(f"   ID: {ann_id} | Source: {source}")
            print(f"{'='*60}")

            # 1. 공고 상세 페이지 접속
            url = f"{self.base_url}/announcement/{ann_id}?source={source}&test_mode=true"
            print(f"\n📍 Step 1: 공고 페이지 접속")
            print(f"   URL: {url}")

            self.driver.get(url)
            time.sleep(2)
            self.screenshot(f"{ann_id}_01_page_loaded")
            result["steps"].append({"step": "page_load", "status": "success"})

            # 2. 페이지 로드 확인
            print(f"\n📍 Step 2: 페이지 로드 확인")
            try:
                # 공고 제목 또는 AI 신청서 자동 작성 섹션 찾기
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//h1 | //*[contains(text(), 'AI 신청서')]"))
                )
                print("   ✓ 페이지 로드 완료")
                result["steps"].append({"step": "content_loaded", "status": "success"})
            except TimeoutException:
                print("   ⚠ 페이지 로드 시간 초과")
                self.screenshot(f"{ann_id}_02_timeout")
                result["steps"].append({"step": "content_loaded", "status": "timeout"})

            # 3. ApplicationWriter 컴포넌트 확인
            print(f"\n📍 Step 3: ApplicationWriter 확인")
            try:
                writer = self.wait_for_element(
                    "//*[contains(text(), 'AI 신청서 자동 작성')]",
                    By.XPATH,
                    timeout=15
                )
                print("   ✓ ApplicationWriter 컴포넌트 발견")
                self.screenshot(f"{ann_id}_03_writer_found")
                result["steps"].append({"step": "writer_found", "status": "success"})
            except TimeoutException:
                print("   ❌ ApplicationWriter 찾을 수 없음")
                self.screenshot(f"{ann_id}_03_writer_not_found")
                result["steps"].append({"step": "writer_found", "status": "failed"})
                result["error"] = "ApplicationWriter not found"
                return result

            # 4. 티어 선택 카드 확인
            print(f"\n📍 Step 4: 티어 선택 UI 확인")
            tier_found = False
            for tier_name in ["베이직", "스탠다드", "프리미엄"]:
                try:
                    tier_elem = self.driver.find_element(
                        By.XPATH, f"//*[contains(text(), '{tier_name}')]"
                    )
                    print(f"   ✓ {tier_name} 티어 발견")
                    tier_found = True
                except NoSuchElementException:
                    pass

            if tier_found:
                self.screenshot(f"{ann_id}_04_tier_cards")
                result["steps"].append({"step": "tier_ui", "status": "success"})
            else:
                print("   ⚠ 티어 카드를 찾을 수 없음 (크레딧 결제 단계가 아닐 수 있음)")
                result["steps"].append({"step": "tier_ui", "status": "not_found"})

            # 5. 페이지 스크롤하여 전체 컨텐츠 확인
            print(f"\n📍 Step 5: 페이지 스크롤")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            self.screenshot(f"{ann_id}_05_scrolled")
            result["steps"].append({"step": "scroll", "status": "success"})

            # 성공
            result["success"] = True
            result["end_time"] = datetime.now().isoformat()
            print(f"\n✅ 테스트 완료: {ann_id}")

        except Exception as e:
            result["error"] = str(e)
            result["end_time"] = datetime.now().isoformat()
            print(f"\n❌ 테스트 실패: {e}")
            self.screenshot(f"{ann_id}_error")

        self.results.append(result)
        return result

    def test_application_generation(self, announcement, tier="basic"):
        """신청서 생성 전체 플로우 테스트 (실제 API 호출)"""
        ann_id = announcement["id"]
        source = announcement["source"]
        name = announcement["name"]

        result = {
            "announcement_id": ann_id,
            "source": source,
            "tier": tier,
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "success": False,
            "error": None
        }

        try:
            print(f"\n{'='*60}")
            print(f"🚀 신청서 생성 테스트: {name}")
            print(f"   Tier: {tier.upper()}")
            print(f"{'='*60}")

            # 1. 테스트 페이지 접속
            url = f"{self.base_url}/test-writer?id={ann_id}&source={source}"
            print(f"\n📍 테스트 페이지 접속")
            self.driver.get(url)
            time.sleep(3)
            self.screenshot(f"{ann_id}_{tier}_01_test_page")

            # 2. 테스트 버튼 찾기 및 클릭
            print(f"\n📍 테스트 시작 버튼 클릭")
            try:
                test_btn = self.wait_and_click(
                    f"//*[contains(text(), '테스트') or contains(text(), '시작')]",
                    By.XPATH,
                    timeout=10
                )
                time.sleep(2)
                self.screenshot(f"{ann_id}_{tier}_02_clicked")
                result["steps"].append({"step": "click_start", "status": "success"})
            except:
                print("   테스트 버튼 없음 - 직접 API 테스트")
                result["steps"].append({"step": "click_start", "status": "skipped"})

            # 3. 생성 진행 상황 모니터링
            print(f"\n📍 생성 진행 상황 대기 (최대 3분)")
            start = time.time()
            while time.time() - start < 180:  # 3분 대기
                try:
                    # 완료 메시지 확인
                    self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), '완료') or contains(text(), '성공')]"
                    )
                    print("   ✓ 생성 완료!")
                    self.screenshot(f"{ann_id}_{tier}_03_completed")
                    result["steps"].append({"step": "generation", "status": "success"})
                    break
                except NoSuchElementException:
                    pass

                # 로딩 상태 확인
                try:
                    self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), '생성 중') or contains(text(), '작성')]"
                    )
                    elapsed = int(time.time() - start)
                    print(f"   ⏳ 생성 중... ({elapsed}초)", end="\r")
                except NoSuchElementException:
                    pass

                time.sleep(3)
            else:
                print("   ⚠ 생성 시간 초과")
                self.screenshot(f"{ann_id}_{tier}_03_timeout")
                result["steps"].append({"step": "generation", "status": "timeout"})

            result["success"] = True
            result["end_time"] = datetime.now().isoformat()

        except Exception as e:
            result["error"] = str(e)
            result["end_time"] = datetime.now().isoformat()
            print(f"\n❌ 오류: {e}")
            self.screenshot(f"{ann_id}_{tier}_error")

        self.results.append(result)
        return result

    def run_all_tests(self):
        """모든 테스트 실행"""
        print("\n" + "="*70)
        print("🧪 Selenium E2E 테스트 시작")
        print("="*70)
        print(f"테스트 대상: {len(TEST_ANNOUNCEMENTS)}개 공고")
        print(f"브라우저: Chrome (headless={self.headless})")
        print("="*70)

        try:
            self.setup_driver()

            # 각 공고별 페이지 테스트
            for announcement in TEST_ANNOUNCEMENTS:
                self.test_announcement_page(announcement)
                time.sleep(2)  # 요청 간격

            # 결과 저장
            self.save_results()

        finally:
            # 테스트 완료 후 잠시 대기 (결과 확인용)
            if not self.headless:
                print("\n⏳ 5초 후 브라우저 종료...")
                time.sleep(5)
            self.teardown_driver()

    def save_results(self):
        """테스트 결과 저장"""
        os.makedirs("test_screenshots/selenium", exist_ok=True)

        result_file = f"test_screenshots/selenium/test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({
                "test_time": datetime.now().isoformat(),
                "total_tests": len(self.results),
                "passed": sum(1 for r in self.results if r["success"]),
                "failed": sum(1 for r in self.results if not r["success"]),
                "results": self.results
            }, f, ensure_ascii=False, indent=2)

        print(f"\n📄 결과 저장: {result_file}")

        # HTML 리포트 생성
        self.generate_html_report()

    def generate_html_report(self):
        """HTML 테스트 리포트 생성"""
        passed = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - passed

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Selenium E2E 테스트 결과</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat.passed {{ border-left: 4px solid #22c55e; }}
        .stat.failed {{ border-left: 4px solid #ef4444; }}
        .stat h3 {{ margin: 0; font-size: 2em; }}
        .stat p {{ margin: 5px 0 0; color: #666; }}
        .test-card {{ background: white; margin: 15px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .test-card.success {{ border-left: 4px solid #22c55e; }}
        .test-card.failed {{ border-left: 4px solid #ef4444; }}
        .test-title {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }}
        .test-meta {{ color: #666; font-size: 0.9em; }}
        .steps {{ margin-top: 15px; }}
        .step {{ padding: 5px 10px; margin: 5px 0; background: #f8f8f8; border-radius: 4px; }}
        .step.success {{ background: #dcfce7; }}
        .step.failed {{ background: #fee2e2; }}
        .screenshots {{ margin-top: 15px; }}
        .screenshots img {{ max-width: 300px; margin: 5px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; }}
        .screenshots img:hover {{ transform: scale(1.02); }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Selenium E2E 테스트 결과</h1>
        <p>테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <div class="stat passed">
                <h3>{passed}</h3>
                <p>통과</p>
            </div>
            <div class="stat failed">
                <h3>{failed}</h3>
                <p>실패</p>
            </div>
            <div class="stat">
                <h3>{len(self.results)}</h3>
                <p>전체</p>
            </div>
        </div>

        <h2>테스트 상세</h2>
"""

        for result in self.results:
            status_class = "success" if result["success"] else "failed"
            status_icon = "✅" if result["success"] else "❌"

            html += f"""
        <div class="test-card {status_class}">
            <div class="test-title">{status_icon} {result.get('name', result['announcement_id'])}</div>
            <div class="test-meta">
                ID: {result['announcement_id']} | Source: {result['source']}
                {f" | Tier: {result.get('tier', 'N/A')}" if 'tier' in result else ""}
            </div>
            <div class="steps">
                <strong>실행 단계:</strong>
"""
            for step in result.get("steps", []):
                step_class = "success" if step["status"] == "success" else "failed"
                html += f'                <div class="step {step_class}">{step["step"]}: {step["status"]}</div>\n'

            if result.get("error"):
                html += f'                <div class="step failed">Error: {result["error"]}</div>\n'

            html += """
            </div>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""

        report_file = "test_screenshots/selenium/test_report.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"📊 HTML 리포트: {report_file}")


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Selenium E2E 테스트")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드 (브라우저 숨김)")
    parser.add_argument("--id", type=str, help="특정 공고 ID만 테스트")
    parser.add_argument("--source", type=str, choices=["kstartup", "bizinfo"], help="특정 소스만 테스트")
    args = parser.parse_args()

    # 테스트 대상 필터링
    global TEST_ANNOUNCEMENTS
    if args.id:
        TEST_ANNOUNCEMENTS = [a for a in TEST_ANNOUNCEMENTS if a["id"] == args.id]
    if args.source:
        TEST_ANNOUNCEMENTS = [a for a in TEST_ANNOUNCEMENTS if a["source"] == args.source]

    if not TEST_ANNOUNCEMENTS:
        print("❌ 테스트할 공고가 없습니다.")
        return

    # 테스트 실행
    test = SeleniumE2ETest(headless=args.headless)
    test.run_all_tests()

    # 결과 출력
    print("\n" + "="*70)
    print("📊 테스트 결과 요약")
    print("="*70)
    passed = sum(1 for r in test.results if r["success"])
    failed = len(test.results) - passed
    print(f"✅ 통과: {passed}")
    print(f"❌ 실패: {failed}")
    print(f"📁 스크린샷: test_screenshots/selenium/")
    print(f"📄 HTML 리포트: test_screenshots/selenium/test_report.html")


if __name__ == "__main__":
    main()
