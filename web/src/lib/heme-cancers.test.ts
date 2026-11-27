import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/supabase/client', () => ({ createClient: () => ({}) }));

import { getDbCancerType } from './api';
import { HEME_CANCERS, isHemeCancerType } from './heme-cancers';

function csvFullNames(): string[] {
  const csv = readFileSync(resolve(__dirname, '../../../melanoma/resources/ash/indications.csv'), 'utf8');
  // full_name is the second column and never contains a comma
  return csv.trim().split('\n').slice(1).map((line) => line.split(',')[1]);
}

describe('heme cancers', () => {
  it('labels match indications.csv full_name', () => {
    expect(HEME_CANCERS.map((c) => c.label)).toEqual(csvFullNames());
  });

  it('slugs are plain kebab ASCII', () => {
    for (const { slug } of HEME_CANCERS) expect(slug).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
    const slugs = HEME_CANCERS.map((c) => c.slug);
    expect(slugs).toContain('allogeneic-transplant-gvhd');
    expect(slugs).toContain('polycythemia-vera-essential-thrombocythemia');
    expect(slugs).toContain('waldenstrom-macroglobulinemia');
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it('getDbCancerType maps every heme slug', () => {
    for (const { slug, label } of HEME_CANCERS) expect(getDbCancerType(slug)).toBe(label);
  });

  it('getDbCancerType keeps melanoma mapping and unknown passthrough', () => {
    expect(getDbCancerType('uveal-melanoma')).toBe('Uveal Melanoma');
    expect(getDbCancerType('nope')).toBe('nope');
  });

  it('isHemeCancerType is true for heme names and false for Cutaneous Melanoma', () => {
    expect(isHemeCancerType('Multiple Myeloma')).toBe(true);
    expect(isHemeCancerType('Cutaneous Melanoma')).toBe(false);
  });
});
