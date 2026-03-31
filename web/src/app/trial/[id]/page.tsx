'use client';

import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

export default function TrialDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  React.useEffect(() => {
    // Legacy route kept for backwards compatibility.
    // Canonical route is `/trial/nct/[nctId]`, which reads from Supabase.
    router.replace(`/trial/nct/${encodeURIComponent(id)}`);
  }, [id, router]);

  return (
    <div className="container mx-auto py-10">
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Redirecting to trial details…</p>
        </div>
      </div>
    </div>
  );
}

