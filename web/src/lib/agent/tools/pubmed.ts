import { tool } from 'ai';
import { z } from 'zod';
import { getServerEnv } from '@/lib/env';
import { fetchJson, fetchText } from './fetch-with-retry';

const ESEARCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi';
const EFETCH  = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi';

interface ESearchResponse {
  esearchresult: { idlist: string[]; count: string };
}

interface PubmedHit {
  pmid: string;
  title: string;
  abstract: string;
  authors: string[];
  journal: string;
  year: string;
}

function parsePubmedXml(xml: string): PubmedHit[] {
  const articles = xml.split('<PubmedArticle>').slice(1);
  return articles.map((chunk) => {
    const pmid     = chunk.match(/<PMID[^>]*>([^<]+)<\/PMID>/)?.[1] ?? '';
    const title    = chunk.match(/<ArticleTitle>([\s\S]*?)<\/ArticleTitle>/)?.[1]?.replace(/<[^>]+>/g, '') ?? '';
    const abstract = [...chunk.matchAll(/<AbstractText[^>]*>([\s\S]*?)<\/AbstractText>/g)]
      .map((m) => m[1].replace(/<[^>]+>/g, '').trim())
      .join('\n');
    const journal  = chunk.match(/<Title>([^<]+)<\/Title>/)?.[1] ?? '';
    const year     = chunk.match(/<PubDate>[\s\S]*?<Year>(\d{4})<\/Year>/)?.[1] ?? '';
    const authors  = [...chunk.matchAll(/<Author[^>]*>[\s\S]*?<LastName>([^<]+)<\/LastName>[\s\S]*?<ForeName>([^<]+)<\/ForeName>/g)]
      .map((m) => `${m[2]} ${m[1]}`)
      .slice(0, 5);
    return { pmid, title, abstract, authors, journal, year };
  });
}

export const searchPubmedTool = tool({
  description:
    'Search PubMed for peer-reviewed oncology literature. Use for primary research, abstracts, ' +
    'systematic reviews, mechanistic studies. Prefer specific cancer-type and intervention terms ' +
    '(e.g. "BRAF V600E melanoma resistance encorafenib"). Returns PMID, title, abstract, authors, ' +
    'journal, year.',
  inputSchema: z.object({
    query: z.string().describe('PubMed query string. Use MeSH terms or free text.'),
    maxResults: z.number().int().min(1).max(20).default(5),
  }),
  providerOptions: {
    anthropic: { cacheControl: { type: 'ephemeral' } },
  },
  execute: async ({ query, maxResults }) => {
    const { pubmedApiKey } = getServerEnv();
    const keyParam = pubmedApiKey ? `&api_key=${pubmedApiKey}` : '';

    const search = await fetchJson<ESearchResponse>(
      `${ESEARCH}?db=pubmed&term=${encodeURIComponent(query)}&retmode=json&retmax=${maxResults}${keyParam}`
    );

    const ids = search.esearchresult.idlist;
    if (ids.length === 0) {
      return { results: [], total: 0, query };
    }

    const xml = await fetchText(
      `${EFETCH}?db=pubmed&id=${ids.join(',')}&retmode=xml${keyParam}`
    );

    return {
      query,
      total: parseInt(search.esearchresult.count, 10),
      results: parsePubmedXml(xml),
    };
  },
});
