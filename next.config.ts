import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next.js o'z gzip/brotli compression ni ishlatsin
  compress: true,

  typescript: {
    ignoreBuildErrors: false,
  },

  // Og'ir kutubxonalar uchun tree-shaking yaxshilansin
  experimental: {
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
