'use client';

import * as React from 'react';
import { useQueries } from '@tanstack/react-query';
import Link from 'next/link';
import type { Trial, AbstractData, AttributeValue } from '@/lib/api';
import { trialsApi } from '@/lib/api';
import { BarChart3, Shield, ChevronRight } from 'lucide-react';

/** Get numeric value from arm attributes (AttributeType.X or lowercase key). */
function getNumericAttr(attributes: Record<string, AttributeValue | string | number | boolean | null> | undefined, key: string): number | null {
  if (!attributes) return null;
  const attr = attributes[`AttributeType.${key}`] ?? attributes[key.toLowerCase()] ?? attributes[key];
  if (attr == null) return null;
  if (typeof attr === 'number') return attr;
  if (typeof attr === 'object' && attr !== null && 'value' in attr) {
    const v = (attr as { value?: unknown }).value;
    if (typeof v === 'number') return v;
    if (typeof v === 'string') {
      const n = parseFloat(v.replace(/[^0-9.-]/g, ''));
      return isNaN(n) ? null : n;
    }
  }
  if (typeof attr === 'string') {
    const n = parseFloat(attr.replace(/[^0-9.-]/g, ''));
    return isNaN(n) ? null : n;
  }
  return null;
}

/** First efficacy key we care about for preview. */
const EFFICACY_KEYS = ['OBJECTIVE_RESPONSE_RATE', 'DISEASE_CONTROL_RATE', 'MEDIAN_PFS', 'MEDIAN_OS'];
/** First safety key we care about for preview. */
const SAFETY_KEYS = ['GRADE_3_PLUS_TRAE', 'GRADE_3_PLUS_TEAE', 'GRADE_3_PLUS_AE', 'TRAE'];

function getEfficacySafetyPreview(armResults: AbstractData['arm_results']): { efficacy?: string; safety?: string } {
  if (!armResults || typeof armResults !== 'object') return {};
  const firstArm = Object.values(armResults)[0];
  if (!firstArm?.attributes) return {};
  const attrs = firstArm.attributes;
  let efficacy: string | undefined;
  let safety: string | undefined;
  for (const key of EFFICACY_KEYS) {
    const n = getNumericAttr(attrs, key);
    if (n != null) {
      const label = key === 'OBJECTIVE_RESPONSE_RATE' ? 'ORR' : key === 'DISEASE_CONTROL_RATE' ? 'DCR' : key.replace(/_/g, ' ');
      efficacy = `${label}: ${n}%`;
      break;
    }
  }
  for (const key of SAFETY_KEYS) {
    const n = getNumericAttr(attrs, key);
    if (n != null) {
      safety = `G3+ TRAE: ${n}%`;
      break;
    }
  }
  return { efficacy, safety };
}

/** Group trials by abstract/publication id (one card per source). */
function groupTrialsBySource(trials: Trial[]): Map<string, Trial[]> {
  const map = new Map<string, Trial[]>();
  for (const t of trials) {
    const id = t.abstract_id || t.publication_name || t.id || '';
    if (!id) continue;
    if (!map.has(id)) map.set(id, []);
    map.get(id)!.push(t);
  }
  return map;
}

export interface AbstractsPublicationsPanelProps {
  trials: Trial[];
  category?: string;
  className?: string;
}

export function AbstractsPublicationsPanel({ trials, category, className = '' }: AbstractsPublicationsPanelProps) {
  const bySource = React.useMemo(() => groupTrialsBySource(trials), [trials]);
  const abstractIds = React.useMemo(
    () => Array.from(bySource.keys()).filter((id) => id && !id.startsWith('webscrape_')),
    [bySource]
  );

  const detailQueries = useQueries({
    queries: abstractIds.slice(0, 15).map((abstractId) => ({
      queryKey: ['abstract-preview', abstractId],
      queryFn: () => trialsApi.getByAbstractId(abstractId),
      staleTime: 5 * 60 * 1000,
      retry: false,
    })),
  });

  const detailByKey = React.useMemo(() => {
    const map = new Map<string, AbstractData>();
    detailQueries.forEach((q, i) => {
      const id = abstractIds[i];
      if (id && q.data) map.set(id, q.data);
    });
    return map;
  }, [abstractIds, detailQueries]);

  if (trials.length === 0) return null;

  return (
    <div className={`min-w-0 ${className}`}>
      <h2 className="text-lg font-bold text-gray-900 mb-3">Abstracts & Publications</h2>
      <p className="text-sm text-gray-600 mb-4">
        Extracted efficacy & safety data from conference abstracts and publications for this trial.
      </p>
      <div className="space-y-3">
        {Array.from(bySource.entries()).map(([sourceId, sourceTrials]) => {
          const first = sourceTrials[0];
          const displayId = (first?.type === 'publication' && first?.publication_name) ? first.publication_name : sourceId;
          const armNames = Array.from(new Set(sourceTrials.map((t) => t.arm_name || t.generic_name).filter(Boolean))) as string[];
          const abstractUrl = category
            ? `/trial/abstract/${sourceId}?category=${category}`
            : `/trial/abstract/${sourceId}`;
          const isWebScraped = sourceId.startsWith('webscrape_');
          const queryIndex = abstractIds.indexOf(sourceId);
          const query = queryIndex >= 0 ? detailQueries[queryIndex] : undefined;
          const detail = detailByKey.get(sourceId);
          const preview = detail ? getEfficacySafetyPreview(detail.arm_results) : {};
          const failed = query?.isError === true;

          return (
            <div
              key={sourceId}
              className="rounded-lg border border-gray-200 bg-gray-50 overflow-hidden shadow-sm"
            >
              <div className="p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    {isWebScraped && first?.source_url ? (
                      <a
                        href={first.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-semibold text-blue-600 hover:underline truncate block"
                      >
                        {displayId}
                      </a>
                    ) : (
                      <Link
                        href={abstractUrl}
                        className="text-sm font-semibold text-blue-600 hover:underline truncate block"
                      >
                        {displayId}
                      </Link>
                    )}
                    {armNames.length > 0 && (
                      <p className="text-xs text-gray-500 mt-1 truncate" title={armNames.join(', ')}>
                        Arms: {armNames.join(', ')}
                      </p>
                    )}
                  </div>
                  {!isWebScraped && (
                    <Link
                      href={abstractUrl}
                      className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"
                    >
                      View <ChevronRight className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>
                {(preview.efficacy || preview.safety || (detail && !preview.efficacy && !preview.safety) || failed) && (
                  <div className="mt-2 pt-2 border-t border-gray-200 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                    {failed ? (
                      <span className="text-gray-500">View abstract for details</span>
                    ) : (
                      <>
                        {preview.efficacy && (
                          <span className="inline-flex items-center gap-1 text-gray-700">
                            <BarChart3 className="h-3.5 w-3.5 text-emerald-600" aria-hidden />
                            {preview.efficacy}
                          </span>
                        )}
                        {preview.safety && (
                          <span className="inline-flex items-center gap-1 text-gray-700">
                            <Shield className="h-3.5 w-3.5 text-amber-600" aria-hidden />
                            {preview.safety}
                          </span>
                        )}
                        {!preview.efficacy && !preview.safety && detail && (
                          <span className="text-gray-500">Extracted attributes available</span>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
