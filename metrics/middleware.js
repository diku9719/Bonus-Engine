// Vercel Routing Middleware: username + password in front of every file on this site (page and data).
// Logins come from the Vercel environment variable DASH_USERS: "user:password" pairs separated by commas,
// e.g. "zayn:LongPassword1,manav:LongPassword2" (no commas inside passwords). If it is missing, nobody gets in.
export const config = { matcher: '/(.*)' };

const same = (a, b) => {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
};

const logins = () => (process.env.DASH_USERS || '')
  .split(',').map((p) => p.trim()).filter(Boolean)
  .map((p) => { const i = p.indexOf(':'); return i > 0 ? [p.slice(0, i), p.slice(i + 1)] : null; })
  .filter((p) => p && p[1]);

export default function middleware(request) {
  const header = request.headers.get('authorization') || '';
  if (header.startsWith('Basic ')) {
    let decoded = '';
    try { decoded = atob(header.slice(6)); } catch (e) { decoded = ''; }
    const i = decoded.indexOf(':');
    if (i > 0) {
      const u = decoded.slice(0, i), p = decoded.slice(i + 1);
      if (logins().some(([lu, lp]) => same(u, lu) && same(p, lp))) return; // allowed through
    }
  }
  return new Response('Login required', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="Enki metrics", charset="UTF-8"', 'Cache-Control': 'no-store' },
  });
}
