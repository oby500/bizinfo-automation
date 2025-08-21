// Edge Function 로컬 테스트 버전
const https = require('https');
const http = require('http');
const fs = require('fs');

// 환경변수 직접 설정
process.env.SUPABASE_URL = 'https://csuziaogycciwgxxmahm.supabase.co';
process.env.SUPABASE_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzdXppYW9neWNjaXdneHhtYWhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYxNTc4MCwiZXhwIjoyMDY5MTkxNzgwfQ.HnhM7zSLzi7lHVPd2IVQKIACDq_YA05mBMgZbSN1c9Q';

// Supabase 클라이언트 mock (간단 버전)
class SimpleSupabaseClient {
  constructor(url, key) {
    this.url = url;
    this.key = key;
  }
  
  table(tableName) {
    return new SimpleTable(this.url, this.key, tableName);
  }
}

class SimpleTable {
  constructor(url, key, tableName) {
    this.url = url;
    this.key = key;
    this.tableName = tableName;
  }
  
  select(columns) {
    return {
      count: (type) => ({
        head: (value) => ({
          execute: async () => {
            console.log(`📊 ${this.tableName} 테이블 카운트 조회 중...`);
            return { data: 279 }; // Mock data
          }
        })
      })
    };
  }
  
  eq(column, value) {
    return {
      single: async () => {
        console.log(`🔍 중복 체크: ${column} = ${value}`);
        return { data: null }; // No duplicate found
      }
    };
  }
  
  insert(data) {
    return {
      select: (columns) => ({
        single: async () => {
          console.log(`✅ 삽입 성공: ${data.pblanc_nm || data.title || 'Unknown'}`);
          return { 
            data: { id: Math.floor(Math.random() * 10000), ...data },
            error: null
          };
        }
      })
    };
  }
}

function createClient(url, key) {
  return new SimpleSupabaseClient(url, key);
}

// HTTP 요청 함수
function fetchData(url, options = {}) {
  return new Promise((resolve, reject) => {
    const protocol = url.startsWith('https:') ? https : http;
    
    const req = protocol.request(url, {
      method: options.method || 'GET',
      headers: options.headers || {},
      timeout: options.timeout || 30000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({
          ok: res.statusCode >= 200 && res.statusCode < 300,
          status: res.statusCode,
          statusText: res.statusMessage,
          text: () => Promise.resolve(data)
        });
      });
    });
    
    req.on('error', reject);
    req.on('timeout', () => reject(new Error('Request timeout')));
    req.end();
  });
}

// XML 파싱 함수들 (Edge Function에서 복사)
function parseXmlItems(xmlText) {
  const items = [];
  
  try {
    // XML에서 item 요소 찾기
    const itemMatches = xmlText.match(/<item[^>]*>([\s\S]*?)<\/item>/gi);
    
    if (!itemMatches) {
      console.log('⚠️ XML에서 item 요소를 찾을 수 없습니다.');
      // RSS 구조 확인
      if (xmlText.includes('<rss')) {
        console.log('📄 RSS 형식 감지, 다른 구조 확인 중...');
        const channelMatch = xmlText.match(/<channel[^>]*>([\s\S]*?)<\/channel>/i);
        if (channelMatch) {
          const channelContent = channelMatch[1];
          const channelItemMatches = channelContent.match(/<item[^>]*>([\s\S]*?)<\/item>/gi);
          if (channelItemMatches) {
            return parseItemMatches(channelItemMatches);
          }
        }
      }
      return items;
    }
    
    return parseItemMatches(itemMatches);
    
  } catch (e) {
    console.error('❌ XML 파싱 오류:', e);
    return items;
  }
}

function parseItemMatches(itemMatches) {
  const items = [];
  
  itemMatches.forEach((itemXml, index) => {
    try {
      const item = {};
      
      // 각 필드 추출
      const fieldMatches = itemXml.match(/<([^>\s]+)>([\s\S]*?)<\/\1>/gi);
      
      if (fieldMatches) {
        fieldMatches.forEach(fieldXml => {
          const match = fieldXml.match(/<([^>\s]+)>([\s\S]*?)<\/\1>/i);
          if (match) {
            const [, tagName, value] = match;
            if (tagName.toLowerCase() !== 'item' && value.trim()) {
              const cleanValue = value
                .replace(/<[^>]*>/g, '')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&amp;/g, '&')
                .replace(/&quot;/g, '"')
                .replace(/&#39;/g, "'")
                .replace(/\s+/g, ' ')
                .trim();
              
              if (cleanValue) {
                item[tagName.toLowerCase()] = cleanValue;
              }
            }
          }
        });
      }
      
      if (Object.keys(item).length > 0) {
        items.push(item);
      }
    } catch (e) {
      console.log(`⚠️ 아이템 ${index + 1} 파싱 실패:`, e);
    }
  });
  
  return items;
}

function parseDate(dateStr) {
  if (!dateStr || !dateStr.trim()) return null;
  
  const cleaned = dateStr.trim();
  
  const formats = [
    /^(\d{4})-(\d{2})-(\d{2})/,
    /^(\d{4})(\d{2})(\d{2})$/,
    /^(\d{4})\.(\d{2})\.(\d{2})/,
    /^(\d{4})\/(\d{2})\/(\d{2})/,
  ];
  
  for (const regex of formats) {
    const match = cleaned.match(regex);
    if (match) {
      const [, year, month, day] = match;
      return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    }
  }
  
  return null;
}

// 메인 Edge Function 로직
async function runEdgeFunction() {
  const startTime = new Date();
  console.log(`🚀 Edge Function 로컬 테스트 시작 - ${startTime.toISOString()}`);

  try {
    // Supabase 클라이언트 생성
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_SERVICE_KEY;
    const supabase = createClient(supabaseUrl, supabaseKey);
    
    const batchId = `local_test_${startTime.toISOString().replace(/[:.]/g, '_').slice(0, 19)}`;
    console.log(`📋 배치 ID: ${batchId}`);
    
    // 1. 기존 데이터 현황 확인
    const existingCount = await supabase
      .from('kstartup_complete')
      .select('id', { count: 'exact', head: true })
      .execute();
    
    console.log(`📊 기존 DB 데이터: ${existingCount.data || 0}개`);
    
    // 2. K-Startup API 호출 (Edge Function에서 사용하는 URL)
    const apiUrl = 'https://www.k-startup.go.kr/api/apisvc/xml/GetPblancListSvc';
    const params = new URLSearchParams({
      perPage: '100',
      page: '1',
      sortColumn: 'REG_YMD',
      sortDirection: 'DESC'
    });
    
    console.log(`📡 API 호출: ${apiUrl}`);
    
    const apiResponse = await fetchData(`${apiUrl}?${params}`, {
      headers: {
        'User-Agent': 'Local-Test/1.0'
      },
      timeout: 30000
    });
    
    if (!apiResponse.ok) {
      throw new Error(`API 호출 실패: ${apiResponse.status} ${apiResponse.statusText}`);
    }
    
    const xmlText = await apiResponse.text();
    console.log(`✅ API 응답 수신: ${xmlText.length} bytes`);
    
    // 3. XML 파싱
    const items = parseXmlItems(xmlText);
    console.log(`📄 파싱된 아이템: ${items.length}개`);
    
    if (items.length === 0) {
      console.log('⚠️ 파싱된 아이템이 없습니다.');
      console.log('📄 XML 미리보기:', xmlText.slice(0, 500));
      return;
    }
    
    // 4. 샘플 데이터 출력
    console.log('\n📋 파싱된 아이템 샘플:');
    items.slice(0, 3).forEach((item, index) => {
      console.log(`  ${index + 1}. ${item.pblancnm || item.title || 'Unknown'}`);
    });
    
    // 5. DB 저장 시뮬레이션
    let insertedCount = 0;
    let duplicateCount = 0;
    
    for (const item of items.slice(0, 5)) { // 처음 5개만 테스트
      try {
        // 중복 체크 시뮬레이션
        const existing = await supabase
          .table('kstartup_complete')
          .select('id, pblanc_nm')
          .eq('pblanc_id', item.pblancid || item.seq);
        
        if (existing.data) {
          duplicateCount++;
        } else {
          // 새 레코드 삽입 시뮬레이션
          const record = {
            collection_batch_id: batchId,
            source: 'k-startup-edge',
            pblanc_nm: item.pblancnm || item.title,
            pblanc_id: item.pblancid || item.seq,
            pblanc_url: item.pblancurl || item.link,
            organ_nm: item.organnm || item.author,
            bsns_sumry: item.bsnssumry || item.description,
            raw_xml_data: item
          };
          
          const result = await supabase
            .table('kstartup_complete')
            .insert(record)
            .select('id, pblanc_nm')
            .single();
          
          insertedCount++;
        }
      } catch (err) {
        console.error(`❌ 처리 실패: ${item.pblancnm || 'Unknown'} - ${err}`);
      }
    }
    
    const endTime = new Date();
    const duration = endTime.getTime() - startTime.getTime();
    
    console.log('\n🎉 Edge Function 테스트 완료');
    console.log(`⏱️ 소요시간: ${duration}ms`);
    console.log(`📊 결과: 삽입 ${insertedCount}개, 중복 ${duplicateCount}개`);
    
  } catch (error) {
    console.error(`❌ Edge Function 오류:`, error.message);
  }
}

// 실행
runEdgeFunction();