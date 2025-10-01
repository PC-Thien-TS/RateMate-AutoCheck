import { NextResponse } from 'next/server';
import { createHmac, randomBytes } from 'crypto';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type LoginPayload = {
  password?: string;
};

function signSession(sessionId: string, token: string, secret: string): string {
  const signature = createHmac('sha256', secret).update(`${sessionId}:${token}`).digest('hex');
  return `${sessionId}.${signature}`;
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as LoginPayload;
  const password = String(body?.password ?? '');
  const token = process.env.DASH_TOKEN || '';
  if (!token) {
    return NextResponse.json({ ok: true });
  }
  if (password !== token) {
    return NextResponse.json({ ok: false, error: 'Invalid password' }, { status: 401 });
  }
  const res = NextResponse.json({ ok: true });
  const sessionSecret = process.env.DASH_SESSION_SECRET || token;
  const sessionId = randomBytes(32).toString('hex');
  const cookieValue = signSession(sessionId, token, sessionSecret);
  res.cookies.set('dash_session', cookieValue, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60 * 8,
    path: '/',
  });
  return res;
}
