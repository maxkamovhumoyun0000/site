import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next.js o'z gzip/brotli compression ni ishlatsin
  compress: true,
  poweredByHeader: false,
  productionBrowserSourceMaps: false,

  typescript: {
    ignoreBuildErrors: false,
  },

  // Og'ir kutubxonalar uchun tree-shaking yaxshilansin
  experimental: {
    // Hash-based script integrity lets production use a strict script-src
    // policy without forcing every route into dynamic rendering.
    sri: { algorithm: "sha256" },
    optimizePackageImports: [
      "three",
      "@react-three/fiber",
      "@react-three/drei",
      "epubjs",
    ],
  },

  // Image optimizatsiya cache muddati (1 hafta)
  images: {
    minimumCacheTTL: 604800,
  },

  // AI import 33-35s ketadi — proxy timeout 90s ga oshirildi
  httpAgentOptions: {
    keepAlive: true,
  },

  async redirects() {
    return [
      {
        source: "/student/mistakes",
        destination: "/student/dashboard",
        permanent: false,
      },
    ];
  },

  async headers() {
    // Keep third-party permissions narrow and separate executable scripts,
    // stylesheet elements, and React's style attributes.
    const isDevelopment = process.env.NODE_ENV !== "production";
    const csp = [
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
      `script-src 'self' https://telegram.org${isDevelopment ? " 'unsafe-eval'" : ""}`,
      "script-src-attr 'none'",
      "style-src 'self' https://fonts.googleapis.com",
      "style-src-elem 'self' https://fonts.googleapis.com",
      "style-src-attr 'unsafe-inline'",
    ].join("; ");
    return [{
      source: "/:path*",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "SAMEORIGIN" },
        { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=()" },
      ],
    }];
  },

  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:3001";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
      {
        source: "/chats/media/:path*",
        destination: `${backendUrl}/chats/media/:path*`,
      },
      {
        source: "/student/certificates/:id/pdf",
        destination: `${backendUrl}/student/certificates/:id/pdf`,
      },
      {
        source: "/certificates/:id/pdf",
        destination: `${backendUrl}/certificates/:id/pdf`,
      },
    ];
  },
};

export default nextConfig;
