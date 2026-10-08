import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The container image runs the self-contained server; local dev and Vercel do not need it.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  turbopack: { root: fileURLToPath(new URL(".", import.meta.url)) },
};

export default nextConfig;
