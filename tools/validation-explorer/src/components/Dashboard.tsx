import type { ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { decisionBreakdown, failRateByField, missedValuesCount, scoreHistogram } from '@/lib/aggregate'
import { cn } from '@/lib/cn'
import { DECISION_DOT_CLASS } from '@/lib/decision-style'
import type { FieldEvalRow, TrialRow } from '@/lib/types'
import { StatTile } from './StatTile'

// Chart chrome + data colors, per the dataviz reference palette (light chart surface).
// Gridline/axis/tick tokens keep chrome recessive; the FAIL-rate series is an
// error-rate metric so it wears the fixed "critical" status color (never categorical);
// the score histogram is an ordered set of buckets, so it takes the sequential blue
// ramp (ordinal steps 250->700) with lightness carrying the bucket order.
const CHART_GRIDLINE = '#e1e0d9'
const CHART_AXIS = '#c3c2b7'
const CHART_TICK = '#898781'
const CHART_LABEL = '#52514e'
const STATUS_CRITICAL = '#d03b3b'
const ORDINAL_BLUE_RAMP = [
  '#86b6ef',
  '#6da7ec',
  '#5598e7',
  '#3987e5',
  '#2a78d6',
  '#256abf',
  '#1c5cab',
  '#184f95',
  '#104281',
  '#0d366b',
]

const tooltipContentStyle = {
  fontSize: 12,
  borderRadius: 8,
  border: '1px solid #e2e8f0',
  boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
}
const tooltipCursor = { fill: 'rgba(15, 23, 42, 0.04)' }

function ChartCard({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
  return (
    <section className={cn('rounded-lg border border-slate-200 bg-white p-4')}>
      <h2 className={cn('mb-3 text-sm font-medium text-slate-700')}>{title}</h2>
      {empty ? (
        <p className={cn('py-10 text-center text-sm text-slate-400')}>No data matches the current filters.</p>
      ) : (
        children
      )}
    </section>
  )
}

export function Dashboard({
  trials,
  fieldEvals,
  metadata,
}: {
  trials: TrialRow[]
  fieldEvals: FieldEvalRow[]
  metadata: Record<string, unknown>
}) {
  const breakdown = decisionBreakdown(trials)
  const byField = failRateByField(fieldEvals).map((r) => ({ ...r, pct: Math.round(r.rate * 100) }))
  const hist = scoreHistogram(trials)
  const cost = typeof metadata.total_cost_usd === 'number' ? metadata.total_cost_usd : null
  const tokens = typeof metadata.total_tokens === 'number' ? metadata.total_tokens : null

  return (
    <div className={cn('space-y-6')}>
      <div className={cn('grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6')}>
        {breakdown.map((b) => (
          <StatTile
            key={b.decision}
            label={b.decision}
            value={b.count}
            accentClassName={DECISION_DOT_CLASS[b.decision]}
          />
        ))}
        <StatTile label="trials w/ missed" value={missedValuesCount(trials)} />
        {cost !== null && <StatTile label="cost (final proc)" value={`$${cost.toFixed(2)}`} />}
        {tokens !== null && <StatTile label="tokens (final proc)" value={tokens.toLocaleString()} />}
      </div>

      <ChartCard title="FAIL rate by field (%)" empty={byField.length === 0}>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={byField} margin={{ top: 16, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid vertical={false} stroke={CHART_GRIDLINE} />
            <XAxis
              dataKey="field"
              tick={{ fontSize: 11, fill: CHART_TICK }}
              tickLine={false}
              axisLine={{ stroke: CHART_AXIS }}
              interval={0}
              angle={-30}
              textAnchor="end"
              height={70}
            />
            <YAxis
              tick={{ fontSize: 11, fill: CHART_TICK }}
              tickLine={false}
              axisLine={{ stroke: CHART_AXIS }}
              width={36}
              allowDecimals={false}
            />
            <Tooltip
              cursor={tooltipCursor}
              contentStyle={tooltipContentStyle}
              formatter={(value, _name, item) => [
                `${value}% (${item.payload.fail}/${item.payload.total} FAIL)`,
                'fail rate',
              ]}
            />
            <Bar dataKey="pct" fill={STATUS_CRITICAL} radius={[4, 4, 0, 0]} maxBarSize={28}>
              <LabelList
                dataKey="pct"
                content={(props) => {
                  const { x, y, width, value, index } = props
                  if (index !== 0 || typeof x !== 'number' || typeof y !== 'number' || typeof width !== 'number') {
                    return null
                  }
                  return (
                    <text x={x + width / 2} y={y - 6} textAnchor="middle" fontSize={11} fill={CHART_LABEL}>
                      {value}%
                    </text>
                  )
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Validation score distribution" empty={trials.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={hist} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={CHART_GRIDLINE} />
            <XAxis
              dataKey="bucket"
              tick={{ fontSize: 11, fill: CHART_TICK }}
              tickLine={false}
              axisLine={{ stroke: CHART_AXIS }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: CHART_TICK }}
              tickLine={false}
              axisLine={{ stroke: CHART_AXIS }}
              width={36}
              allowDecimals={false}
            />
            <Tooltip
              cursor={tooltipCursor}
              contentStyle={tooltipContentStyle}
              formatter={(value) => [`${value}`, 'trials']}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={28}>
              {hist.map((entry, i) => (
                <Cell key={entry.bucket} fill={ORDINAL_BLUE_RAMP[Math.min(i, ORDINAL_BLUE_RAMP.length - 1)]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  )
}
