'use client';

import * as React from 'react';
import { useSearchParams } from 'next/navigation';

/**
 * A filter kept in the page address, so Back and shared links restore it. Writes go
 * through history.replaceState, which Next.js syncs into useSearchParams without a
 * server round trip, and replace (not push) so Back still leaves the page.
 */
export function useQueryParam<T extends string>(
  key: string,
  fallback: T,
  isValid: (value: string) => value is T,
): [T, (next: T) => void] {
  const searchParams = useSearchParams();
  const raw = searchParams.get(key);
  const value = raw !== null && isValid(raw) ? raw : fallback;

  const setValue = React.useCallback(
    (next: T) => {
      const params = new URLSearchParams(window.location.search);
      if (next === fallback) params.delete(key);
      else params.set(key, next);
      const qs = params.toString();
      window.history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
    },
    [key, fallback],
  );

  return [value, setValue];
}
