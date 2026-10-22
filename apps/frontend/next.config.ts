import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
