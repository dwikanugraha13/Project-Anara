import type { NextConfig } from "next";

const envOrigins = process.env.ALLOWED_DEV_ORIGINS
  ? process.env.ALLOWED_DEV_ORIGINS.split(",").map((s) => s.trim()).filter(Boolean)
  : [];

const nextConfig: NextConfig = {
  // Dynamic allowed dev origins for local and tunnel access
  allowedDevOrigins: Array.from(
    new Set(["localhost", "127.0.0.1", "anara.my.id", "*.anara.my.id", ...envOrigins])
  ),
  // Disable StrictMode to prevent double WebSocket connections in dev
  reactStrictMode: false,
  typescript: {
    // Verified via 'npx tsc --noEmit' directly to prevent sub-worker V8 heap memory exhaustion
    ignoreBuildErrors: true,
  },
  experimental: {
    cpus: 1,
  },
  devIndicators: false,
  turbopack: {},
  rewrites: async () => {
    const backendPort = process.env.NEXT_PUBLIC_BACKEND_PORT || "8000";
    return [
      {
        source: "/api/:path*",
        destination: `http://localhost:${backendPort}/api/:path*`,
      },
    ];
  },
  headers: async () => {
    return [
      {
        source: "/_next/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
    ];
  },
  webpack: (config, { dev }) => {
    if (dev) {
      // Disable webpack filesystem cache that causes 'Array buffer allocation failed'
      config.cache = false;
      // Increase chunk loading timeout for tunnel / remote access
      config.output = config.output || {};
      config.output.chunkLoadTimeout = 300000;
    }
    return config;
  },
};

export default nextConfig;
