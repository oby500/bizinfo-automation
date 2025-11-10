/**
 * 인증 및 결제 플로우 E2E 테스트
 *
 * 실행 방법:
 * pnpm test:e2e
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

// 모든 테스트에서 공유할 고정된 사용자 정보
const TEST_USER = {
  name: '테스트 사용자',
  email: 'e2e-test-user@example.com',
  password: 'Test1234!@#$'
};

test.describe('인증 시스템 E2E 테스트', () => {

  test('1. 홈페이지 로드 확인', async ({ page }) => {
    await page.goto(BASE_URL);

    // 페이지가 완전히 로드될 때까지 대기
    await page.waitForLoadState('networkidle');

    // DOM이 준비될 때까지 추가 대기
    await page.waitForTimeout(1000);

    // 페이지 로드 확인 - 헤더의 로튼 로고 (h1 태그)
    const logo = page.getByRole('heading', { name: '로튼', level: 1 });
    await expect(logo).toBeVisible({ timeout: 10000 });

    // 검색 기능 확인
    const searchInput = page.getByPlaceholder('검색어 입력 (2글자 이상)');
    await expect(searchInput).toBeVisible({ timeout: 10000 });

    // 🔍 로그아웃 상태 UI 검증: 인증된 요소가 보이면 안 됨
    await expect(page.getByText('보유 크레딧')).not.toBeVisible();
    await expect(page.getByText('충전하기')).not.toBeVisible();

    // 로그아웃 상태에서는 "로그인" 버튼이 보여야 함
    const loginButton = page.getByRole('link', { name: '로그인' });
    await expect(loginButton).toBeVisible({ timeout: 5000 });

    console.log('✅ 홈페이지 정상 로드');
    console.log('✅ 로그아웃 상태 UI 검증 완료 (크레딧/충전하기 미표시)');
  });

  test('2. 회원가입 플로우', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // 회원가입 탭 클릭
    await page.getByRole('tab', { name: '회원가입' }).click();

    // alert 이벤트를 Promise로 캡처
    const alertPromise = page.waitForEvent('dialog');

    // 폼 입력 (실제 placeholder 사용)
    await page.locator('#signup-name').fill(TEST_USER.name);
    await page.locator('#signup-email').fill(TEST_USER.email);
    await page.locator('#signup-password').fill(TEST_USER.password);

    // 회원가입 버튼 클릭
    await page.getByRole('button', { name: '회원가입' }).click();

    // alert 대기 및 확인
    const dialog = await alertPromise;
    const message = dialog.message();
    console.log('Alert 메시지:', message);
    await dialog.accept();

    // 회원가입 성공 또는 이미 존재하는 사용자
    if (message.includes('회원가입이 완료되었습니다') || message.includes('이미 가입된')) {
      console.log('✅ 회원가입 처리:', TEST_USER.email);
    } else {
      throw new Error(`예상하지 못한 메시지: ${message}`);
    }
  });

  test('3. 로그아웃 플로우', async ({ page }) => {
    // 먼저 로그인
    await page.goto(`${BASE_URL}/login`);
    await page.locator('#email').fill(TEST_USER.email);
    await page.locator('#password').fill(TEST_USER.password);

    // alert 이벤트 리스너 등록
    page.on('dialog', async dialog => {
      console.log('Alert:', dialog.message());
      await dialog.accept();
    });

    await page.getByRole('button', { name: '이메일로 로그인' }).click();
    await page.waitForURL(BASE_URL, { timeout: 10000 });

    // 페이지 로드 대기
    await page.waitForLoadState('networkidle');

    // 홈페이지에서는 드롭다운이 없으므로 마이페이지로 이동
    await page.goto(`${BASE_URL}/mypage`);
    await page.waitForLoadState('networkidle');

    // Avatar 버튼 찾기 (마이페이지에는 레이아웃 헤더가 있음)
    const avatarButton = page.locator('header').getByRole('button').first();
    await expect(avatarButton).toBeVisible({ timeout: 10000 });

    // Avatar 버튼 클릭
    await avatarButton.click();

    // 드롭다운 메뉴가 나타날 때까지 대기
    await expect(page.getByText('로그아웃')).toBeVisible({ timeout: 5000 });

    // 로그아웃 메뉴 클릭
    await page.getByText('로그아웃').click();

    // 로그인 페이지로 리디렉트 확인
    await page.waitForURL(`${BASE_URL}/login`, { timeout: 5000 });

    // 로그인 탭이 보이는지 확인
    const loginTab = page.getByRole('tab', { name: '로그인' });
    await expect(loginTab).toBeVisible();

    console.log('✅ 로그아웃 성공');
  });

  test('4. 이메일 로그인 플로우', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // alert 이벤트 리스너 등록
    page.on('dialog', async dialog => {
      console.log('Alert:', dialog.message());
      await dialog.accept();
    });

    // 로그인 폼 입력
    await page.locator('#email').fill(TEST_USER.email);
    await page.locator('#password').fill(TEST_USER.password);

    // 로그인 버튼 클릭
    await page.getByRole('button', { name: '이메일로 로그인' }).click();

    // 네트워크가 안정될 때까지 대기
    await page.waitForLoadState('networkidle');

    // 홈으로 리디렉트 확인 (타임아웃 증가)
    await page.waitForURL(BASE_URL, { timeout: 30000 });

    // 🔍 로그인된 상태 UI 검증: 인증된 요소들이 보여야 함
    await expect(page.getByText('보유 크레딧')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('충전하기')).toBeVisible({ timeout: 10000 });

    // 로그인된 상태 확인 (헤더의 사용자 버튼 존재)
    const userButton = page.locator('header').getByRole('button').filter({ hasText: '👤' });
    await expect(userButton).toBeVisible({ timeout: 10000 });

    // 🔍 로그인 상태에서는 "로그인" 버튼이 보이면 안 됨
    await expect(page.getByRole('link', { name: '로그인' })).not.toBeVisible();

    console.log('✅ 이메일 로그인 성공');
    console.log('✅ 로그인 상태 UI 검증 완료 (크레딧/충전하기 표시)');
  });

  test('5. 페이지 보호 테스트 - /charge', async ({ page }) => {
    // 로그아웃 상태에서 /charge 접속
    await page.goto(`${BASE_URL}/charge`);

    // 로그인 페이지로 리디렉트 확인
    await page.waitForURL(/\/login\?callbackUrl/, { timeout: 5000 });

    // URL에 callbackUrl 파라미터 확인 (인코딩 여부 무관)
    const url = page.url();
    expect(url).toMatch(/callbackUrl=(\/charge|%2Fcharge)/);

    console.log('✅ /charge 페이지 보호 확인');
  });

  test('6. 페이지 보호 테스트 - /mypage', async ({ page }) => {
    // 로그아웃 상태에서 /mypage 접속
    await page.goto(`${BASE_URL}/mypage`);

    // 로그인 페이지로 리디렉트 확인
    await page.waitForURL(/\/login\?callbackUrl/, { timeout: 5000 });

    // URL에 callbackUrl 파라미터 확인 (인코딩 여부 무관)
    const url = page.url();
    expect(url).toMatch(/callbackUrl=(\/mypage|%2Fmypage)/);

    console.log('✅ /mypage 페이지 보호 보호 확인');
  });

  test('7. 로그인 후 callbackUrl로 리디렉트', async ({ page }) => {
    // 로그아웃 상태에서 /charge 접속
    await page.goto(`${BASE_URL}/charge`);
    await page.waitForURL(/\/login\?callbackUrl/, { timeout: 10000 });

    // alert 이벤트 리스너 등록
    page.on('dialog', async dialog => {
      console.log('Alert:', dialog.message());
      await dialog.accept();
    });

    // 로그인
    await page.locator('#email').fill(TEST_USER.email);
    await page.locator('#password').fill(TEST_USER.password);
    await page.getByRole('button', { name: '이메일로 로그인' }).click();

    // /charge로 리디렉트 확인
    await page.waitForURL(`${BASE_URL}/charge`, { timeout: 10000 });

    // 충전 페이지 타이틀 확인
    const heading = page.locator('h1', { hasText: '충전하기' });
    await expect(heading).toBeVisible({ timeout: 5000 });

    console.log('✅ 로그인 후 callbackUrl 리디렉트 성공');
  });

  test('8. 충전 페이지 UI 확인', async ({ page }) => {
    // alert 이벤트 리스너 등록
    page.on('dialog', async dialog => {
      console.log('Alert:', dialog.message());
      await dialog.accept();
    });

    // 로그인
    await page.goto(`${BASE_URL}/login`);
    await page.locator('#email').fill(TEST_USER.email);
    await page.locator('#password').fill(TEST_USER.password);
    await page.getByRole('button', { name: '이메일로 로그인' }).click();
    await page.waitForURL(BASE_URL, { timeout: 10000 });

    // /charge 페이지 접속
    await page.goto(`${BASE_URL}/charge`);

    // 페이지 로드 확인
    const heading = page.locator('h1', { hasText: '충전하기' });
    await expect(heading).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('현재 보유 크레딧')).toBeVisible();

    // 충전 옵션 카드 확인 (10,000원 텍스트가 여러 개 있으므로 CardTitle 내부 것 선택)
    const option10k = page.locator('.text-2xl').filter({ hasText: '10,000원' }).first();
    await expect(option10k).toBeVisible();

    // 충전 금액 선택 (카드 클릭)
    const firstCard = page.locator('div.cursor-pointer').first();
    await firstCard.click();

    // 충전 버튼 텍스트 변경 확인
    await page.waitForTimeout(500); // 상태 업데이트 대기
    const chargeButton = page.getByRole('button', { name: /충전하기/ });
    await expect(chargeButton).toContainText('10,000원');

    console.log('✅ 충전 페이지 UI 정상 작동');
  });

  test('9. 잘못된 로그인 정보 처리', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // alert 이벤트를 Promise로 캡처
    const alertPromise = page.waitForEvent('dialog');

    // 잘못된 비밀번호로 로그인 시도
    await page.locator('#email').fill(TEST_USER.email);
    await page.locator('#password').fill('wrong-password');
    await page.getByRole('button', { name: '이메일로 로그인' }).click();

    // alert 대기 및 확인
    const dialog = await alertPromise;
    const alertMessage = dialog.message();
    console.log('Alert:', alertMessage);
    expect(alertMessage).toContain('이메일 또는 비밀번호가');
    await dialog.accept();

    // 로그인 페이지에 머물러 있는지 확인
    expect(page.url()).toContain('/login');

    console.log('✅ 잘못된 로그인 정보 처리 확인');
  });

  test('10. 마이페이지 접근 확인', async ({ page }) => {
    // alert 이벤트 리스너 등록
    page.on('dialog', async dialog => {
      console.log('Alert:', dialog.message());
      await dialog.accept();
    });

    // 로그인
    await page.goto(`${BASE_URL}/login`);
    await page.locator('#email').fill(TEST_USER.email);
    await page.locator('#password').fill(TEST_USER.password);
    await page.getByRole('button', { name: '이메일로 로그인' }).click();
    await page.waitForURL(BASE_URL, { timeout: 30000 });

    // 페이지 로드 대기
    await page.waitForLoadState('networkidle');

    // 사용자 버튼 찾기 (홈페이지에는 header가 없으므로 직접 버튼 선택)
    const userButton = page.getByRole('button', { name: /👤.*님/ });
    await expect(userButton).toBeVisible({ timeout: 10000 });

    // 사용자 버튼 클릭
    await userButton.click();

    // 드롭다운 메뉴가 나타날 때까지 대기
    await expect(page.getByText('마이페이지')).toBeVisible({ timeout: 5000 });

    // 마이페이지 메뉴 클릭
    await page.getByText('마이페이지').click();

    // 마이페이지로 이동 확인
    await page.waitForURL(`${BASE_URL}/mypage`, { timeout: 5000 });

    // 마이페이지 타이틀 확인 (CardTitle)
    await expect(page.getByText('마이페이지').first()).toBeVisible({ timeout: 5000 });

    console.log('✅ 마이페이지 접근 성공');
  });
});

test.describe('결제 플로우 테스트 (수동)', () => {
  test.skip('결제 프로세스는 실제 결제 모듈이 필요하므로 수동 테스트 권장', async ({ page }) => {
    // 이 테스트는 실제 PortOne 결제창을 테스트합니다
    // 테스트 환경에서는 skip 처리하고 수동으로 테스트하세요

    await page.goto(`${BASE_URL}/login`);
    // ... 로그인 후 결제 진행
  });
});
