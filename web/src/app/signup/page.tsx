'use client';

import { useState, useTransition } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Mail, Lock } from 'lucide-react';
import { AuthAlert, AuthCard, AuthField, AuthSubmit, authLinkClass } from '@/components/auth/AuthCard';
import { isValidEmail, MIN_PASSWORD_LENGTH, validatePassword } from '@/lib/auth-utils';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

export default function SignupPage() {
  const router = useRouter();
  const [, startTransition] = useTransition();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (!email || !password) {
      setError('Please enter both email and password');
      return;
    }

    if (!isValidEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    const passwordValidation = validatePassword(password);
    if (!passwordValidation.valid) {
      setError(passwordValidation.error || 'Invalid password');
      return;
    }

    setIsLoading(true);

    try {
      const supabase = createClient();
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });

      if (error) {
        setError(error.message);
        setIsLoading(false);
      } else if (data.session) {
        startTransition(() => {
          router.push(ROUTES.DASHBOARD);
          router.refresh();
        });
      } else if (data.user) {
        setSuccessMsg('Account created. Check your inbox for a link to confirm your email.');
        setIsLoading(false);
      }
    } catch (err) {
      console.error('Signup error:', err);
      setError('An error occurred. Please try again.');
      setIsLoading(false);
    }
  };

  const errorId = error ? 'signup-error' : undefined;

  return (
    <AuthCard title="Create account">
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
          hint={`At least ${MIN_PASSWORD_LENGTH} characters`}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
          autoComplete="new-password"
          errorId={errorId}
        />

        {error && <AuthAlert id={errorId} tone="error">{error}</AuthAlert>}
        {successMsg && <AuthAlert tone="success">{successMsg}</AuthAlert>}

        <AuthSubmit loading={isLoading} loadingLabel="Creating account…">Create account</AuthSubmit>
      </form>

      <p className="mt-6 text-sm text-gray-600 text-center">
        Already have an account?{' '}
        <Link href={ROUTES.LOGIN} className={cn(authLinkClass, 'font-semibold')}>
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
