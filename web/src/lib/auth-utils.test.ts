import { describe, expect, it, vi } from 'vitest';

// env.ts throws without Supabase env vars; pin production mode
vi.mock('./env', () => ({ isDevelopment: false }));

import { MIN_PASSWORD_LENGTH, validatePassword } from './auth-utils';

describe('validatePassword', () => {
  it('requires 8 characters in production', () => {
    expect(MIN_PASSWORD_LENGTH).toBe(8);
  });

  it('rejects an empty password', () => {
    expect(validatePassword('')).toEqual({ valid: false, error: 'Password is required' });
  });

  it('rejects one character short of the minimum, naming the minimum', () => {
    expect(validatePassword('a'.repeat(7))).toEqual({
      valid: false,
      error: 'Password must be at least 8 characters',
    });
  });

  it('accepts a password at the minimum', () => {
    expect(validatePassword('a'.repeat(8))).toEqual({ valid: true });
  });
});
