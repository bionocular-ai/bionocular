import LoginForm from './LoginForm';

// Reading searchParams on the server avoids the useSearchParams Suspense fallback flashing a placeholder card
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string | string[]; error?: string | string[] }>;
}) {
  const { callbackUrl, error } = await searchParams;
  return (
    <LoginForm
      callbackUrl={typeof callbackUrl === 'string' ? callbackUrl : undefined}
      urlError={typeof error === 'string' ? error : undefined}
    />
  );
}
