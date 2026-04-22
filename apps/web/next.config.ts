import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  transpilePackages: ["@bidforge/web-sdk"],
  turbopack: {
    root: path.join(__dirname, "../.."),
  },
  async rewrites() {
    const target = process.env.API_PROXY_TARGET?.trim();
    if (!target) return [];
    const base = target.replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${base}/api/:path*` }];
  },
};

export default nextConfig;
