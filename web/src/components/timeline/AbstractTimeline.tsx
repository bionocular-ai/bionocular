'use client';

import { useQuery } from '@tanstack/react-query';
import { trialsApi } from '@/lib/api';
import { extractKeyMetrics, formatAbstractIdForDisplay } from '@/lib/utils/trial-utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import Link from 'next/link';

interface AbstractTimelineProps {
  nctId: string;
  currentAbstractId?: string;
  /** Outer radius = inner (rounded-lg) + padding; use for consistent panel look. */
  className?: string;
}

interface TimelineItem {
  abstractId: string;
  conference: string;
  year: string;
  date: string;
  metrics?: Record<string, { value: string; shortForm: string }>;
  publicationName?: string;
}

export function AbstractTimeline({ nctId, currentAbstractId, className = '' }: AbstractTimelineProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['trials', 'nct', nctId],
    queryFn: () => trialsApi.getByNctId(nctId, 0, 100),
    enabled: !!nctId,
  });

  // Fetch full abstract data for each trial to get metrics
  const { data: timelineData, isLoading: isLoadingMetrics } = useQuery({
    queryKey: ['timeline', 'nct', nctId, data?.trials?.map(t => t.abstract_id).join(',')],
    queryFn: async () => {
      if (!data?.trials) return [];
      
      // Fetch all abstract data in parallel
      const abstractPromises = data.trials
        .filter(trial => trial.abstract_id)
        .map(async (trial) => {
          try {
            const fullData = await trialsApi.getByAbstractId(trial.abstract_id!);
            const metrics = extractKeyMetrics(fullData);
            
            // Include items that have a year (conference is optional, will be "Publication" for publications)
            if (metrics.year) {
              return {
                abstractId: trial.abstract_id!,
                conference: metrics.conference || 'Publication',
                year: metrics.year,
                date: metrics.date || (metrics.conference ? `${metrics.conference} ${metrics.year}` : metrics.year),
                metrics: metrics.metrics,
                publicationName: metrics.publicationName,
              } as Omit<TimelineItem, 'isCurrent'>;
            }
          } catch (error) {
            console.error(`Error fetching metrics for ${trial.abstract_id}:`, error);
          }
          return null;
        });
      
      const results = await Promise.all(abstractPromises);
      const timelineItems = results.filter((item): item is Omit<TimelineItem, 'isCurrent'> => item !== null);
      
      // Sort by year descending (newest first)
      timelineItems.sort((a, b) => {
        const yearA = parseInt(a.year) || 0;
        const yearB = parseInt(b.year) || 0;
        if (yearB !== yearA) return yearB - yearA;
        
        // If same year, sort by conference (ASCO before ESMO)
        if (a.conference !== b.conference) {
          return a.conference === 'ASCO' ? -1 : 1;
        }
        
        return 0;
      });
      
      return timelineItems;
    },
    enabled: !!data?.trials && data.trials.length > 0,
  });

  const cardClass = `border-gray-200 shadow-sm ${className}`.trim();

  if (isLoading || isLoadingMetrics) {
    return (
      <Card className={cardClass}>
        <CardContent className="p-6">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!timelineData || timelineData.length === 0) {
    return (
      <Card className={`${cardClass} sticky top-20`}>
        <CardHeader className="pb-4">
          <CardTitle className="text-lg font-semibold">Trial History</CardTitle>
          <CardDescription>Previous abstracts and publications</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">No other abstracts found for this NCT number.</p>
        </CardContent>
      </Card>
    );
  }

  // Group by year
  const groupedByYear: Record<string, TimelineItem[]> = {};
  timelineData.forEach((item) => {
    if (!groupedByYear[item.year]) {
      groupedByYear[item.year] = [];
    }
    groupedByYear[item.year].push(item);
  });

  const years = Object.keys(groupedByYear).sort((a, b) => parseInt(b) - parseInt(a));

  return (
    <Card className={`${cardClass} sticky top-20`}>
      <CardHeader className="pb-4">
        <CardTitle className="text-lg font-semibold">Trial History</CardTitle>
        <CardDescription>Previous abstracts and publications</CardDescription>
      </CardHeader>
      <CardContent>
        
        <div className="relative">
          {/* Timeline line - positioned at 16px from left */}
          <div 
            className="absolute top-0 bottom-0 bg-purple-500 z-0" 
            style={{ 
              left: '16px', 
              width: '2px',
              transform: 'translateX(-50%)'
            }}
          ></div>
          
          <div className="pl-8 space-y-4">
            {years.map((year) => {
              const items = groupedByYear[year];
              return (
                <div key={year}>
                  {items.map((item) => {
                    // Determine if this item is current based on currentAbstractId prop
                    const isCurrent = item.abstractId === currentAbstractId;
                    
                    return (
                    <div
                      key={item.abstractId}
                      className="relative pb-4 last:pb-0"
                    >
                      {/* Timeline node - positioned to align with line at 16px from outer container */}
                      {/* Content div has pl-8 (32px padding), so item starts at 32px from outer */}
                      {/* Line center is at 16px from outer, so circle center needs to be at -16px relative to item */}
                      {/* To center at -16px: left edge at -16px - 8px = -24px, then translateX(-50%) shifts by -8px, so left edge at -32px, center at -24px... */}
                      {/* Actually: left: -16px positions left edge at -16px, translateX(-50%) shifts by -8px, so left edge at -24px, center at -16px ✓ */}
                      <div
                        className={`absolute top-3 rounded-full border-2 z-10 ${
                          isCurrent
                            ? 'bg-blue-600 border-blue-600'
                            : 'bg-white border-blue-500'
                        }`}
                        style={{ 
                          left: '-16px', 
                          width: '16px',
                          height: '16px',
                          transform: 'translateX(-50%)'
                        }}
                      ></div>
                      
                      {/* Card */}
                      <Link
                        href={`/trial/abstract/${item.abstractId}`}
                        className={`block rounded-lg border transition-all hover:shadow-md cursor-pointer ${
                          isCurrent
                            ? 'border-blue-500 bg-blue-50 shadow-sm'
                            : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                        }`}
                      >
                        <div className="p-4">
                          {/* Header */}
                          <div className="mb-3">
                            <h4 className="text-base font-bold text-gray-900 mb-1.5">
                              {item.publicationName || `${item.conference} ${item.year}`}
                            </h4>
                            <div className="flex items-center gap-1.5 text-xs text-gray-600">
                              {item.publicationName ? (
                                <>
                                  <span>{item.conference} {item.year}</span>
                                  <span className="text-gray-400">•</span>
                                  <span className="font-mono text-xs text-gray-700 hover:text-blue-600 transition-colors">
                                    #{formatAbstractIdForDisplay(item.abstractId)}
                                  </span>
                                </>
                              ) : (
                                <>
                                  <span>{item.date}</span>
                                  <span className="text-gray-400">•</span>
                                  <span className="font-mono text-xs text-gray-700 hover:text-blue-600 transition-colors">
                                    #{formatAbstractIdForDisplay(item.abstractId)}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                          
                          {/* Metrics */}
                          {item.metrics && Object.keys(item.metrics).length > 0 && (
                            <div className="flex flex-wrap gap-x-4 gap-y-2.5 mt-3 pt-3 border-t border-gray-100">
                              {Object.entries(item.metrics).map(([shortForm, metric]) => (
                                <div key={shortForm} className="min-w-[60px]">
                                  <div className="text-sm font-bold text-blue-600 leading-tight">
                                    {metric.value}
                                  </div>
                                  <div className="text-xs text-gray-500 mt-1">{shortForm}</div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </Link>
                    </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}



