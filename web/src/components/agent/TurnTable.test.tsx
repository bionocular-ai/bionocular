import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { toTurnTable } from '@/lib/agent/turn-table';
import { TurnTable } from './TurnTable';

const arm = (id: string, armName: string, values: unknown) => ({ id, source_id: 'ASH_2025_1', nct_id: 'NCT1', arm_name: armName, values });
const heme = (rows: unknown[]) => ({ ok: true, table: 'arm_outcomes', rows });

describe('TurnTable subgroups', () => {
  it('draws subgroup values in a collapsed table under the arms', () => {
    const table = toTurnTable([
      heme([
        arm('a1', 'Tafasitamab', { response_rates: [{ field: 'CR', value: '50' }, { field: 'CR', value: '70', context: 'POD24' }] }),
        arm('a2', 'Placebo', { response_rates: [{ field: 'CR', value: '40' }] }),
      ]),
    ])!;
    const html = renderToStaticMarkup(<TurnTable table={table} cancerType="follicular-lymphoma" />);
    const [main, details] = html.split('<details');
    expect(main).toContain('>CR<');
    expect(main).not.toContain('CR (POD24)');
    expect(details).toMatch(/^ class="[^"]*"><summary[^>]*>Subgroups \(1\)<\/summary>/);
    expect(details).toContain('CR (POD24)');
    expect(details).toContain('Tafasitamab');
    expect(details).not.toContain('Placebo');
  });

  it('draws no disclosure without subgroup values', () => {
    const table = toTurnTable([heme([arm('a1', 'A', { response_rates: [{ field: 'CR', value: '50' }] })])])!;
    expect(renderToStaticMarkup(<TurnTable table={table} cancerType="follicular-lymphoma" />)).not.toContain('<details');
  });
});
