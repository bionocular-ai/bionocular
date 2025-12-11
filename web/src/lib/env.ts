/**
 * Environment variable validation and access
 * This ensures all required environment variables are present and prevents
 * accidental exposure of secrets in the codebase
 */

function getOptionalEnvVar(key: string, defaultValue?: string): string | undefined {
  return process.env[key] || defaultValue;
}

/**
 * Validated environment configuration
 * Access environment variables through this object to ensure type safety
 */
// Helper to get AUTH_SECRET with proper fallback
function getAuthSecret(): string {
  const secret = getOptionalEnvVar('AUTH_SECRET') || getOptionalEnvVar('NEXTAUTH_SECRET');
  
  if (secret) {
    return secret;
  }
  
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'AUTH_SECRET is required in production. ' +
      'Please set AUTH_SECRET in your environment variables. ' +
      'Generate one with: openssl rand -base64 32'
    );
  }
  
  // For development, generate a warning but allow a fallback
  console.warn(
    '⚠️  AUTH_SECRET not set. Using a temporary secret for development. ' +
    'Set AUTH_SECRET in .env.local for production.'
  );
  return 'temporary-dev-secret-change-in-production';
}

export const env = {
  // NextAuth configuration
  auth: {
    secret: getAuthSecret(),
  },
  
  // API configuration
  api: {
    url: getOptionalEnvVar('NEXT_PUBLIC_API_URL', 'http://localhost:8000'),
  },
  
  // Application environment
  nodeEnv: getOptionalEnvVar('NODE_ENV', 'development') as 'development' | 'production' | 'test',
  
  // Demo credentials (only for development)
  demo: {
    email: getOptionalEnvVar('DEMO_EMAIL', 'demo@bionocular.ai'),
    password: getOptionalEnvVar('DEMO_PASSWORD', 'demo123'),
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

