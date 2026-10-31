'use client';

import { useState, useTransition } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import { Lock } from 'lucide-react';
import { AuthAlert, AuthCard, AuthField, AuthSubmit } from '@/components/auth/AuthCard';
import { MIN_PASSWORD_LENGTH, validatePassword } from '@/lib/auth-utils';
import { ROUTES } from '@/lib/constants';

export default function ResetPasswordPage() {
  const router = useRouter();
  const [, startTransition] = useTransition();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    const passwordValidation = validatePassword(password);
    if (!passwordValidation.valid) {
      setError(passwordValidation.error || 'Invalid password');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);

    try {
      const supabase = createClient();
      const { error } = await supabase.auth.updateUser({ password });

      if (error) {
        setError(error.message);
        setIsLoading(false);
      } else {
        startTransition(() => {
          router.push(ROUTES.DASHBOARD);
          router.refresh();
        });
      }
    } catch {
      setError('An error occurred. Please try again.');
      setIsLoading(false);
    }
  };

  const errorId = error ? 'reset-error' : undefined;

  return (
    <AuthCard title="New password">
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <AuthField
          id="password"
          label="New password"
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

        <AuthField
          id="confirm-password"
          label="Confirm new password"
          icon={Lock}
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          disabled={isLoading}
          autoComplete="new-password"
          errorId={errorId}
        />

        {error && <AuthAlert id={errorId} tone="error">{error}</AuthAlert>}

        <AuthSubmit loading={isLoading} loadingLabel="Updating…">Update password</AuthSubmit>
      </form>
    </AuthCard>
  );
}
