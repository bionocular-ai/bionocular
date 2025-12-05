'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { trialsApi } from '@/lib/api';
import { extractTrialMetadata, formatDate } from '@/lib/utils/trial-utils';
import { Loader2, ArrowLeft } from 'lucide-react';

export default function TrialDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { data, isLoading, error } = useQuery({
    queryKey: ['trial', id],
    queryFn: () => trialsApi.getById(id),
  });

  if (isLoading) {
    return (
      <div className="container mx-auto py-10">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-muted-foreground">Loading trial details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container mx-auto py-10">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Trial Not Found</CardTitle>
            <CardDescription>
              The trial you&apos;re looking for could not be found.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button 
              onClick={() => router.push('/dashboard')} 
              variant="outline"
              className="group border-gray-300 text-xs sm:text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20"
              aria-label="Go back to dashboard"
            >
              <ArrowLeft className="mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4 transition-transform group-hover:-translate-x-0.5 group-hover:text-primary" />
              Back to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const metadata = data.metadata || {};
  const trialData = extractTrialMetadata(data);

  return (
    <div className="container mx-auto py-10">
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button 
            onClick={() => router.push('/dashboard')} 
            variant="outline" 
            size="sm"
            className="group border-gray-300 text-xs sm:text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20"
            aria-label="Go back to dashboard"
          >
            <ArrowLeft className="mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4 transition-transform group-hover:-translate-x-0.5 group-hover:text-primary" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Trial Details</h1>
            <p className="text-muted-foreground mt-1">Detailed information about this clinical trial</p>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">NCT ID</p>
                <p className="text-lg font-semibold">{trialData.nctId}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Title</p>
                <p className="text-lg">{trialData.title}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Abstract ID</p>
                <p className="text-lg">{trialData.abstractId}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Year</p>
                <p className="text-lg">{trialData.year}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Trial Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Phase</p>
                <Badge variant="outline" className="mt-1">
                  {trialData.phase}
                </Badge>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Status</p>
                <Badge variant="secondary" className="mt-1">
                  {trialData.status}
                </Badge>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Sponsor</p>
                <p className="text-lg">{trialData.sponsor}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Cancer Type</p>
                <p className="text-lg">{trialData.cancerType}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Full Metadata</CardTitle>
            <CardDescription>Complete metadata extracted from the document</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="bg-muted p-4 rounded-md overflow-auto text-sm">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Document Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="font-medium text-muted-foreground">Document ID</p>
                <p className="font-mono text-xs">{data.id}</p>
              </div>
              <div>
                <p className="font-medium text-muted-foreground">Original Filename</p>
                <p>{data.original_filename}</p>
              </div>
              <div>
                <p className="font-medium text-muted-foreground">Type</p>
                <p>{data.type}</p>
              </div>
              <div>
                <p className="font-medium text-muted-foreground">Upload Date</p>
                <p>{formatDate(data.upload_date)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

