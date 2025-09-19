import { NextRequest, NextResponse } from 'next/server';

export function middleware(req: NextRequest) {
  const token = process.env.DASH_TOKEN;
  if (!token) return NextResponse.next(); // disabled
  const cookie = req.cookies.get('dash_token')?.value;
  if (cookie === token) return NextResponse.next();
  const url = req.nextUrl.clone();
  url.pathname = '/auth';
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|auth|api/login).*)'],
};

