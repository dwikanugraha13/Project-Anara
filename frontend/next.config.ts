import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow Cloudflare Tunnel & local origins in development mode
  allowedDevOrigins: [
    "anara.my.id",
    "*.anara.my.id",
    "localhost",
    "127.0.0.1",
  ],
  // Disable StrictMode to prevent double WebSocket connections in dev
  reactStrictMode: false,
  typescript: {
    // Verified via 'npx tsc --noEmit' directly to prevent sub-worker V8 heap memory exhaustion
    ignoreBuildErrors: true,
  },
  experimental: {
    cpus: 1,
  },
  turbopack: {},
  webpack: (config, { dev }) => {
    if (dev) {
      // Disable webpack filesystem cache that causes 'Array buffer allocation failed'
      config.cache = false;
    }
    return config;
  },
};

export default nextConfig;
