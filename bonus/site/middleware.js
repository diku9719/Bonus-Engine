// Vercel Routing Middleware: HTTP Basic auth in front of every file on this site.
// Set DASH_USER and DASH_PASSWORD in the Vercel project's Environment Variables.
export const config = { matcher: '/(.*)' };

export default function middleware(request) {
  const user = process.env.DASH_USER;
  const pass = process.env.DASH_PASSWORD;
  const header = request.headers.get('authorization') || '';
  if (user && pass && header.startsWith('Basic ')) {
    const [u, ...rest] = atob(header.slice(6)).split(':');
    if (u === user && rest.join(':') === pass) return; // let the request through
  }
  return new Response('Login required', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="Enki metrics", charset="UTF-8"', 'Cache-Control': 'no-store' },
  });
}
