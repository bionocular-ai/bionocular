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
import { Loader2, ExternalLink, Eye, MoreVertical, ChevronDown, ChevronUp } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { BackNav } from '@/components/nav/BackNav';
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
}

function Header({ session }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50 shrink-0">
      <div className="w-full px-3 sm:px-4 md:px-6">
        <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
          <Link href="/" className="brand flex-shrink-0">
              <Logo height={32} />
            <span className="brand-text" style={{ lineHeight: '1.2' }}>
              bi<span className="brand-o">o</span>nocular
            </span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
            <DashboardNavLink />
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
  
  // Get category from URL search params to pass along to NCT page
  const [category, setCategory] = React.useState<string | null>(null);
  
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const searchParams = new URLSearchParams(window.location.search);
      setCategory(searchParams.get('category'));
    }
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ['abstract', abstractId],
    queryFn: () => trialsApi.getByAbstractId(abstractId),
  });

  if (isLoading) {
    return (
      <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
        <Header session={session} />
        <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
          <div className="w-full max-w-[1600px] mx-auto px-4 py-10 sm:px-6 md:px-6">
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
      <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
        <Header session={session} />
        <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
          <div className="w-full max-w-[1600px] mx-auto px-4 py-10 sm:px-6 md:px-6">
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <h2 className="text-xl font-semibold text-destructive mb-2">Abstract Not Found</h2>
                  <p className="text-muted-foreground mb-4">
                    The abstract you&apos;re looking for could not be found.
                  </p>
                  <BackNav href="/dashboard" label="Go to dashboard" className="inline-flex" />
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
      <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
        <Header session={session} />
        <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
          <div className="w-full max-w-[1600px] mx-auto px-4 py-10 sm:px-6 md:px-6">
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <h2 className="text-xl font-semibold text-destructive mb-2">Invalid Abstract Data</h2>
                  <p className="text-muted-foreground mb-4">
                    Unable to parse abstract data.
                  </p>
                  <BackNav href="/dashboard" label="Go to dashboard" className="inline-flex" />
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
    <div className="flex flex-col min-h-screen w-full min-w-0 overflow-x-hidden bg-white">
      <Header session={session} />

      {/* Page title strip: Back + context (distinct from nav and content) */}
      <div className="border-b border-gray-200 bg-gray-50 px-3 sm:px-4 md:px-6 py-4">
        <BackNav
          onClick={() => {
            if (details.nctNumber) {
              const nctUrl = category
                ? `/trial/nct/${details.nctNumber}?category=${category}`
                : `/trial/nct/${details.nctNumber}`;
              router.push(nctUrl);
            } else {
              router.back();
            }
          }}
          label={details.nctNumber ? 'Back to trial' : 'Back'}
        />
      </div>

      {/* Main Content */}
      <main className="flex-1 min-w-0 overflow-auto bg-gray-100">
        <div className="w-full min-w-0 max-w-[1600px] mx-auto px-4 py-5 sm:px-5 sm:py-6 md:px-6 md:py-6">
          <div className="pb-8 sm:pb-10 flex min-w-0 flex-col xl:flex-row xl:items-start xl:gap-8 2xl:gap-10 gap-6">
            {/* Left Column - Main Content */}
            <div className="xl:order-1 flex-1 min-w-0 basis-0 space-y-2">
              {/* Section 1: Trial summary */}
              <Card className="bg-white border border-gray-200 shadow-sm rounded-md overflow-hidden">
                <CardHeader className="pb-5 pt-6 px-5 sm:px-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-4">
                        {conferenceBadge && (
                          <Badge 
                            variant="secondary" 
                            className="text-xs font-semibold pl-0 pr-2.5 py-0.5 rounded-md"
                          >
                            {conferenceBadge}
                          </Badge>
                        )}
                        {details.phase && (
                          <Badge 
                            variant="outline" 
                            className="bg-blue-50 text-blue-700 border-blue-200 text-xs font-medium px-2.5 py-0.5 rounded-md"
                          >
                            Phase {details.phase}
                          </Badge>
                        )}
                        {details.status && details.status !== 'Unknown' && (
                          <Badge 
                            variant="outline" 
                            className="bg-green-50 text-green-700 border-green-200 text-xs font-medium px-2.5 py-0.5 rounded-md"
                          >
                            {details.status}
                          </Badge>
                        )}
                      </div>
                      <CardTitle className="text-xl sm:text-2xl font-bold text-gray-900 leading-snug break-words mb-2">
                        {details.title || 'Untitled Abstract'}
                      </CardTitle>
                      {details.nctNumber && (
                        <CardDescription className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-2 text-sm text-gray-600">
                          <Link
                            href={category ? `/trial/nct/${details.nctNumber}?category=${category}` : `/trial/nct/${details.nctNumber}`}
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                          >
                            {details.nctNumber}
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Link>
                          {details.abstractId && (
                            <>
                              <span className="text-gray-400">•</span>
                              {details.abstractId.startsWith('webscrape_') && details.sourceUrl ? (
                                <a
                                  href={details.sourceUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                                  title="View source"
                                >
                                  <span className="font-mono">#{details.abstractId}</span>
                                  <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                              ) : (
                                <span className="text-sm text-gray-600 font-mono">
                                  #{details.abstractId}
                                </span>
                              )}
                            </>
                          )}
                        </CardDescription>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Button variant="ghost" size="icon" className="h-9 w-9 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100" aria-label="View">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-9 w-9 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100" aria-label="More options">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-5 sm:px-6 pt-0 pb-6">
                  {/* Key Information Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5 sm:gap-y-6">
                    {/* Sponsor */}
                    {details.sponsor && (
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-gray-900 tracking-wide capitalize mb-1">Sponsor</p>
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-semibold text-sm shadow-sm flex-shrink-0">
                            {details.sponsor.charAt(0).toUpperCase()}
                          </div>
                          <p className="text-[15px] leading-snug text-gray-900 break-words">{details.sponsor}</p>
                        </div>
                      </div>
                    )}

                    {/* Treatment */}
                    {details.treatment && (
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-gray-900 tracking-wide capitalize mb-1">Treatment</p>
                        <p className="text-[15px] leading-snug text-gray-900 break-words">{details.treatment}</p>
                      </div>
                    )}

                    {/* Indication */}
                    {details.indication && (
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-gray-900 tracking-wide capitalize mb-1">Indication</p>
                        <p className="text-[15px] leading-snug text-gray-900 break-words">{details.indication}</p>
                      </div>
                    )}

                    {/* Line of Therapy */}
                    {details.lineOfTherapy && (
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-gray-900 tracking-wide capitalize mb-1">Line of Therapy</p>
                        <p className="text-[15px] leading-snug text-gray-900 break-words">{details.lineOfTherapy}</p>
                      </div>
                    )}

                    {/* Target */}
                    {details.target && (
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-gray-900 tracking-wide capitalize mb-1">Target</p>
                        <p className="text-[15px] leading-snug text-gray-900 break-words">{details.target}</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Section 2: Complete Information (gap with outer bg between sections) */}
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
                  <Card className="bg-white border border-gray-200 shadow-sm rounded-md overflow-hidden">
                    <CardHeader className="pb-4 pt-6 px-5 sm:px-6">
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <CardTitle className="text-sm font-bold tracking-wide capitalize text-gray-900 border-b border-gray-200 pb-2 mb-1 w-fit">Complete Information</CardTitle>
                          <CardDescription className="text-sm text-gray-600 mt-1">All extracted attributes and data points</CardDescription>
                        </div>
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
                            className="h-9 px-3 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2 transition-colors rounded-md w-fit flex-shrink-0"
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
                    </CardHeader>
                    <CardContent className="px-5 sm:px-6 pt-0 pb-6">
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
                      className="w-full space-y-3"
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
                            <AccordionItem key={sectionName} value={sectionName} className="border border-gray-200 rounded-md bg-white shadow-sm overflow-hidden">
                              <AccordionTrigger className="text-sm font-semibold text-gray-900 hover:no-underline py-4 px-5 hover:bg-gray-50/80 transition-colors [&[data-state=open]]:bg-gray-50/50">
                                {sectionName} ({totalCount})
                              </AccordionTrigger>
                              <AccordionContent className="pt-5 pb-6 px-5 bg-gray-50/50 text-[15px] leading-relaxed">
                                <div className="space-y-6">
                                  {/* Efficacy Sub-section - Always show */}
                                  <div>
                                    <h4 className="text-sm font-bold tracking-wide capitalize text-gray-900 mb-3 pb-2 border-b border-gray-200">
                                      Efficacy ({sectionData.Efficacy ? Object.keys(sectionData.Efficacy).length : 0})
                                    </h4>
                                    {sectionData.Efficacy && Object.keys(sectionData.Efficacy).length > 0 ? (
                                      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
                                        <table className="w-full border-collapse text-sm">
                                          <thead>
                                            <tr className="bg-gray-50 border-b border-gray-200">
                                              <th className="text-left py-3 px-4 text-sm font-bold text-gray-900 tracking-wide capitalize">Attribute</th>
                                              <th className="text-left py-3 px-4 text-sm font-bold text-gray-900 tracking-wide capitalize">Value</th>
                                            </tr>
                                          </thead>
                                          <tbody className="divide-y divide-gray-200">
                                            {Object.entries(sectionData.Efficacy).map(([key, value]) => (
                                              <tr key={key} className="hover:bg-gray-50 transition-colors">
                                                <td className="py-3 px-4 text-sm font-medium text-gray-700 align-top">{key}</td>
                                                <td className="py-3 px-4 text-[15px] leading-snug text-gray-900 break-words">{String(value)}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      </div>
                                    ) : (
                                      <div className="rounded-lg border border-gray-200 bg-gray-50 py-5 px-4 text-center">
                                        <p className="text-sm text-gray-500">No efficacy data available</p>
                                      </div>
                                    )}
                                  </div>
                                  
                                  {/* Safety Sub-section - Always show */}
                                  <div>
                                    <h4 className="text-sm font-bold tracking-wide capitalize text-gray-900 mb-3 pb-2 border-b border-gray-200">
                                      Safety ({sectionData.Safety ? Object.keys(sectionData.Safety).length : 0})
                                    </h4>
                                    {sectionData.Safety && Object.keys(sectionData.Safety).length > 0 ? (
                                      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
                                        <table className="w-full border-collapse text-sm">
                                          <thead>
                                            <tr className="bg-gray-50 border-b border-gray-200">
                                              <th className="text-left py-3 px-4 text-sm font-bold text-gray-900 tracking-wide capitalize">Attribute</th>
                                              <th className="text-left py-3 px-4 text-sm font-bold text-gray-900 tracking-wide capitalize">Value</th>
                                            </tr>
                                          </thead>
                                          <tbody className="divide-y divide-gray-200">
                                            {Object.entries(sectionData.Safety).map(([key, value]) => (
                                              <tr key={key} className="hover:bg-gray-50 transition-colors">
                                                <td className="py-3 px-4 text-sm font-medium text-gray-700 align-top">{key}</td>
                                                <td className="py-3 px-4 text-[15px] leading-snug text-gray-900 break-words">{String(value)}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      </div>
                                    ) : (
                                      <div className="rounded-lg border border-gray-200 bg-gray-50 py-5 px-4 text-center">
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
                          <AccordionItem key={sectionName} value={sectionName} className="border border-gray-200 rounded-md bg-white shadow-sm overflow-hidden">
                            <AccordionTrigger className="text-sm font-semibold text-gray-900 hover:no-underline py-4 px-5 hover:bg-gray-50/80 transition-colors [&[data-state=open]]:bg-gray-50/50">
                              {sectionName} ({Object.keys(sectionData).length})
                            </AccordionTrigger>
                            <AccordionContent className="pt-5 pb-6 px-5 bg-gray-50/50 text-[15px] leading-relaxed">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
                                {Object.entries(sectionData).map(([key, value]) => (
                                  <div key={key} className="min-w-0 py-3 border-b border-gray-200 last:border-b-0">
                                    <p className="text-sm font-bold text-gray-900 tracking-wide capitalize mb-1.5">{key}</p>
                                    <p className="text-[15px] leading-snug text-gray-900 break-words">{String(value)}</p>
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
                          <AccordionItem key={sectionName} value={sectionName} className="border border-gray-200 rounded-md bg-white shadow-sm overflow-hidden">
                            <AccordionTrigger className="text-sm font-semibold text-gray-900 hover:no-underline py-4 px-5 hover:bg-gray-50/80 transition-colors [&[data-state=open]]:bg-gray-50/50">
                              {sectionName} ({Object.keys(sectionData).length})
                            </AccordionTrigger>
                            <AccordionContent className="pt-5 pb-6 px-5 bg-gray-50/50 text-[15px] leading-relaxed">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
                                {Object.entries(sectionData).map(([key, value]) => (
                                  <div key={key} className="min-w-0 py-3 border-b border-gray-200 last:border-b-0">
                                    <p className="text-sm font-bold text-gray-900 tracking-wide capitalize mb-1.5">{key}</p>
                                    <p className="text-[15px] leading-snug text-gray-900 break-words">{String(value)}</p>
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

            {/* Right Column - Trial History */}
            {details.nctNumber && (
              <div className="xl:order-2 w-full xl:w-[380px] xl:flex-shrink-0">
                <AbstractTimeline
                  nctId={details.nctNumber}
                  currentAbstractId={details.abstractId}
                  className="bg-white border border-gray-200 rounded-[calc(0.5rem+1.5rem)]"
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

