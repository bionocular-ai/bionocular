const localDay = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/**
 * Dates are calendar days ("2026-10-28"); read them as UTC so no timezone shifts the day.
 * The reader's own today and yesterday read "Today" / "Yesterday", with the date underneath.
 */
export function dayLabel(date: string, now = new Date()): { day: string; weekday: string } {
  const key = date.slice(0, 10);
  const d = new Date(`${key}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return { day: date, weekday: '' };
  const sameYear = d.getUTCFullYear() === now.getFullYear();
  const day = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(sameYear ? {} : { year: 'numeric' }), timeZone: 'UTC' });
  const weekday = d.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' });
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  if (key === localDay(now)) return { day: 'Today', weekday: `${weekday}, ${day}` };
  if (key === localDay(yesterday)) return { day: 'Yesterday', weekday: `${weekday}, ${day}` };
  return { day, weekday };
}
