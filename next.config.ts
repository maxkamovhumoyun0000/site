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
    return [{
      source: "/:path*",
      headers: [
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
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
