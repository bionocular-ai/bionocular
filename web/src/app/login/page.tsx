'use client';

import { useState, useTransition } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter, useSearchParams } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Mail, Lock } from 'lucide-react';
import { isValidEmail, validatePassword } from '@/lib/auth-utils';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get('callbackUrl') || '/dashboard';
  const [isPending, startTransition] = useTransition();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Validate callback URL to prevent open redirects
  const safeCallbackUrl = callbackUrl.startsWith('/') && !callbackUrl.startsWith('//')
    ? callbackUrl
    : '/dashboard';

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

    const passwordValidation = validatePassword(password);
    if (!passwordValidation.valid) {
      setError(passwordValidation.error || 'Invalid password');
      return;
    }

    setIsLoading(true);

    try {
      const result = await signIn('credentials', {
        email: email.trim(),
        password,
        redirect: false,
      });

      if (result?.error) {
        // Generic error message to prevent user enumeration
        setError('Invalid email or password');
        setIsLoading(false);
      } else if (result?.ok) {
        // Use startTransition for navigation to avoid blocking
        startTransition(() => {
          router.push(safeCallbackUrl);
          router.refresh();
        });
      } else {
        setError('An unexpected error occurred. Please try again.');
        setIsLoading(false);
      }
    } catch (err) {
      // Log error but show generic message to user
      console.error('Login error:', err);
      setError('An error occurred. Please try again.');
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-sky-50 to-blue-100 p-4 relative overflow-hidden">
      {/* Wave pattern background */}
      <div className="absolute inset-0 opacity-30">
        <svg className="absolute top-0 left-0 w-full h-full" viewBox="0 0 1200 800" preserveAspectRatio="none">
          <path
            d="M0,200 Q300,150 600,200 T1200,200 L1200,800 L0,800 Z"
            fill="url(#wave-gradient)"
            className="opacity-50"
          />
          <path
            d="M0,300 Q400,250 800,300 T1200,300 L1200,800 L0,800 Z"
            fill="url(#wave-gradient)"
            className="opacity-30"
          />
          <defs>
            <linearGradient id="wave-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#1A73E8" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#1A73E8" stopOpacity="0.1" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <Card className="w-full max-w-md shadow-2xl border-0 bg-white rounded-2xl relative z-10">
        <CardHeader className="pb-8 pt-10">
          <div className="flex justify-center mb-1">
            <div className="relative w-32 h-32">
              <Image
                src="/logo.png"
                alt="Bionocular Logo"
                fill
                className="object-contain"
                priority
              />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-center -mt-1" style={{ color: '#1A73E8' }}>
            Welcome Back
          </h1>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="p-3.5 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg">
                {error}
              </div>
            )}
            
            <div className="relative">
              <div className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: '#1A73E8' }}>
                <Mail className="h-5 w-5" />
              </div>
              <Input
                id="email"
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
                autoComplete="email"
                className="h-12 pl-11 rounded-lg border-gray-300 focus:border-[#1A73E8] focus:ring-[#1A73E8]"
              />
            </div>
            
            <div className="relative">
              <div className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: '#1A73E8' }}>
                <Lock className="h-5 w-5" />
              </div>
              <Input
                id="password"
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
                autoComplete="current-password"
                className="h-12 pl-11 rounded-lg border-gray-300 focus:border-[#1A73E8] focus:ring-[#1A73E8]"
              />
            </div>

            <Button
              type="submit"
              className="w-full h-12 text-base font-semibold rounded-lg text-white shadow-md hover:shadow-lg transition-all hover:opacity-90"
              style={{ backgroundColor: '#1A73E8' }}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Login'
              )}
            </Button>
          </form>

          <div className="mt-6 space-y-4 text-center">
            <Link
              href="/forgot-password"
              className="text-sm hover:underline block hover:opacity-80 transition-opacity"
              style={{ color: '#1A73E8' }}
            >
              Forgot Password?
            </Link>
            <p className="text-sm text-gray-600">
              Don't have an account?{' '}
              <Link
                href="/signup"
                className="font-semibold hover:underline hover:opacity-80 transition-opacity"
                style={{ color: '#1A73E8' }}
              >
                Sign Up
              </Link>
            </p>
          </div>

          {process.env.NODE_ENV === 'development' && (
            <div className="mt-6 p-3 rounded-lg border" style={{ backgroundColor: 'rgba(26, 115, 232, 0.05)', borderColor: 'rgba(26, 115, 232, 0.2)' }}>
              <p className="text-xs text-gray-600 text-center">
                <strong className="font-semibold" style={{ color: '#1A73E8' }}>Demo credentials (development only):</strong>
                <br />
                Check your .env.local file for demo credentials
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

