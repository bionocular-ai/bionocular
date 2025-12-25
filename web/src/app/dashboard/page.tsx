'use client';

import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { UserMenu } from '@/components/user-menu';
import { ArrowRight } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

const SKIN_CANCER_CATEGORIES = [
  'Basal Cell Carcinoma',
  'Cutaneous Squamous Cell Carcinoma',
  'Cutaneous melanoma',
  'Uveal Melanoma',
  'Merkel Cell Carcinoma',
  'Acral Melanoma',
  'Mucosal Melanoma',
  'Cutaneous melanoma with Brain/CNS metastasis',
] as const;

// Mapping of category names to slugs for consistent URL generation
const CATEGORY_SLUG_MAP: Record<string, string> = {
  'Cutaneous melanoma': 'cutaneous-melanoma',
  'Cutaneous melanoma with Brain/CNS metastasis': 'cutaneous-melanoma-with-brain-cns-metastasis',
  'Uveal Melanoma': 'uveal-melanoma',
  'Mucosal Melanoma': 'mucosal-melanoma',
  'Acral Melanoma': 'acral-melanoma',
  'Basal Cell Carcinoma': 'basal-cell-carcinoma',
  'Merkel Cell Carcinoma': 'merkel-cell-carcinoma',
  'Cutaneous Squamous Cell Carcinoma': 'cutaneous-squamous-cell-carcinoma',
};

// Helper function to create URL-friendly slug from category name
function categoryToSlug(category: string): string {
  return CATEGORY_SLUG_MAP[category] || category
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

export default function CategoriesPage() {
  const { data: session } = useSession();

  return (
    <div className="flex flex-col min-h-screen w-full bg-white">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shrink-0">
        <div className="w-full px-3 sm:px-4 md:px-6">
          <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
            <Link href="/" className="brand flex-shrink-0">
              <div className="relative flex items-center" style={{ height: '37px', flexShrink: 0, background: 'transparent' }}>
                <Image
                  src="/logo.png"
                  alt="Bionocular Logo"
                  width={37}
                  height={37}
                  className="object-contain"
                  priority
                  unoptimized
                  style={{ height: '37px', width: 'auto', background: 'transparent' }}
                />
              </div>
              <span className="brand-text" style={{ lineHeight: '1.2' }}>
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
              {session?.user && (
                <UserMenu
                  email={session.user.email || null}
                  name={session.user.name || null}
                  image={undefined}
                />
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-gradient-to-b from-gray-50 via-white to-gray-50">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 max-w-6xl">
          {/* Page Header */}
          <div className="mb-6 sm:mb-8 text-center">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900 mb-2 tracking-tight">
              Skin Cancer Categories
            </h1>
            <p className="text-sm sm:text-base text-gray-600 max-w-2xl mx-auto">
              Select a category to view clinical results from these cancer types
            </p>
          </div>

          {/* Categories Grid - 2 columns layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4 lg:gap-5">
            {SKIN_CANCER_CATEGORIES.map((category) => {
              const slug = categoryToSlug(category);
              return (
                <Link
                  key={category}
                  href={`/dashboard/${slug}`}
                  className="group block"
                >
                  <Card className="h-full transition-all duration-200 hover:shadow-lg hover:shadow-primary/5 hover:border-primary/60 hover:-translate-y-0.5 cursor-pointer flex flex-col border-2 bg-white relative overflow-hidden">
                    {/* Subtle gradient overlay on hover */}
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/0 to-primary/0 group-hover:from-primary/5 group-hover:to-transparent transition-all duration-200 pointer-events-none" />
                    
                    <CardHeader className="flex-1 pb-3 pt-4 px-5 relative z-10">
                      <CardTitle className="text-base sm:text-lg font-semibold text-gray-900 group-hover:text-primary transition-colors leading-snug">
                        {category}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0 px-5 pb-4 relative z-10">
                      <div className="flex items-center justify-between">
                        <CardDescription className="text-xs sm:text-sm text-gray-500 group-hover:text-gray-600 transition-colors font-medium">
                          View clinical trials
                        </CardDescription>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400 group-hover:text-primary transition-colors hidden sm:inline">
                            Explore
                          </span>
                          <ArrowRight className="h-4 w-4 text-gray-400 group-hover:text-primary group-hover:translate-x-0.5 transition-all flex-shrink-0" />
                        </div>
                      </div>
                    </CardContent>
                    
                    {/* Decorative accent line */}
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-primary/0 via-primary/0 to-primary/0 group-hover:from-primary/50 group-hover:via-primary group-hover:to-primary/50 transition-all duration-200" />
                  </Card>
                </Link>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
