import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
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
