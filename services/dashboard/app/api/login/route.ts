import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const { password } = await req.json().catch(() => ({ password: '' }));
  const token = process.env.DASH_TOKEN || '';
  if (!token) return NextResponse.json({ ok: true });
  if (password !== token) return NextResponse.json({ ok: false, error: 'Invalid password' }, { status: 401 });
  const res = NextResponse.json({ ok: true });
  res.cookies.set('dash_token', token, { httpOnly: false, sameSite: 'lax', maxAge: 60 * 60 * 8 });
  return res;
}

