import { describe, expect, it, vi, beforeEach } from 'vitest';
import { NextRequest } from 'next/server';

let signedIn = false;
vi.mock('@supabase/ssr', () => ({
  createServerClient: () => ({
    auth: { getUser: async () => ({ data: { user: signedIn ? { id: 'u1' } : null } }) },
  }),
}));

import { proxy } from './proxy';

async function visit(path: string) {
  const res = await proxy(new NextRequest(`http://localhost:3000${path}`));
  return res.headers.get('location');
}

describe('proxy', () => {
  beforeEach(() => {
    signedIn = false;
  });

  it('sends signed-in users away from login and signup', async () => {
    signedIn = true;
    expect(await visit('/login')).toBe('http://localhost:3000/dashboard');
    expect(await visit('/signup')).toBe('http://localhost:3000/dashboard');
  });

  // The emailed reset link signs the user in at /auth/callback, then lands on /reset-password
  it('lets signed-in users reach the auth callback and the reset form', async () => {
    signedIn = true;
    expect(await visit('/auth/callback?code=abc&next=/reset-password')).toBeNull();
    expect(await visit('/reset-password')).toBeNull();
  });

  it('sends signed-out users from the dashboard to login with a callback', async () => {
    expect(await visit('/dashboard/melanoma')).toBe('http://localhost:3000/login?callbackUrl=%2Fdashboard%2Fmelanoma');
  });
});
