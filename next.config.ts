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

  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:3001";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
