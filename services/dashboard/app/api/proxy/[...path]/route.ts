import { NextRequest, NextResponse } from 'next/server';

const API_BASE = (process.env.API_GATEWAY_URL ?? 'http://localhost:8000').replace(/\/+$/, '');
const API_KEY = process.env.DASH_API_KEY ?? process.env.NEXT_PUBLIC_API_KEY ?? '';

export const dynamic = 'force-dynamic';

function buildTargetUrl(pathSegments: string[] | undefined, origin: NextRequest['nextUrl']): string {
  const joined = (pathSegments ?? []).join('/');
  const basePath = joined ? `${API_BASE}/${joined}` : API_BASE;
  const search = origin.search ?? '';
  return `${basePath}${search}`;
}

async function forwardRequest(req: NextRequest, context: { params: { path?: string[] } }): Promise<NextResponse> {
  if (!API_BASE) {
    return NextResponse.json({ error: 'API gateway URL not configured' }, { status: 500 });
  }
  const targetUrl = buildTargetUrl(context.params?.path, req.nextUrl);
  const headers = new Headers(req.headers);
  headers.delete('host');
  headers.delete('content-length');
  headers.set('accept-encoding', 'identity');
  if (API_KEY && !headers.has('x-api-key')) {
    headers.set('x-api-key', API_KEY);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: 'manual',
  };

  if (!['GET', 'HEAD'].includes(req.method.toUpperCase())) {
    const body = await req.arrayBuffer();
    init.body = body;
  }

  try {
    const upstream = await fetch(targetUrl, init);
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.delete('content-encoding');
    responseHeaders.delete('content-length');
    responseHeaders.set('cache-control', 'no-store');
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error: unknown) {
    return NextResponse.json({ error: (error as Error).message ?? 'Proxy request failed' }, { status: 502 });
  }
}

export async function GET(req: NextRequest, context: { params: { path?: string[] } }) {
  return forwardRequest(req, context);
}

export async function POST(req: NextRequest, context: { params: { path?: string[] } }) {
  return forwardRequest(req, context);
}

export async function PUT(req: NextRequest, context: { params: { path?: string[] } }) {
  return forwardRequest(req, context);
}

export async function PATCH(req: NextRequest, context: { params: { path?: string[] } }) {
  return forwardRequest(req, context);
}

export async function DELETE(req: NextRequest, context: { params: { path?: string[] } }) {
  return forwardRequest(req, context);
}

export async function OPTIONS(req: NextRequest, context: { params: { path?: string[] } }) {
  return forwardRequest(req, context);
}
