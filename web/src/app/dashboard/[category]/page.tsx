'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function CategoryPage() {
  const router = useRouter();
  const params = useParams();
  const categorySlug = params?.category as string;
  
  useEffect(() => {
    router.replace(`/dashboard/${categorySlug}/disease-landscape`);
  }, [router, categorySlug]);

  return null;
}
