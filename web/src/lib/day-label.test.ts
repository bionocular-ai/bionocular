import { describe, expect, it } from 'vitest';
import { dayLabel } from './day-label';

describe('dayLabel', () => {
  it('labels a calendar day without a timezone shift', () => {
    const now = new Date(2026, 9, 29, 12); // the reader's local Oct 29
    expect(dayLabel('2026-10-27', now)).toEqual({ day: 'Oct 27', weekday: 'Tuesday' });
    expect(dayLabel('2025-12-31', now).day).toBe('Dec 31, 2025');
  });

  it('calls the reader\'s today and yesterday by name', () => {
    const now = new Date(2026, 9, 29, 0, 5); // just after local midnight
    expect(dayLabel('2026-10-29', now)).toEqual({ day: 'Today', weekday: 'Thursday, Oct 29' });
    expect(dayLabel('2026-10-28', now)).toEqual({ day: 'Yesterday', weekday: 'Wednesday, Oct 28' });
    expect(dayLabel('2026-11-01', new Date(2026, 10, 2, 9)).day).toBe('Yesterday'); // across a month boundary
  });
});
