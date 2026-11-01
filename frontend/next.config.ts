import type { NextConfig } from "next";

// Backend URL is server-side only. Never expose MODEL_API_KEY to the frontend.
const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  experimental: { proxyClientMaxBodySize: "110mb" },
  async rewrites() {
    return [{ source: "/api/backend/:path*", destination: `${backend}/api/v1/:path*` }];
  },
};
export default nextConfig;
