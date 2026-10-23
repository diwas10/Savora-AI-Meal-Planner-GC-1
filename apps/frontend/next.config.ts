import type { NextConfig } from "next";

// FastAPI, reached through this server so the session cookie is first-party. Read when
// the app is built (rewrites are compiled into the build).
const API_ORIGIN = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  async redirects() {
    // The craving screen is now the Discover tab (SCREENS.md).
    return [{ source: "/craving", destination: "/discover", permanent: true }];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
};

export default nextConfig;
