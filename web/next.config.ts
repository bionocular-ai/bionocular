import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next 16 rule for agents lives in AGENTS.md; stop `next dev` from managing its own block.
  agentRules: false,
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
