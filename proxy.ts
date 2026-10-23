import { NextRequest, NextResponse } from "next/server";

function contentSecurityPolicy(nonce: string, isDevelopment: boolean) {
  return [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'self'",
    "form-action 'self'",
    // User-provided profile/book thumbnails may live on external HTTPS hosts.
    // Images are non-executable; keep this broader than script/connect sources.
    "img-src 'self' data: blob: https: https://api.dicebear.com https://api.qrserver.com",
    "font-src 'self' data: https://fonts.gstatic.com",
    // Teachers can attach hosted audio/video URLs to lessons and learning paths.
    "media-src 'self' blob: https:",
    `connect-src 'self' https://live.diamond-education.uz wss://diamond-education.uz wss://live.diamond-education.uz${isDevelopment ? " ws://localhost:3001 http://127.0.0.1:18765" : ""}`,
    "worker-src 'self' blob:",
    "frame-src 'self' blob: https://www.youtube.com https://www.youtube-nocookie.com https://web.telegram.org https://www.google.com https://maps.google.com https://view.officeapps.live.com",
    `script-src 'self' 'nonce-${nonce}' https://telegram.org${isDevelopment ? " 'unsafe-eval'" : ""}`,
    "script-src-attr 'none'",
    `style-src 'self' 'nonce-${nonce}' https://fonts.googleapis.com`,
    `style-src-elem 'self' 'nonce-${nonce}' https://fonts.googleapis.com`,
    "style-src-attr 'unsafe-inline'",
  ].join("; ");
}

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy(nonce, process.env.NODE_ENV !== "production");

  // Next reads the request CSP to nonce its inline hydration and framework scripts.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("Content-Security-Policy", csp);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
