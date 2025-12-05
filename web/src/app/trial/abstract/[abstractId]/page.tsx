'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { UserMenu } from '@/components/user-menu';
import { trialsApi } from '@/lib/api';
import { extractAbstractDetails } from '@/lib/utils/trial-utils';
import { Loader2, ArrowLeft, ExternalLink, Eye, MoreVertical, LayoutGrid, ChevronDown, ChevronUp } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { organizeAttributesBySection } from '@/lib/utils/trial-utils';
import { AbstractTimeline } from '@/components/timeline/AbstractTimeline';

// Header component moved outside to avoid re-creation on render
interface HeaderProps {
  session: { user?: { email?: string | null; name?: string | null } } | null;
  onNavigateToDashboard: () => void;
}

function Header({ session, onNavigateToDashboard }: HeaderProps) {
  return (
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
            <Button
              variant="outline"
              size="sm"
              onClick={onNavigateToDashboard}
              className="group border-gray-300 text-xs sm:text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20"
              aria-label="Navigate to main categories"
            >
              <LayoutGrid className="h-3.5 w-3.5 sm:mr-1.5 transition-colors group-hover:text-primary" />
              <span className="hidden sm:inline">Categories</span>
              <span className="sm:hidden">Main</span>
            </Button>
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
  );
}

export default function AbstractDetailPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const abstractId = params.abstractId as string;
  const [expandedSections, setExpandedSections] = React.useState<string[]>([]);
  const [isAllExpanded, setIsAllExpanded] = React.useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['abstract', abstractId],
    queryFn: () => trialsApi.getByAbstractId(abstractId),
  });

  const handleNavigateToDashboard = React.useCallback(() => {
    router.push('/dashboard');
  }, [router]);

  if (isLoading) {
    return (
      <div className="flex flex-col min-h-screen w-full bg-gray-50">
        <Header session={session} onNavigateToDashboard={handleNavigateToDashboard} />
        <main className="flex-1 overflow-auto bg-gray-50">
          <div className="container mx-auto py-10">
            <div className="flex items-center justify-center min-h-[400px]">
              <div className="flex flex-col items-center gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-muted-foreground">Loading abstract details...</p>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col min-h-screen w-full bg-gray-50">
        <Header session={session} onNavigateToDashboard={handleNavigateToDashboard} />
        <main className="flex-1 overflow-auto bg-gray-50">
          <div className="container mx-auto py-10">
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <h2 className="text-xl font-semibold text-destructive mb-2">Abstract Not Found</h2>
                  <p className="text-muted-foreground mb-4">
                    The abstract you&apos;re looking for could not be found.
                  </p>
                  <Button 
                    onClick={() => router.push('/dashboard')} 
                    variant="outline"
                    className="group border-gray-300 text-xs sm:text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20"
                  >
                    <ArrowLeft className="mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4 transition-transform group-hover:-translate-x-0.5" />
                    Go to Dashboard
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    );
  }

  const details = extractAbstractDetails(data);

  if (!details) {
    return (
      <div className="flex flex-col min-h-screen w-full bg-gray-50">
        <Header session={session} onNavigateToDashboard={handleNavigateToDashboard} />
        <main className="flex-1 overflow-auto bg-gray-50">
          <div className="container mx-auto py-10">
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <h2 className="text-xl font-semibold text-destructive mb-2">Invalid Abstract Data</h2>
                  <p className="text-muted-foreground mb-4">
                    Unable to parse abstract data.
                  </p>
                  <Button 
                    onClick={() => router.push('/dashboard')} 
                    variant="outline"
                    className="group border-gray-300 text-xs sm:text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20"
                  >
                    <ArrowLeft className="mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4 transition-transform group-hover:-translate-x-0.5" />
                    Go to Dashboard
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    );
  }

  const conferenceBadge = details.conference && details.year 
    ? `${details.conference} ${details.year}` 
    : details.conference || '';

  return (
    <div className="flex flex-col min-h-screen w-full bg-gray-50">
      <Header session={session} onNavigateToDashboard={handleNavigateToDashboard} />

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <div className="container mx-auto max-w-7xl py-8 px-4 sm:px-6 lg:px-8">
          {/* Back Button */}
          <div className="mb-6">
            <Button 
              onClick={() => {
                // Navigate to NCT page if we have NCT number, otherwise go back
                if (details.nctNumber) {
                  router.push(`/trial/nct/${details.nctNumber}`);
                } else {
                  router.back();
                }
              }}
              variant="outline" 
              size="sm"
              className="group border-gray-300 text-sm text-gray-700 font-medium transition-all duration-200 hover:border-primary hover:bg-blue-50 hover:text-primary"
            >
              <ArrowLeft className="mr-2 h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
              Back
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Main Content */}
            <div className="lg:col-span-2 space-y-6">
              {/* Header Card */}
              <Card className="border-gray-200 shadow-sm">
                <CardHeader className="pb-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-3">
                        {conferenceBadge && (
                          <Badge 
                            variant="secondary" 
                            className="text-xs font-semibold px-3 py-1"
                          >
                            {conferenceBadge}
                          </Badge>
                        )}
                        {details.phase && (
                          <Badge 
                            variant="outline" 
                            className="bg-blue-50 text-blue-700 border-blue-200 text-xs font-medium"
                          >
                            Phase {details.phase}
                          </Badge>
                        )}
                        {details.status && details.status !== 'Unknown' && (
                          <Badge 
                            variant="outline" 
                            className="bg-green-50 text-green-700 border-green-200 text-xs font-medium"
                          >
                            {details.status}
                          </Badge>
                        )}
                      </div>
                      <CardTitle className="text-2xl font-bold text-gray-900 leading-tight mb-2">
                        {details.title || 'Untitled Abstract'}
                      </CardTitle>
                      {details.nctNumber && (
                        <CardDescription className="flex items-center gap-2 mt-2">
                          <Link
                            href={`/trial/nct/${details.nctNumber}`}
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                          >
                            {details.nctNumber}
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Link>
                          {details.abstractId && (
                            <>
                              <span className="text-gray-400">•</span>
                              <span className="text-sm text-gray-600 font-mono">
                                #{details.abstractId}
                              </span>
                            </>
                          )}
                        </CardDescription>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="icon" className="h-9 w-9">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-9 w-9">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Key Information Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Sponsor */}
                    {details.sponsor && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Sponsor</p>
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-semibold text-sm shadow-sm">
                            {details.sponsor.charAt(0).toUpperCase()}
                          </div>
                          <p className="text-sm font-medium text-gray-900">{details.sponsor}</p>
                        </div>
                      </div>
                    )}


                    {/* Treatment */}
                    {details.treatment && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Treatment</p>
                        <p className="text-sm font-medium text-gray-900">{details.treatment}</p>
                      </div>
                    )}

                    {/* Indication */}
                    {details.indication && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Indication</p>
                        <p className="text-sm font-medium text-gray-900">{details.indication}</p>
                      </div>
                    )}

                    {/* Line of Therapy */}
                    {details.lineOfTherapy && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Line of Therapy</p>
                        <p className="text-sm font-medium text-gray-900">{details.lineOfTherapy}</p>
                      </div>
                    )}

                    {/* Target */}
                    {details.target && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Target</p>
                        <p className="text-sm font-medium text-gray-900">{details.target}</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Complete Information Card */}
              {details.armResults && Object.keys(details.armResults).length > 0 && (() => {
                const organizedSections = organizeAttributesBySection(details.armResults);
                const sectionOrder = [
                  'Trial Information',
                  'Trial Design',
                  'Disease & Population',
                  'Sponsor',
                  'Endpoints',
                  'Treatment',
                  'Patient Demographics',
                  'Results',
                  'Other'
                ];
                const allSections = [
                  ...sectionOrder.filter(s => organizedSections[s]),
                  ...Object.keys(organizedSections).filter(s => !sectionOrder.includes(s) && organizedSections[s])
                ];
                
                return (
                <Card className="border-gray-300 shadow-md bg-white">
                  <CardHeader className="bg-gradient-to-r from-gray-50 to-white border-b border-gray-200 pb-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <CardTitle className="text-xl font-bold text-gray-900">Complete Information</CardTitle>
                        <CardDescription className="text-sm text-gray-600 mt-1">All extracted attributes and data points</CardDescription>
                      </div>
                      <div className="flex items-center gap-2 pt-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (isAllExpanded) {
                              setExpandedSections([]);
                              setIsAllExpanded(false);
                            } else {
                              setExpandedSections(allSections);
                              setIsAllExpanded(true);
                            }
                          }}
                          className="h-9 px-3 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 transition-all duration-200 rounded-md"
                        >
                          {isAllExpanded ? (
                            <>
                              <ChevronUp className="h-4 w-4 mr-1.5 transition-transform" />
                              <span>Collapse All</span>
                            </>
                          ) : (
                            <>
                              <ChevronDown className="h-4 w-4 mr-1.5 transition-transform" />
                              <span>Expand All</span>
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="bg-white pt-6">
                    {(() => {
                      type NestedSectionData = { Efficacy?: Record<string, string>; Safety?: Record<string, string> };
                      type SectionDataType = Record<string, string> | NestedSectionData;
                      
                      // Helper function to check if section data is nested (Results with Efficacy/Safety)
                      const isNestedSection = (sectionData: SectionDataType): sectionData is NestedSectionData => {
                        return sectionData && typeof sectionData === 'object' && 
                               ('Efficacy' in sectionData || 'Safety' in sectionData);
                      };
                      
                      // Helper function to count total attributes in nested section
                      const countNestedAttributes = (sectionData: SectionDataType): number => {
                        if (!isNestedSection(sectionData)) return 0;
                        const efficacyCount = sectionData.Efficacy ? Object.keys(sectionData.Efficacy).length : 0;
                        const safetyCount = sectionData.Safety ? Object.keys(sectionData.Safety).length : 0;
                        return efficacyCount + safetyCount;
                      };
                      
                      return (
                    <Accordion 
                      type="multiple" 
                      className="w-full space-y-2"
                      value={expandedSections}
                      onValueChange={(value) => {
                        setExpandedSections(value);
                        setIsAllExpanded(value.length === allSections.length);
                      }}
                    >
                      {sectionOrder.map((sectionName) => {
                        const sectionData = organizedSections[sectionName];
                        if (!sectionData) return null;
                        
                        // Handle nested Results section
                        if (sectionName === 'Results' && isNestedSection(sectionData)) {
                          const totalCount = countNestedAttributes(sectionData);
                          if (totalCount === 0) return null;
                          
                          return (
                            <AccordionItem key={sectionName} value={sectionName} className="border border-gray-200 rounded-lg bg-white shadow-sm mb-2">
                              <AccordionTrigger className="text-sm font-semibold text-gray-900 hover:no-underline py-4 px-4 hover:bg-gray-50 rounded-t-lg">
                                {sectionName} ({totalCount})
                              </AccordionTrigger>
                              <AccordionContent className="pt-4 pb-4 px-4 bg-gray-50/30">
                                <div className="space-y-6">
                                  {/* Efficacy Sub-section - Always show */}
                                  <div>
                                    <h4 className="text-sm font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
                                      Efficacy ({sectionData.Efficacy ? Object.keys(sectionData.Efficacy).length : 0})
                                    </h4>
                                    {sectionData.Efficacy && Object.keys(sectionData.Efficacy).length > 0 ? (
                                      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
                                        <table className="w-full border-collapse">
                                          <thead>
                                            <tr className="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                                              <th className="text-left py-3 px-5 text-xs font-semibold text-gray-700 uppercase tracking-wider">Attribute</th>
                                              <th className="text-left py-3 px-5 text-xs font-semibold text-gray-700 uppercase tracking-wider">Value</th>
                                            </tr>
                                          </thead>
                                          <tbody className="bg-white divide-y divide-gray-100">
                                            {Object.entries(sectionData.Efficacy).map(([key, value]) => (
                                              <tr key={key} className="hover:bg-blue-50/50 transition-colors duration-150">
                                                <td className="py-3 px-5 text-sm font-medium text-gray-700 whitespace-nowrap">{key}</td>
                                                <td className="py-3 px-5 text-sm text-gray-900 break-words">{String(value)}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      </div>
                                    ) : (
                                      <div className="rounded-lg border border-gray-200 bg-gray-50 py-6 px-4 text-center">
                                        <p className="text-sm text-gray-500">No efficacy data available</p>
                                      </div>
                                    )}
                                  </div>
                                  
                                  {/* Safety Sub-section - Always show */}
                                  <div>
                                    <h4 className="text-sm font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
                                      Safety ({sectionData.Safety ? Object.keys(sectionData.Safety).length : 0})
                                    </h4>
                                    {sectionData.Safety && Object.keys(sectionData.Safety).length > 0 ? (
                                      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
                                        <table className="w-full border-collapse">
                                          <thead>
                                            <tr className="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                                              <th className="text-left py-3 px-5 text-xs font-semibold text-gray-700 uppercase tracking-wider">Attribute</th>
                                              <th className="text-left py-3 px-5 text-xs font-semibold text-gray-700 uppercase tracking-wider">Value</th>
                                            </tr>
                                          </thead>
                                          <tbody className="bg-white divide-y divide-gray-100">
                                            {Object.entries(sectionData.Safety).map(([key, value]) => (
                                              <tr key={key} className="hover:bg-blue-50/50 transition-colors duration-150">
                                                <td className="py-3 px-5 text-sm font-medium text-gray-700 whitespace-nowrap">{key}</td>
                                                <td className="py-3 px-5 text-sm text-gray-900 break-words">{String(value)}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      </div>
                                    ) : (
                                      <div className="rounded-lg border border-gray-200 bg-gray-50 py-6 px-4 text-center">
                                        <p className="text-sm text-gray-500">No safety data available</p>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </AccordionContent>
                            </AccordionItem>
                          );
                        }
                        
                        // Handle regular flat sections
                        if (Object.keys(sectionData).length === 0) return null;
                        
                        return (
                          <AccordionItem key={sectionName} value={sectionName} className="border border-gray-200 rounded-lg bg-white shadow-sm mb-2">
                            <AccordionTrigger className="text-sm font-semibold text-gray-900 hover:no-underline py-4 px-4 hover:bg-gray-50 rounded-t-lg">
                              {sectionName} ({Object.keys(sectionData).length})
                            </AccordionTrigger>
                            <AccordionContent className="pt-4 pb-4 px-4 bg-gray-50/30">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {Object.entries(sectionData).map(([key, value]) => (
                                  <div key={key} className="space-y-1 bg-white p-3 rounded border border-gray-100">
                                    <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">{key}</p>
                                    <p className="text-sm text-gray-900 break-words font-medium">{String(value)}</p>
                                  </div>
                                ))}
                              </div>
                            </AccordionContent>
                          </AccordionItem>
                        );
                      })}
                      
                      {/* Show any sections not in the predefined order */}
                      {Object.keys(organizedSections).filter(s => !sectionOrder.includes(s)).map((sectionName) => {
                        const sectionData = organizedSections[sectionName];
                        if (!sectionData || Object.keys(sectionData).length === 0) return null;
                        
                        return (
                          <AccordionItem key={sectionName} value={sectionName} className="border border-gray-200 rounded-lg bg-white shadow-sm mb-2">
                            <AccordionTrigger className="text-sm font-semibold text-gray-900 hover:no-underline py-4 px-4 hover:bg-gray-50 rounded-t-lg">
                              {sectionName} ({Object.keys(sectionData).length})
                            </AccordionTrigger>
                            <AccordionContent className="pt-4 pb-4 px-4 bg-gray-50/30">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {Object.entries(sectionData).map(([key, value]) => (
                                  <div key={key} className="space-y-1 bg-white p-3 rounded border border-gray-100">
                                    <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">{key}</p>
                                    <p className="text-sm text-gray-900 break-words font-medium">{String(value)}</p>
                                  </div>
                                ))}
                              </div>
                            </AccordionContent>
                          </AccordionItem>
                        );
                      })}
                    </Accordion>
                      );
                    })()}
                  </CardContent>
                </Card>
                );
              })()}
            </div>
            
            {/* Right Column - Timeline */}
            {details.nctNumber && (
              <div className="lg:col-span-1">
                <AbstractTimeline 
                  nctId={details.nctNumber} 
                  currentAbstractId={details.abstractId}
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

