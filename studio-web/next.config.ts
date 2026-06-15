import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  // Pin the tracing root to this app so a stray lockfile higher in the tree
  // can't nest the standalone output under .next/standalone/studio-web/.
  outputFileTracingRoot: path.join(__dirname),
  async rewrites() {
    // In dev mode, proxy API calls to the FastAPI backend
    const apiUrl = process.env.API_URL || "http://localhost:8080";
    return [
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
      { source: "/ws/:path*", destination: `${apiUrl}/ws/:path*` },
    ];
  },
};

export default nextConfig;
