import { describe, expect, it } from 'vitest';
import { readoutDate, readoutOf, regimenKey } from './regimen';

describe('regimenKey', () => {
  it('reads every spelling one regimen takes across readouts as one key', () => {
    // RELATIVITY-047's combination arm, as NEJM 2022, ASCO 2021/2023 and ASCO 2026 spell it.
    for (const name of [
      'NIVO + RELA',
      'Relatlimab-Nivolumab',
      'Nivolumab + Relatlimab',
      'Relatlimab + Nivolumab',
      'nivolumab plus relatlimab',
    ]) {
      expect(regimenKey(name), name).toBe('nivolumab+relatlimab');
    }
    expect(regimenKey('nuru + prolgo')).toBe('nurulimab+prolgolimab');
  });

  it('drops placebo, monotherapy and setting words, but keeps a placebo-only arm its own key', () => {
    expect(regimenKey('prolgo monotherapy')).toBe('prolgolimab');
    expect(regimenKey('Placebo + Dabrafenib + Trametinib')).toBe('dabrafenib+trametinib');
    expect(regimenKey('vemurafenib and placebo')).toBe('vemurafenib');
    expect(regimenKey('Neoadjuvant ipilimumab plus nivolumab')).toBe('ipilimumab+nivolumab');
    expect(regimenKey('Adjuvant nivolumab')).toBe('nivolumab');
    expect(regimenKey('Placebo')).toBe('placebo');
  });

  it('keeps dosing words, so two schedules of one drug stay two treatments', () => {
    expect(regimenKey('Pembrolizumab every 2 weeks')).not.toBe(regimenKey('pembrolizumab every 3 weeks'));
  });
});

describe('readoutOf', () => {
  it('names the abstract, else the publication, else the page', () => {
    expect(readoutOf({ abstract_id: 'ASCO_2026_9532', publication_id: 'x' })).toBe('ASCO_2026_9532');
    expect(readoutOf({ publication_id: 'N Engl J Med 2022;386:24-34.' })).toBe('N Engl J Med 2022;386:24-34.');
    expect(readoutOf({ source_url: 'https://example.com/r' })).toBe('https://example.com/r');
    expect(readoutOf({})).toBeNull();
  });
});

describe('readoutDate', () => {
  it('dates an abstract by its meeting, so ESMO reads newer than the same year ASCO', () => {
    expect(readoutDate({ abstract_id: 'ASCO_2026_9532' })).toEqual([2026, 6]);
    expect(readoutDate({ abstract_id: 'ESMO_2025_1619P' })).toEqual([2025, 10]);
    expect(readoutDate({ abstract_id: 'SITC_2025_1234' })).toEqual([2025, 11]);
    expect(readoutDate({ abstract_id: 'ASCO_2022_TPS9589' })).toEqual([2022, 6]);
  });

  it('dates a publication by the first year in its citation, and one with none as oldest', () => {
    expect(readoutDate({ publication_id: 'N Engl J Med 2022;386:24-34.' })).toEqual([2022, 0]);
    expect(readoutDate({ publication_id: 'Lancet 2017; 390: 1853–62' })).toEqual([2017, 0]);
    expect(readoutDate({ publication_id: 'J Clin Oncol 36:383-390.' })).toEqual([0, 0]);
    expect(readoutDate({ source_url: 'https://example.com/r' })).toEqual([0, 0]);
  });
});
