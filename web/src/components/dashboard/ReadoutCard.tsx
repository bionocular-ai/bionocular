import Link from 'next/link';
import { trialRoute } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { MAX_SELECTED, type Arm, type Cell, type Endpoint, type Readout } from '@/lib/readouts';

/** Light rule, connector line and faint text: shades the brand tokens don't carry. */
const HAIR = 'border-[#E3EEEA]';
const SPINE = 'bg-[#9CC7B6]';
const FAINT = 'text-[#7F9BA5]';

/** Forest-plot axis for HRs: log scale from 0.1 to 1.5, dashed line at 1. */
const AXIS_MIN = 0.1;
const AXIS_MAX = 1.5;
const AXIS_W = 120;

function Forest({ hr, lo, hi }: { hr: number; lo?: number; hi?: number }) {
  const clamp = (v: number) => Math.min(AXIS_MAX, Math.max(AXIS_MIN, v));
  const x = (v: number) =>
    4 + ((Math.log(clamp(v)) - Math.log(AXIS_MIN)) / (Math.log(AXIS_MAX) - Math.log(AXIS_MIN))) * (AXIS_W - 8);
  return (
    <svg className="mt-[3px] block" width={AXIS_W} height={12} aria-hidden="true">
      <line x1={4} x2={AXIS_W - 4} y1={6} y2={6} stroke="#E3EEEA" strokeWidth={1.5} />
      <line x1={x(1)} x2={x(1)} y1={0} y2={12} stroke="#7F9BA5" strokeDasharray="2 2" />
      {lo != null && hi != null && (
        <line x1={x(lo)} x2={x(hi)} y1={6} y2={6} stroke="var(--brand-primary)" strokeWidth={1.5} />
      )}
      {lo != null && lo < AXIS_MIN && (
        <path d={`M${x(AXIS_MIN) - 3} 6l4-3v6z`} fill="var(--brand-primary)" />
      )}
      <circle cx={x(hr)} cy={6} r={3.5} fill="var(--brand-primary)" />
    </svg>
  );
}

function Dash() {
  return <span className="text-[15px] text-[#B4C6C0]" aria-label="Not reported">–</span>;
}

function Value({ endpoint, cell }: { endpoint: Endpoint; cell?: Cell }) {
  if (!cell) return <Dash />;
  if (cell.nr) return <span className="text-[17px] font-semibold leading-[1.1]">NR</span>;
  if (cell.value == null) return <Dash />;
  const isHr = endpoint.key === 'hr';
  return (
    <>
      <span className="whitespace-nowrap text-[17px] font-semibold leading-[1.1] tabular-nums">
        {cell.lt && '<'}
        {cell.value.toFixed(isHr ? 2 : 1)}
        {endpoint.unit && (
          <small className="ml-0.5 text-xs font-medium text-(--brand-text-muted)">
            {endpoint.unit === 'mo' ? ' mo' : '%'}
          </small>
        )}
      </span>
      {isHr && cell.lo != null && cell.hi != null && (
        <span className="mt-0.5 text-[11px] tabular-nums text-(--brand-text-muted)">
          {cell.lo.toFixed(2)} to {cell.hi.toFixed(2)}
        </span>
      )}
      {isHr && <Forest hr={cell.value} lo={cell.lo} hi={cell.hi} />}
    </>
  );
}

/**
 * CT.gov often records only a month, so show month and year. A date still
 * ahead of today can only be the registry's estimate.
 */
function Completion({ iso }: { iso: string | null }) {
  if (!iso) return <Dash />;
  const d = new Date(iso);
  const label = d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' });
  return (
    <>
      {label}
      {d > new Date() && <small className="block text-xs font-normal text-(--brand-text-muted)">Anticipated</small>}
    </>
  );
}

function Fact({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('min-w-0 border-t px-0 py-2.5 md:border-t-0 md:border-l md:px-4 md:py-[7px]', HAIR, className)}>
      <dt className="mb-px text-[11.5px] text-(--brand-text-muted)">{label}</dt>
      <dd className="m-0 text-[13px] font-medium [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

/** Spine cell: the CONSORT line from the analyzed N down to each group. The last group's stops at its branch. */
function Spine({ row, last, branch }: { row: number; last?: boolean; branch?: boolean }) {
  return (
    <div className="relative hidden md:block" style={{ gridColumn: 1, gridRow: row }} aria-hidden="true">
      <span className={cn('absolute left-[10px] top-0 w-[1.5px]', SPINE, last ? 'h-1/2' : 'h-full')} />
      {branch && <span className={cn('absolute left-[10px] top-1/2 h-[1.5px] w-[14px]', SPINE)} />}
    </div>
  );
}

function ArmRow({ arm, index, readout, maxN, last }: { arm: Arm; index: number; readout: Readout; maxN: number; last: boolean }) {
  const row = index + 2;
  return (
    <>
      <Spine row={row} last={last} branch />
      <div
        className={cn(
          'flex min-w-0 flex-col justify-center pt-3 pb-1 md:col-start-2 md:row-(--r) md:border-b md:py-[7px] md:pr-[18px] md:pl-1.5',
          HAIR,
          last && 'md:border-b-0',
        )}
        style={{ '--r': row } as React.CSSProperties}
      >
        <span className="text-[13.5px] font-semibold leading-[1.3]">{arm.name}</span>
        <span className="mt-0.5 flex items-center gap-2 text-xs text-(--brand-text-muted)">
          <span className={cn('text-[11.5px]', FAINT)}>Group {index + 1}</span>
          {arm.n != null && (
            <>
              <span>
                n = <span className="font-medium tabular-nums text-(--brand-text)">{arm.n}</span>
              </span>
              <i
                className="block h-1 min-w-[3px] rounded-sm bg-(--brand-accent)"
                style={{ width: maxN ? Math.round((arm.n / maxN) * 56) : 0 }}
              />
            </>
          )}
        </span>
      </div>
      <div
        className={cn(
          'grid grid-cols-2 pb-2 md:col-start-3 md:row-(--r) md:grid-cols-(--cols) md:border-b md:pb-0',
          HAIR,
          last && 'md:border-b-0',
        )}
        style={{ '--r': row, '--cols': `repeat(${readout.endpoints.length}, minmax(84px, 1fr))` } as React.CSSProperties}
      >
        {readout.endpoints.map((e) => (
          <div key={e.key} className="flex min-w-0 flex-col justify-center py-1.5 md:px-3 md:py-[7px]">
            <span className="mb-0.5 text-[11.5px] text-(--brand-text-muted) md:hidden">{e.label}</span>
            <Value endpoint={e} cell={arm.values[e.key]} />
          </div>
        ))}
      </div>
    </>
  );
}

/** One readout: an abstract or publication reporting a trial's results, one row per group. */
export function ReadoutCard({
  readout,
  category,
  selected,
  onToggle,
  selectDisabled,
}: {
  readout: Readout;
  category: string;
  selected: boolean;
  onToggle: () => void;
  /** The selection is full; only ticked cards can change. */
  selectDisabled?: boolean;
}) {
  const href = trialRoute(readout.nctId, category);
  const { arms } = readout;
  const maxN = Math.max(0, ...arms.map((a) => a.n ?? 0));
  const targets = readout.facets.target;

  return (
    <article
      className={cn(
        'rounded-[10px] border p-4 transition-colors md:px-[18px] md:pt-3.5 md:pb-3',
        selected ? 'border-(--brand-primary) bg-[#F3F9F6]' : 'border-(--brand-border) bg-(--brand-surface)',
      )}
    >
      <div className="flex flex-wrap items-start gap-2.5 md:items-center">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          disabled={selectDisabled && !selected}
          title={selectDisabled && !selected ? `Up to ${MAX_SELECTED} readouts can go to the agent at once` : undefined}
          aria-label={`Select ${readout.acronym ?? readout.drug ?? readout.nctId}, ${readout.source.label}`}
          className="mt-0.5 h-[15px] w-[15px] shrink-0 cursor-pointer accent-(--brand-primary) disabled:cursor-not-allowed md:mt-0"
        />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5 text-[13.5px] md:flex-row md:flex-wrap md:items-baseline md:gap-[7px]">
          {readout.acronym && (
            <>
              <Link href={href} className="text-[15px] font-semibold leading-[1.2] text-(--brand-primary) hover:underline hover:underline-offset-[3px]">
                {readout.acronym}
              </Link>
              <span className="hidden text-(--brand-border) md:inline">/</span>
            </>
          )}
          <span>
            {readout.drug}
            {targets.length > 0 && <span className="text-(--brand-text-muted)"> ({targets.join(' × ')})</span>}
          </span>
        </div>
        <div className="flex w-full flex-wrap gap-1.5 pl-[25px] md:ml-auto md:w-auto md:pl-0">
          {readout.phase && (
            <span className="inline-flex h-[22px] items-center rounded-[5px] bg-(--brand-primary) px-2 text-xs font-medium text-white">
              {readout.phase}
            </span>
          )}
          {readout.facets.setting.length > 0 && (
            <span className="inline-flex h-[22px] max-w-[240px] items-center truncate rounded-[5px] bg-(--brand-accent-light) px-2 text-xs font-medium text-(--brand-primary)">
              {readout.facets.setting[0]}
              {readout.facets.setting.length > 1 && <span className="ml-1 opacity-70">+{readout.facets.setting.length - 1}</span>}
            </span>
          )}
        </div>
      </div>

      {readout.title && (
        <h3 className="mt-1.5 mb-2.5 max-w-[80ch] text-[15.5px] font-semibold leading-[1.35] text-pretty">{readout.title}</h3>
      )}

      <dl className={cn('m-0 grid grid-cols-2 border-y md:grid-cols-[auto_repeat(4,minmax(0,1fr))]', HAIR)}>
        <Fact label="Analyzed participants" className="border-t-0 md:border-l-0 md:pl-0 md:pr-6">
          <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            {readout.analyzedN != null ? (
              <span className="whitespace-nowrap text-[22px] font-semibold leading-none tabular-nums">{readout.analyzedN}</span>
            ) : (
              <Dash />
            )}
            <span className="text-[12.5px] font-normal leading-tight text-(--brand-text-muted)">
              across {arms.length} {arms.length === 1 ? 'group' : 'groups'}
            </span>
          </span>
        </Fact>
        <Fact label="Source" className="border-t-0">
          {readout.source.label}
          {readout.source.detail && (
            <small className="block text-xs font-normal leading-[1.3] text-(--brand-text-muted)">{readout.source.detail}</small>
          )}
        </Fact>
        <Fact label="Trial number">
          <Link href={href} className="text-(--brand-primary) hover:underline">{readout.nctId}</Link>
        </Fact>
        <Fact label="Primary completion">
          <Completion iso={readout.completion} />
        </Fact>
        <Fact label="Sponsor" className="col-span-2 md:col-span-1">
          {readout.sponsor ?? <Dash />}
        </Fact>
      </dl>

      {readout.endpoints.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-[22px_260px_minmax(0,1fr)]">
          <Spine row={1} />
          <div
            className="hidden border-b-[1.5px] border-(--brand-text) md:col-span-2 md:grid md:grid-cols-[260px_minmax(0,1fr)]"
            style={{ gridRow: 1 }}
          >
            <div className="pt-2.5 pr-[18px] pb-[5px] pl-1.5 text-xs text-(--brand-text-muted)">Group</div>
            <div
              className="grid grid-cols-(--cols)"
              style={{ '--cols': `repeat(${readout.endpoints.length}, minmax(84px, 1fr))` } as React.CSSProperties}
            >
              {readout.endpoints.map((e) => (
                <div key={e.key} className="min-w-0 px-3 pt-2.5 pb-[5px] text-xs font-semibold">
                  {e.label}
                  {e.key === 'hr' && <small className="block font-normal text-(--brand-text-muted)">95% CI</small>}
                </div>
              ))}
            </div>
          </div>
          {arms.map((arm, i) => (
            <ArmRow key={i} arm={arm} index={i} readout={readout} maxN={maxN} last={i === arms.length - 1} />
          ))}
        </div>
      )}
    </article>
  );
}
