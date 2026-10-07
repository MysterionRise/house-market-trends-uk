import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // The Python API and static data server are separate processes; nothing to proxy here
  output: "standalone",
};

export default config;
