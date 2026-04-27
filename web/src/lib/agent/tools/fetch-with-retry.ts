import pRetry from 'p-retry';

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  return pRetry(
    async () => {
      const res = await fetch(url, init);
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status} ${url} — ${body.slice(0, 200)}`);
      }
      return res.json() as Promise<T>;
    },
    { retries: 3, minTimeout: 500, factor: 2 }
  );
}

export async function fetchText(url: string, init?: RequestInit): Promise<string> {
  return pRetry(
    async () => {
      const res = await fetch(url, init);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status} ${url}`);
      }
      return res.text();
    },
    { retries: 3, minTimeout: 500, factor: 2 }
  );
}
