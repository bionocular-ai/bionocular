import { tool } from 'ai';
import { z } from 'zod';
import { fetchJson } from './fetch-with-retry';

const CHEMBL = 'https://www.ebi.ac.uk/chembl/api/data';

interface ChemblMolecule {
  molecule_chembl_id: string;
  pref_name: string | null;
  max_phase: number | null;
  molecule_type: string | null;
  first_approval: number | null;
  molecule_synonyms?: Array<{ molecule_synonym: string; syn_type: string }>;
}

interface ChemblSearchResponse {
  molecules?: ChemblMolecule[];
  page_meta?: { total_count?: number };
}

export const searchChemblTool = tool({
  description:
    'Search ChEMBL for drugs, compounds, and bioactivity. Use for: mechanism of action, ' +
    'compound chemistry, approval status (max_phase), drug-target affinity. Best when you have ' +
    'a compound name (generic or brand) or a known target.',
  inputSchema: z.object({
    query: z.string().describe('Compound name, e.g. "encorafenib", "trastuzumab"'),
    limit: z.number().int().min(1).max(20).default(5),
  }),
  providerOptions: {
    anthropic: { cacheControl: { type: 'ephemeral' } },
  },
  execute: async ({ query, limit }) => {
    const url = `${CHEMBL}/molecule/search.json?q=${encodeURIComponent(query)}&limit=${limit}`;
    const data = await fetchJson<ChemblSearchResponse>(url);

    return {
      query,
      total: data.page_meta?.total_count ?? 0,
      molecules: (data.molecules ?? []).map((m) => ({
        chemblId:      m.molecule_chembl_id,
        prefName:      m.pref_name,
        maxPhase:      m.max_phase,
        moleculeType:  m.molecule_type,
        firstApproval: m.first_approval,
        synonyms:      (m.molecule_synonyms ?? []).slice(0, 5).map((s) => s.molecule_synonym),
      })),
    };
  },
});
