/**
 * Environment variable validation and access
 * This ensures all required environment variables are present and prevents
 * accidental exposure of secrets in the codebase
 */

function getOptionalEnvVar(key: string, defaultValue?: string): string | undefined {
  return process.env[key] || defaultValue;
}

function getRequiredEnvVar(key: string): string {
  const value = process.env[key];
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
    url: getRequiredEnvVar('NEXT_PUBLIC_SUPABASE_URL'),
    publishableKey: getRequiredEnvVar('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'),
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

