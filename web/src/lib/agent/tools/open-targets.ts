import { tool } from 'ai';
import { z } from 'zod';
import { fetchJson } from './fetch-with-retry';

const OT_GRAPHQL = 'https://api.platform.opentargets.org/api/v4/graphql';

const DISEASE_TARGETS_QUERY = `
  query DiseaseTargets($efoId: String!, $size: Int!) {
    disease(efoId: $efoId) {
      id
      name
      associatedTargets(page: { index: 0, size: $size }) {
        rows {
          target { id approvedSymbol approvedName }
          score
          datatypeScores { id score }
        }
      }
      knownDrugs(size: $size) {
        rows {
          drug { id name }
          mechanismOfAction
          phase
          status
          ctIds
        }
      }
    }
  }
`;

const SEARCH_DISEASE_QUERY = `
  query SearchDisease($q: String!) {
    search(queryString: $q, entityNames: ["disease"], page: { index: 0, size: 5 }) {
      hits { id name entity }
    }
  }
`;

interface GraphqlResponse<T> {
  data?: T;
  errors?: Array<{ message: string }>;
}

interface SearchData {
  search: { hits: Array<{ id: string; name: string; entity: string }> };
}

interface DiseaseData {
  disease: {
    id: string;
    name: string;
    associatedTargets: {
      rows: Array<{
        target: { id: string; approvedSymbol: string; approvedName: string };
        score: number;
        datatypeScores: Array<{ id: string; score: number }>;
      }>;
    };
    knownDrugs: {
      rows: Array<{
        drug: { id: string; name: string };
        mechanismOfAction: string;
        phase: number;
        status: string;
        ctIds: string[];
      }>;
    } | null;
  };
}

async function gql<T>(query: string, variables: Record<string, unknown>): Promise<T> {
  const data = await fetchJson<GraphqlResponse<T>>(OT_GRAPHQL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ query, variables }),
  });
  if (data.errors?.length) {
    throw new Error(`Open Targets GraphQL error: ${data.errors.map((e) => e.message).join('; ')}`);
  }
  if (!data.data) throw new Error('Open Targets returned no data');
  return data.data;
}

export const queryOpenTargetsTool = tool({
  description:
    'Query Open Targets for disease-target-drug associations and genetic evidence. Pass a disease ' +
    'name (e.g. "cutaneous melanoma") and the tool resolves it to an EFO ID, then returns top ' +
    'associated targets and known drugs with mechanism + phase. Best for understanding the ' +
    'biological landscape of a cancer indication.',
  inputSchema: z.object({
    disease: z.string().describe('Disease name (e.g. "uveal melanoma")'),
    size: z.number().int().min(1).max(15).default(8),
  }),
  providerOptions: {
    anthropic: { cacheControl: { type: 'ephemeral' } },
  },
  execute: async ({ disease, size }) => {
    const search = await gql<SearchData>(SEARCH_DISEASE_QUERY, { q: disease });
    const hit = search.search.hits[0];
    if (!hit) {
      return { disease, resolved: null, targets: [], drugs: [] };
    }

    const result = await gql<DiseaseData>(DISEASE_TARGETS_QUERY, {
      efoId: hit.id,
      size,
    });

    return {
      disease,
      resolved: { efoId: result.disease.id, name: result.disease.name },
      targets: result.disease.associatedTargets.rows.map((r) => ({
        targetId:        r.target.id,
        symbol:          r.target.approvedSymbol,
        name:            r.target.approvedName,
        overallScore:    r.score,
        evidenceByType:  r.datatypeScores,
      })),
      drugs: (result.disease.knownDrugs?.rows ?? []).map((d) => ({
        drugId:            d.drug.id,
        name:              d.drug.name,
        mechanismOfAction: d.mechanismOfAction,
        phase:             d.phase,
        status:            d.status,
        nctIds:            d.ctIds,
      })),
    };
  },
});
