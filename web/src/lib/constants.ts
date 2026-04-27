/**
 * Application constants
 * Centralized constants to avoid magic strings and improve maintainability
 */

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  SIGNUP: '/signup',
  FORGOT_PASSWORD: '/forgot-password',
  RESET_PASSWORD: '/reset-password',
  DASHBOARD: '/dashboard',
  ANALYTICS: '/analytics',
  AGENT: '/agent',
} as const;

export const PUBLIC_ROUTES = [
  ROUTES.HOME,
  ROUTES.LOGIN,
  ROUTES.SIGNUP,
  ROUTES.FORGOT_PASSWORD,
  ROUTES.RESET_PASSWORD,
  ROUTES.ANALYTICS,
] as const;

export const AUTH_ERROR_MESSAGES = {
  INVALID_CREDENTIALS: 'Invalid email or password',
  GENERIC_ERROR: 'An error occurred. Please try again.',
  REQUIRED_FIELDS: 'Please enter both email and password',
  INVALID_EMAIL: 'Please enter a valid email address',
} as const;

