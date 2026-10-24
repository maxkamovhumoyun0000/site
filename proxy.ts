import { NextRequest, NextResponse } from "next/server";

function contentSecurityPolicy(nonce: string, isDevelopment: boolean) {
  return [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    // The product has no supported embedding use case; prevent clickjacking.
    "frame-ancestors 'none'",
    "form-action 'self'",
    "manifest-src 'self'",
    "upgrade-insecure-requests",
    // Render user uploads and locally-generated QR codes from this origin only.
    "img-src 'self' data: blob:",
    // Fonts are served by this site or use the user's local system fonts.
    "font-src 'self'",
    // Lesson audio/video is served by Diamond Education or captured locally.
    "media-src 'self' blob:",
    `connect-src 'self' https://live.diamond-education.uz wss://diamond-education.uz wss://live.diamond-education.uz${isDevelopment ? " ws://localhost:3001 http://127.0.0.1:18765" : ""}`,
    "worker-src 'self' blob:",
    "frame-src 'self' blob: https://www.youtube.com https://www.youtube-nocookie.com https://web.telegram.org https://www.google.com https://maps.google.com https://view.officeapps.live.com",
    `script-src 'self' 'nonce-${nonce}' https://telegram.org${isDevelopment ? " 'unsafe-eval'" : ""}`,
    "script-src-attr 'none'",
    `style-src 'self' 'nonce-${nonce}'`,
    `style-src-elem 'self' 'nonce-${nonce}'`,
    "style-src-attr 'none'",
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
      // Exclude actual backend API paths, but keep similarly-prefixed page
      // paths (for example `/api$`) under the same nonce-based CSP policy.
      source: "/((?!api(?:/|$)|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
