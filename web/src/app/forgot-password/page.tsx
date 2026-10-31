'use client';

import { useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import Link from 'next/link';
import { Mail } from 'lucide-react';
import { AuthAlert, AuthCard, AuthField, AuthSubmit, authLinkClass } from '@/components/auth/AuthCard';
import { isValidEmail } from '@/lib/auth-utils';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    if (!isValidEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    setIsLoading(true);

    try {
      const supabase = createClient();
      await supabase.auth.resetPasswordForEmail(email.trim(), {
        redirectTo: `${window.location.origin}/auth/callback?next=${ROUTES.RESET_PASSWORD}`,
      });
      // Always show success — never reveal whether the email exists
      setSubmitted(true);
    } catch {
      setError('An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const errorId = error ? 'forgot-error' : undefined;

  return (
    <AuthCard title="Reset password">
      {submitted ? (
        <div className="space-y-6 text-center">
          <AuthAlert tone="success">
            If an account exists for <strong>{email}</strong>, you will receive a password reset link shortly.
          </AuthAlert>
          <Link href={ROUTES.LOGIN} className={cn(authLinkClass, 'font-semibold')}>
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          <p className="text-sm text-gray-600 text-center">
            Enter your email and we&apos;ll send you a link to reset your password.
          </p>

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

          {error && <AuthAlert id={errorId} tone="error">{error}</AuthAlert>}

          <AuthSubmit loading={isLoading} loadingLabel="Sending…">Send reset link</AuthSubmit>

          <div className="text-center">
            <Link href={ROUTES.LOGIN} className={authLinkClass}>
              Back to sign in
            </Link>
          </div>
        </form>
      )}
    </AuthCard>
  );
}
