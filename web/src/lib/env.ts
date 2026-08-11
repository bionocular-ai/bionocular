/**
 * Environment variable validation and access
 * This ensures all required environment variables are present and prevents
 * accidental exposure of secrets in the codebase
 */

function getOptionalEnvVar(key: string, defaultValue?: string): string | undefined {
  return process.env[key] || defaultValue;
}

/**
 * IMPORTANT (Next.js): For browser bundles, `NEXT_PUBLIC_*` vars are replaced at build time.
 * Dynamic access like `process.env[key]` won't be inlined and will be `undefined` in the client.
 * Use direct property access for any env var that must work in the browser.
 */
function getRequiredPublicEnvVar(key: 'NEXT_PUBLIC_SUPABASE_URL' | 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'): string {
  const value =
    key === 'NEXT_PUBLIC_SUPABASE_URL'
      ? process.env.NEXT_PUBLIC_SUPABASE_URL
      : process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (value) return value;
  throw new Error(`Missing required environment variable: ${key}`);
}

/**
 * Validated environment configuration
 * Access environment variables through this object to ensure type safety
 */
export const env = {
  // Application environment
  nodeEnv: getOptionalEnvVar('NODE_ENV', 'development') as 'development' | 'production' | 'test',

  // Supabase (public; safe to expose to browser because of NEXT_PUBLIC_)
  supabase: {
    url: getRequiredPublicEnvVar('NEXT_PUBLIC_SUPABASE_URL'),
    publishableKey: getRequiredPublicEnvVar('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'),
  },
} as const;

/**
 * Check if we're in development mode
 */
export const isDevelopment = env.nodeEnv === 'development';

/**
 * Check if we're in production mode
 */
export const isProduction = env.nodeEnv === 'production';

/**
 * Server-only environment variables.
 *
 * Lazy access — only call from server code (route handlers, server components, server actions).
 * Throws at call time if the var is missing, so importing this module in a client bundle is safe.
 */
function requireServerEnv(key: string): string {
  const value = process.env[key];
  if (!value) throw new Error(`Missing required server env var: ${key}`);
  return value;
}

export function getServerEnv() {
  return {
    supabaseSecretKey: requireServerEnv('SUPABASE_SECRET_KEY'),
  };
}

