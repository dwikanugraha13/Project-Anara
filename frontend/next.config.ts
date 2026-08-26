import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable StrictMode to prevent double WebSocket connections in dev
  reactStrictMode: false,
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
