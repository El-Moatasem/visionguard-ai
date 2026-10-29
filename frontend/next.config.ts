import type { NextConfig } from "next";

// Same-origin proxy keeps phone and desktop clients independent of localhost:8000.
// BACKEND_URL is read by Next.js on the SERVER (not bundled into the browser).
const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/backend/:path*", destination: `${backend}/api/v1/:path*` }];
  },
};
export default nextConfig;
