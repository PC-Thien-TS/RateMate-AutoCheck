import { NextRequest, NextResponse } from 'next/server';

async function hmacSha256Hex(key: string, message: string): Promise<string> {
  const enc = new TextEncoder();
  const keyData = enc.encode(key);
  const msgData = enc.encode(message);
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', cryptoKey, msgData);
  const bytes = new Uint8Array(sig);
  let hex = '';
  for (let i = 0; i < bytes.length; i++) {
    const h = bytes[i].toString(16).padStart(2, '0');
    hex += h;
  }
  return hex;
}

function constantTimeEqualHex(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let res = 0;
  for (let i = 0; i < a.length; i++) {
    res |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return res === 0;
}

async function isSessionValid(raw: string | undefined, token: string): Promise<boolean> {
  if (!raw) return false;
  const [sessionId, signature] = raw.split('.');
  if (!sessionId || !signature) return false;
  const secret = process.env.DASH_SESSION_SECRET || token;
  try {
    const expected = await hmacSha256Hex(secret, `${sessionId}:${token}`);
    const sigNorm = signature.trim().toLowerCase();
    return constantTimeEqualHex(sigNorm, expected);
  } catch (err) {
    console.warn('Edge HMAC verify failed', err);
    return false;
  }
}

export async function middleware(req: NextRequest) {
  const token = process.env.DASH_TOKEN;
  if (!token) {
    return NextResponse.next();
  }
  const cookie = req.cookies.get('dash_session')?.value;
  if (await isSessionValid(cookie, token)) {
    return NextResponse.next();
  }
  const url = req.nextUrl.clone();
  if (url.pathname === '/auth') {
    return NextResponse.next();
  }
  url.pathname = '/auth';
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|auth|api/login).*)'],
};
