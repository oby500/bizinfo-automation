import { NextResponse } from 'next/server';
import OpenAI from 'openai';
import { supabase } from '@/lib/supabase/client';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY!,
});

type Source = 'all' | 'kstartup' | 'bizinfo';

function computeKeywordScore(query: string, record: any): number {
  const q = (query || '').trim();
  if (!q) return 0;

  const qLower = q.toLowerCase();
  const searchAnalysis = record?.search_analysis;

  // 2차 임베딩이 있는 경우 (첨부파일 O)
  if (searchAnalysis) {
    let score = 0;

    // search_keywords 매칭 (15%)
    const searchKeywords: unknown = searchAnalysis?.search_keywords;
    if (Array.isArray(searchKeywords)) {
      const match = searchKeywords.some((kw) => String(kw).toLowerCase().includes(qLower));
      if (match) score += 0.15;
    }

    // summary 매칭 (5%)
    const summaryText = String(searchAnalysis?.summary ?? '').toLowerCase();
    if (summaryText.includes(qLower)) score += 0.05;

    // support_target 매칭 (5%)
    const supportTargetText = String(searchAnalysis?.support_target ?? '').toLowerCase();
    if (supportTargetText.includes(qLower)) score += 0.05;

    // business_fields + tech_fields 매칭 (5%)
    const businessFields: unknown = searchAnalysis?.business_fields;
    const techFields: unknown = searchAnalysis?.tech_fields;
    const fields = [
      ...(Array.isArray(businessFields) ? businessFields : []),
      ...(Array.isArray(techFields) ? techFields : []),
    ].map((v) => String(v).toLowerCase());
    if (fields.some((f) => f.includes(qLower))) score += 0.05;

    return score;
  }

  // 1차 임베딩 폴백 (첨부파일 X)
  const summaryFallback = String(
    record?.simple_summary ?? record?.bsns_sumry ?? record?.pblanc_cn ?? ''
  ).toLowerCase();
  return summaryFallback.includes(qLower) ? 0.3 : 0.0;
}

function normalizeResult(source: Source, row: any, query: string) {
  const similarity = Number(row?.similarity ?? 0);
  const keyword_score = computeKeywordScore(query, row);
  const vector_score = similarity;
  const final_score = vector_score * 0.7 + keyword_score;

  if (source === 'kstartup') {
    return {
      source: 'kstartup',
      announcement_id: row?.announcement_id,
      title: row?.biz_pbanc_nm,
      organization: row?.pbanc_ntrp_nm,
      start_date: row?.pbanc_rcpt_bgng_dt,
      end_date: row?.pbanc_rcpt_end_dt,
      summary: row?.simple_summary ?? row?.bsns_sumry ?? null,
      has_writable_content: row?.has_writable_content ?? null,
      vector_score,
      keyword_score,
      final_score,
    };
  }

  return {
    source: 'bizinfo',
    announcement_id: row?.pblanc_id,
    title: row?.pblanc_nm,
    organization: row?.organ_nm,
    start_date: row?.reqst_begin_ymd,
    end_date: row?.reqst_end_ymd,
    summary: row?.simple_summary ?? row?.pblanc_cn ?? null,
    has_writable_content: row?.has_writable_content ?? null,
    vector_score,
    keyword_score,
    final_score,
  };
}

export async function POST(request: Request) {
  const body = await request.json();
  const query = String(body?.query ?? '');
  const source = (body?.source ?? 'all') as Source;
  const limit = Number(body?.limit ?? 20);

  if (!query.trim()) {
    return NextResponse.json({ results: [], total: 0, query }, { status: 200 });
  }

  const embeddingResponse = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: query,
  });
  const query_embedding = embeddingResponse.data[0].embedding;

  const results: any[] = [];

  if (source === 'all' || source === 'kstartup') {
    const { data, error } = await supabase.rpc('match_kstartup_announcements', {
      query_embedding,
      match_threshold: 0.0,
      match_count: Math.max(100, limit * 50),
    });
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    for (const row of data ?? []) {
      results.push(normalizeResult('kstartup', row, query));
    }
  }

  if (source === 'all' || source === 'bizinfo') {
    const { data, error } = await supabase.rpc('match_bizinfo_announcements', {
      query_embedding,
      match_threshold: 0.0,
      match_count: Math.max(100, limit * 50),
    });
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    for (const row of data ?? []) {
      results.push(normalizeResult('bizinfo', row, query));
    }
  }

  results.sort((a, b) => (b.final_score ?? 0) - (a.final_score ?? 0));
  const sliced = results.slice(0, Math.max(0, limit));

  return NextResponse.json({
    results: sliced,
    total: sliced.length,
    query,
  });
}
