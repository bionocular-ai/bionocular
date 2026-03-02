'use client';

import * as React from 'react';
import type { TrialDetailApiResponse } from '@/lib/api';
import { ExternalLink } from 'lucide-react';

function LabelValue({
  label,
  value,
  className = '',
}: {
  label: string;
  value: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-[12rem_1fr] gap-x-4 gap-y-1 sm:gap-y-0 sm:items-baseline min-w-0 ${className}`}>
      <dt className="text-sm font-bold tracking-wide text-gray-900 shrink-0 capitalize">{label}</dt>
      <dd className="text-[15px] leading-snug text-gray-900 break-words min-w-0">{value ?? '—'}</dd>
    </div>
  );
}

/** Card-style wrapper for major sections so they stand out on the page background. */
const sectionCardClass = 'bg-white rounded-xl border border-gray-200 shadow-sm p-4 sm:p-5 md:p-6';

/** Readable prose: relaxed line-height and comfortable line length for long text. */
const proseClass = 'text-[15px] leading-relaxed text-gray-800 break-words';

function Section({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 ${className}`}>
      <h2 className="text-base font-bold tracking-wide text-gray-900 border-b border-gray-200 pb-2 mb-4 capitalize">{title}</h2>
      <div className={`${proseClass} space-y-3`}>{children}</div>
    </section>
  );
}

/**
 * Eligibility criteria mapping (ClinicalTrials.gov API v2):
 * The API provides a single field: eligibilityModule.eligibilityCriteria (one string).
 * There are no separate inclusionCriteria/exclusionCriteria fields. The string format is:
 *   "Inclusion Criteria:\n\n1. ...\n\nExclusion Criteria:\n\n1. ..."
 * We split on "Exclusion Criteria:" to get two blocks, and strip the embedded headings
 * so our section titles ("Inclusion Criteria:", "Exclusion Criteria:") are not duplicated.
 */
function parseEligibilityCriteria(text: string | undefined): { inclusion: string; exclusion: string } {
  if (!text || !text.trim()) return { inclusion: '', exclusion: '' };
  const normalized = text.trim();
  const exclusionMarker = /\n\s*Exclusion Criteria\s*:/i;
  const exclusionIndex = normalized.search(exclusionMarker);
  if (exclusionIndex === -1) {
    const inclMarker = /\n\s*Inclusion Criteria\s*:/i;
    const inclStart = normalized.search(inclMarker);
    if (inclStart === -1) return { inclusion: normalized, exclusion: '' };
    const inclusionBlock = normalized.slice(inclStart).trim();
    const inclusionContent = inclusionBlock.replace(/^\s*Inclusion Criteria\s*:?\s*/i, '').trim();
    return { inclusion: inclusionContent, exclusion: '' };
  }
  const inclusionBlock = normalized.slice(0, exclusionIndex).trim();
  const exclusionBlock = normalized.slice(exclusionIndex).trim();
  const inclusionContent = inclusionBlock.replace(/^\s*Inclusion Criteria\s*:?\s*/i, '').trim();
  const exclusionContent = exclusionBlock.replace(/^\s*Exclusion Criteria\s*:?\s*/i, '').trim();
  return { inclusion: inclusionContent, exclusion: exclusionContent };
}

/** Format date string for display. */
function formatDate(s: string | undefined): string {
  if (!s) return '—';
  try {
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  } catch {
    return s;
  }
}

type LocationItem = {
  facility?: string;
  city?: string;
  state?: string;
  zip?: string;
  country?: string;
  status?: string;
};

/** Group locations by country with count. */
function groupLocationsByCountry(locations: LocationItem[] | undefined): Map<string, LocationItem[]> {
  const map = new Map<string, LocationItem[]>();
  if (!locations?.length) return map;
  for (const loc of locations) {
    const country = loc.country ?? 'Unknown';
    if (!map.has(country)) map.set(country, []);
    map.get(country)!.push(loc);
  }
  return map;
}

export interface TrialDetailViewProps {
  data: TrialDetailApiResponse;
  nctId: string;
  className?: string;
}

export function TrialDetailView({ data, nctId, className = '' }: TrialDetailViewProps) {
  const protocol = data?.protocolSection ?? {};
  const idModule = protocol.identificationModule ?? {};
  const conditionsModule = protocol.conditionsModule ?? {};
  const designModule = protocol.designModule ?? {};
  const statusModule = protocol.statusModule ?? {};
  const sponsorModule = protocol.sponsorCollaboratorsModule ?? {};
  const armsInterventions = protocol.armsInterventionsModule ?? {};
  const descriptionModule = protocol.descriptionModule ?? {};
  const eligibilityModule = protocol.eligibilityModule ?? {};
  const outcomesModule = protocol.outcomesModule ?? {};
  const locationsModule = protocol.contactsLocationsModule ?? {};

  const interventions = armsInterventions.interventions ?? [];
  const armGroups = armsInterventions.armGroups ?? [];
  // API v2 puts conditions under conditionsModule, not identificationModule
  const conditions = (conditionsModule.conditions?.length ? conditionsModule.conditions : idModule.conditions) ?? [];
  const phases = designModule.phases ?? [];
  const studyType = designModule.studyType ?? '';
  const enrollmentInfo = designModule.enrollmentInfo ?? {};
  const leadSponsor = sponsorModule.leadSponsor ?? {};
  const status = typeof statusModule.overallStatus === 'string'
    ? statusModule.overallStatus
    : (statusModule.overallStatus as { status?: string } | undefined)?.status ?? '';

  const eligibilityCriteria = eligibilityModule.eligibilityCriteria ?? '';
  const eligibilityInfo = eligibilityModule.eligibilityInfo ?? {};
  const primaryOutcomes = outcomesModule.primaryOutcomes ?? [];
  const secondaryOutcomes = outcomesModule.secondaryOutcomes ?? [];
  const locations = locationsModule.locations ?? [];

  const { inclusion: inclusionText, exclusion: exclusionText } = parseEligibilityCriteria(eligibilityCriteria);
  const locationsByCountry = groupLocationsByCountry(locations);

  const interventionNames = interventions
    .map((i) => (i.name ?? '').trim())
    .filter(Boolean);
  const treatmentDisplay = interventionNames.length > 0
    ? interventionNames.map((name) => `DRUG: ${name}`).join('\n')
    : '—';

  return (
    <article className={`w-full max-w-4xl xl:max-w-5xl 2xl:max-w-6xl min-w-0 mx-auto text-gray-900 ${className}`}>
      {/* Single section: all clinical trial data */}
      <div className={`${sectionCardClass} overflow-hidden`}>
      <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-6 sm:mb-8 leading-snug break-words">
        {idModule.briefTitle ?? nctId}
      </h1>

      {/* Key information: one row per field (Label → Value) */}
      <div className="flex flex-col gap-y-4 pb-8 sm:pb-10 mb-8 sm:mb-10 border-b border-gray-100">
        <LabelValue
          label="Condition"
          value={conditions.length > 0 ? conditions.join(', ') : '—'}
        />
        <LabelValue
          label="Intervention/Treatment"
          value={
            <span className="whitespace-pre-line">
              {treatmentDisplay}
            </span>
          }
        />
        <LabelValue label="Phase" value={phases.length > 0 ? phases.join(' / ') : '—'} />
        <LabelValue label="Study Type" value={studyType || '—'} />
        <LabelValue label="Lead Sponsor" value={leadSponsor.name ?? '—'} />
        <LabelValue label="Status" value={status || '—'} />
        <LabelValue
          label="Enrollment"
          value={
            enrollmentInfo.count != null
              ? `Anticipated: ${enrollmentInfo.count} participants`
              : '—'
          }
        />
        <LabelValue
          label="Posted"
          value={formatDate(statusModule.studyFirstPostDateStruct?.date)}
        />
        <LabelValue
          label="Updated"
          value={formatDate(statusModule.lastUpdatePostDateStruct?.date)}
        />
        <LabelValue
          label="Primary Completion"
          value={formatDate(statusModule.primaryCompletionDateStruct?.date)}
        />
        <LabelValue
          label="Study Completion"
          value={formatDate(statusModule.completionDateStruct?.date)}
        />
        <div className="grid grid-cols-1 sm:grid-cols-[12rem_1fr] gap-x-4 gap-y-1 sm:gap-y-0 sm:items-baseline min-w-0">
          <dt className="text-sm font-bold tracking-wide text-gray-900 shrink-0 capitalize">Study Identifier</dt>
          <dd className="text-[15px] leading-snug text-gray-900 inline-flex flex-wrap items-center gap-x-1.5 gap-y-1">
            {nctId}
            <a
              href={`https://clinicaltrials.gov/study/${nctId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 inline-flex items-center"
              aria-label="View on ClinicalTrials.gov"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </dd>
        </div>
      </div>

      {/* Summary */}
      {descriptionModule.briefSummary && (
        <Section title="Summary" className="mb-10">
          <p className="whitespace-pre-line leading-relaxed">{descriptionModule.briefSummary}</p>
        </Section>
      )}

      {/* Arms & Interventions */}
      <Section title="Arms & Interventions" className="mb-10">
        {armGroups.length > 0 && (
          <ol className="list-decimal list-inside space-y-3 mb-5 pl-0.5">
            {armGroups.map((arm, idx) => (
              <li key={idx} className="pl-1">
                <span className="font-semibold text-gray-900">{arm.label ?? `Arm ${idx + 1}`}</span>
                {arm.description ? <span className="text-gray-800">: {arm.description}</span> : ''}
              </li>
            ))}
          </ol>
        )}
        {interventions.map((int, idx) => {
          const typeLabel = (int.type?.trim() && int.type.toUpperCase()) || 'Intervention';
          return (
            <div key={idx} className="py-1">
              <span className="font-semibold text-gray-900">{typeLabel}: {int.name ?? '—'}</span>
              {int.description ? <span className="text-gray-800"> — {int.description}</span> : ''}
            </div>
          );
        })}
        {armGroups.length === 0 && interventions.length === 0 && <p>—</p>}
      </Section>

      {/* Intervention alternative names */}
      {interventions.some((i) => i.otherNames?.length) ? (
        <Section title="Intervention Alternative Names" className="mb-10">
          {interventions.map((int, idx) =>
            int.otherNames?.length ? (
              <p key={idx}>
                <span className="font-semibold text-gray-900">{int.name ?? '—'}:</span>{' '}
                <span className="text-gray-800">{int.otherNames.join('; ')}</span>
              </p>
            ) : null
          )}
        </Section>
      ) : null}

      {/* Description */}
      {descriptionModule.detailedDescription && (
        <Section title="Description" className="mb-10">
          <p className="whitespace-pre-line leading-relaxed">{descriptionModule.detailedDescription}</p>
        </Section>
      )}

      {/* Primary outcome measures */}
      {primaryOutcomes.length > 0 && (
        <Section title="Primary Outcome Measures" className="mb-10">
          <ol className="list-decimal list-inside space-y-3 pl-0.5">
            {primaryOutcomes.map((out, idx) => (
              <li key={idx} className="pl-1">
                <span className="font-semibold text-gray-900">{out.measure ?? '—'}</span>
                {out.description ? <span className="text-gray-800"> — {out.description}</span> : ''}
                {out.timeFrame ? <span className="text-gray-700"> {out.timeFrame}</span> : ''}
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* Secondary outcome measures */}
      {secondaryOutcomes.length > 0 && (
        <Section title="Secondary Outcome Measures" className="mb-10">
          <ol className="list-decimal list-inside space-y-3 pl-0.5">
            {secondaryOutcomes.map((out, idx) => (
              <li key={idx} className="pl-1">
                <span className="font-semibold text-gray-900">{out.measure ?? '—'}</span>
                {out.description ? <span className="text-gray-800"> — {out.description}</span> : ''}
                {out.timeFrame ? <span className="text-gray-700"> {out.timeFrame}</span> : ''}
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* Eligibility */}
      <Section title="Eligibility" className="mb-10">
        <p>
          <span className="font-semibold text-gray-900">Age:</span>{' '}
          <span className="text-gray-800">{eligibilityInfo.minimumAge ?? '—'} to {eligibilityInfo.maximumAge ?? 'N/A'}</span>
        </p>
        <p>
          <span className="font-semibold text-gray-900">Gender:</span>{' '}
          <span className="text-gray-800">{eligibilityInfo.sex ?? 'ALL'}</span>
        </p>
      </Section>

      {/* Inclusion criteria */}
      {inclusionText && (
        <Section title="Inclusion Criteria" className="mb-10">
          <div className="whitespace-pre-line leading-relaxed">{inclusionText}</div>
        </Section>
      )}

      {/* Exclusion criteria */}
      {exclusionText && (
        <Section title="Exclusion Criteria" className="mb-10">
          <div className="whitespace-pre-line leading-relaxed">{exclusionText}</div>
        </Section>
      )}

      {/* Location */}
      {locationsByCountry.size > 0 && (
        <Section title="Location" className="mb-10">
          {Array.from(locationsByCountry.entries()).map(([country, locs]) => (
            <div key={country} className="mb-4">
              <p className="font-semibold text-gray-900">
                {country} ({locs.length})
              </p>
              <ul className="list-none mt-2 space-y-2">
                {locs.map((loc, idx) => (
                  <li key={idx} className="text-gray-800">
                    {loc.facility ?? '—'}
                    {(loc.city || loc.state || loc.zip) && (
                      <span className="text-blue-600">
                        {' '}
                        ({[loc.city, loc.state, loc.zip].filter(Boolean).join(', ')})
                      </span>
                    )}
                    {loc.status ? ` - ${loc.status}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </Section>
      )}
      </div>
    </article>
  );
}
