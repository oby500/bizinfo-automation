import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const { message, filters, limit } = await request.json();

  const response = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL}/api/search/hybrid`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: message,
      source: filters?.source || 'all',
      limit: limit || 10,
    }),
  });

  const data = await response.json();

  return NextResponse.json({
    results: data.results || data.items || [],
    total: data.total || 0,
    query: message,
  });
}
