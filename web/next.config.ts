import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next 16 rule for agents lives in AGENTS.md; stop `next dev` from managing its own block.
  agentRules: false,
  turbopack: {
    root: path.resolve(__dirname),
  },
  // The agent reads its SKILL.md files from disk at request time; the
  // standalone output only carries what tracing finds, and a readFileSync on a
  // joined path is not something it can see.
  outputFileTracingIncludes: {
    '/api/agent/chat': ['./src/lib/agent/skills/**/*.md'],
  },
};

export default nextConfig;
