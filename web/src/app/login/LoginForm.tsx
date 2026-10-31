'use client';

import { useState, useTransition } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Mail, Lock } from 'lucide-react';
import { AuthAlert, AuthCard, AuthField, AuthSubmit, authLinkClass } from '@/components/auth/AuthCard';
import { isValidEmail } from '@/lib/auth-utils';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

export default function LoginForm({ callbackUrl, urlError }: { callbackUrl?: string; urlError?: string }) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(urlError === 'auth_callback_failed' ? 'Email confirmation failed. Please try again or contact support.' : '');
  const [isLoading, setIsLoading] = useState(false);

  // Validate callback URL to prevent open redirects
  const safeCallbackUrl = callbackUrl?.startsWith('/') && !callbackUrl.startsWith('//')
    ? callbackUrl
    : ROUTES.DASHBOARD;

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    // Client-side validation
    if (!email || !password) {
      setError('Please enter both email and password');
      return;
    }

    if (!isValidEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    setIsLoading(true);

    try {
      const supabase = createClient();
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });

      if (error) {
        if (error.code === 'email_not_confirmed') {
          setError('Please confirm your email address before signing in. Check your inbox.');
        } else {
          setError('Invalid email or password');
        }
        setIsLoading(false);
      } else if (data.session) {
        // Use startTransition for navigation to avoid blocking
        startTransition(() => {
          router.push(safeCallbackUrl);
          router.refresh();
        });
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('An error occurred. Please try again.');
      setIsLoading(false);
    }
  };

  const errorId = error ? 'login-error' : undefined;

  return (
    <AuthCard title="Welcome back">
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <AuthField
          id="email"
          label="Email"
          icon={Mail}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={isLoading}
          autoComplete="email"
          errorId={errorId}
        />

        <AuthField
          id="password"
          label="Password"
          icon={Lock}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
          autoComplete="current-password"
          errorId={errorId}
        />

        {error && <AuthAlert id={errorId} tone="error">{error}</AuthAlert>}

        <AuthSubmit loading={isLoading} loadingLabel="Signing in…">Sign in</AuthSubmit>
      </form>

      <div className="mt-6 space-y-4 text-center">
        <Link href={ROUTES.FORGOT_PASSWORD} className={authLinkClass}>
          Forgot password?
        </Link>
        <p className="text-sm text-gray-600">
          Don&apos;t have an account?{' '}
          <Link href={ROUTES.SIGNUP} className={cn(authLinkClass, 'font-semibold')}>
            Create account
          </Link>
        </p>
      </div>
    </AuthCard>
  );
}
