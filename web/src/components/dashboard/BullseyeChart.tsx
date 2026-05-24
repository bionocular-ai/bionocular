'use client';

import * as React from 'react';
import type { DrugDot, PhaseRing } from '@/hooks/useBullseyeData';

export const CX = 500;
export const VIEWBOX_MIN = -200;
export const VIEWBOX_SIZE = 1400;
export const CY = 500;

// Ring radii: Phase1=outermost, Phase4=innermost.
export const RING_CONFIG: Record<PhaseRing, { outer: number; inner: number }> = {
  'Phase 1': { outer: 460, inner: 349 },
  'Phase 2': { outer: 349, inner: 238 },
  'Phase 3': { outer: 238, inner: 127 },
  'Phase 4': { outer: 127, inner: 15 },
};
const HUB_RADIUS = 15;
const RING_MIDPOINT = (r: PhaseRing) =>
  (RING_CONFIG[r].outer + RING_CONFIG[r].inner) / 2;
const RING_BAND = (r: PhaseRing) =>
  RING_CONFIG[r].outer - RING_CONFIG[r].inner;

// Outer geometry for the connector + sponsor-label layout
export const SECTOR_START_OFFSET = -Math.PI / 2; // 12 o'clock
const DIVIDER_OUTER = RING_CONFIG['Phase 1'].outer; // 460
const DIVIDER_INNER = HUB_RADIUS; // dividers go all the way to the hub
const CONNECTOR_START = 466;
const CONNECTOR_END = 492;

export function sectorMidAngle(index: number, total: number): number {
  const span = (2 * Math.PI) / Math.max(total, 1);
  return SECTOR_START_OFFSET + index * span + span / 2;
}

export function polar(cx: number, cy: number, r: number, angle: number) {
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
}

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

/** Deterministic angular position within a sector for dots sharing (phase, sponsor). */
function jitterAngle(
  baseMid: number,
  sectorSpan: number,
  _drug: DrugDot,
  index: number,
  total: number,
): number {
  if (total <= 1) return baseMid;
  const usable = sectorSpan * 0.7;
  const step = usable / total;
  const start = baseMid - usable / 2 + step / 2;
  return start + step * index;
}

/** Deterministic radial offset within a phase band; pseudo-randomised by drug name. */
function radialJitter(drug: DrugDot, band: number): number {
  const h = hashString(drug.drug_name);
  // Map hash → [-1, 1], then scale to ±35% of the band's half-width
  const t = ((h % 1000) / 999) * 2 - 1;
  return t * band * 0.35;
}

interface BullseyeChartProps {
  drugs: DrugDot[];
  sponsors: string[];
  phaseRings: PhaseRing[];
  colorOf: (value: string) => string;
  onHoverDrug: (drug: DrugDot | null, x: number, y: number) => void;
  onClickDrug: (drug: DrugDot) => void;
}

export function BullseyeChart({
  drugs,
  sponsors,
  phaseRings,
  colorOf,
  onHoverDrug,
  onClickDrug,
}: BullseyeChartProps) {
  const svgRef = React.useRef<SVGSVGElement>(null);

  const sponsorCount = Math.max(sponsors.length, 1);
  const sectorSpan = (2 * Math.PI) / sponsorCount;

  // Per-(phase, sponsor) dot groups for jitter
  const dotGroups = React.useMemo(() => {
    const map = new Map<string, DrugDot[]>();
    for (const drug of drugs) {
      const key = `${drug.phase}::${drug.sponsor}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(drug);
    }
    for (const [, list] of map)
      list.sort((a, b) => hashString(a.drug_name) - hashString(b.drug_name));
    return map;
  }, [drugs]);

  // Pastel-only gradient matching reference — airy outer, soft rose inner
  const ringColors: Record<PhaseRing, string> = {
    'Phase 1': '#fdf4fb',
    'Phase 2': '#f9d4ea',
    'Phase 3': '#f4a8cc',
    'Phase 4': '#ee86b4',
  };

  // Phase labels: vertical column at 12 o'clock (x=CX, y offset by ring midpoint)

  return (
    <svg
      ref={svgRef}
      viewBox="-200 -200 1400 1400"
      className="w-full h-full block"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <radialGradient id="bullseye-hub" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#fff5f7" />
        </radialGradient>
        <filter id="bullseye-dot-shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow
            dx="0"
            dy="1"
            stdDeviation="1.2"
            floodColor="#0f172a"
            floodOpacity="0.18"
          />
        </filter>
      </defs>

      {/* Ring fills — outermost drawn first so inner rings layer on top */}
      {phaseRings.map((phase) => {
        const { outer } = RING_CONFIG[phase];
        return (
          <circle
            key={phase}
            cx={CX}
            cy={CY}
            r={outer}
            fill={ringColors[phase]}
            stroke="none"
          />
        );
      })}

      {/* Center hub */}
      <circle cx={CX} cy={CY} r={HUB_RADIUS} fill="url(#bullseye-hub)" />
      <circle
        cx={CX}
        cy={CY}
        r={HUB_RADIUS}
        fill="none"
        stroke="#f9a8d4"
        strokeWidth={1}
        opacity={0.35}
      />

      {/* Ring borders (white separators between phases) */}
      {phaseRings.map((phase) => (
        <circle
          key={`border-${phase}`}
          cx={CX}
          cy={CY}
          r={RING_CONFIG[phase].outer}
          fill="none"
          stroke="#ffffff"
          strokeWidth={2}
          opacity={0.9}
        />
      ))}

      {/* Sector dividers — truncated: start at inner ring, end at outer ring */}
      {sponsors.map((_, i) => {
        const angle = SECTOR_START_OFFSET + i * sectorSpan;
        const start = polar(CX, CY, DIVIDER_INNER, angle);
        const end = polar(CX, CY, DIVIDER_OUTER, angle);
        return (
          <line
            key={`divider-${i}`}
            x1={start.x}
            y1={start.y}
            x2={end.x}
            y2={end.y}
            stroke="#ffffff"
            strokeWidth={1}
            opacity={0.7}
          />
        );
      })}

      {/* Connector stubs + perimeter sponsor labels */}
      {sponsors.map((sponsor, i) => {
        const mid = sectorMidAngle(i, sponsorCount);
        const start = polar(CX, CY, CONNECTOR_START, mid);
        const end = polar(CX, CY, CONNECTOR_END, mid);
        // Label position at r=540, text-anchor by quadrant
        const LABEL_R = 540;
        const lp = polar(CX, CY, LABEL_R, mid);
        const cosA = Math.cos(mid);
        const anchor: 'start' | 'end' | 'middle' =
          cosA > 0.25 ? 'start' : cosA < -0.25 ? 'end' : 'middle';
        const MAX_CHARS = 25;
        const label =
          sponsor.length > MAX_CHARS ? sponsor.slice(0, MAX_CHARS - 1) + '\u2026' : sponsor;
        return (
          <g key={`sponsor-${sponsor}-${i}`}>
            <line
              x1={start.x}
              y1={start.y}
              x2={end.x}
              y2={end.y}
              stroke="#cbd5e1"
              strokeWidth={0.75}
              opacity={0.9}
            />
            <text
              x={lp.x}
              y={lp.y}
              textAnchor={anchor}
              dominantBaseline="middle"
              fontSize={11}
              fill="#64748b"
              fontFamily="ui-sans-serif, system-ui, sans-serif"
              fontWeight={400}
              letterSpacing="0.01em"
            >
              {label}
            </text>
          </g>
        );
      })}

      {/* Phase labels — left horizontal plane (9 o'clock) */}
      {phaseRings.map((phase) => {
        const r = RING_MIDPOINT(phase);
        const pos = { x: CX - r, y: CY };
        const label = phase.replace('Phase ', 'P');
        return (
          <g key={`label-${phase}`}>
            <text
              x={pos.x}
              y={pos.y}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={10.5}
              fill="#475569"
              fontWeight={500}
              fontFamily="Georgia, 'Times New Roman', serif"
              letterSpacing="0.02em"
            >
              {label}
            </text>
          </g>
        );
      })}

      {/* Dots + compact drug-name labels */}
      {drugs.map((drug) => {
        const sponsorIdx = sponsors.indexOf(drug.sponsor);
        const sectorMid = sectorMidAngle(
          sponsorIdx >= 0 ? sponsorIdx : sponsors.length - 1,
          sponsorCount,
        );
        const key = `${drug.phase}::${drug.sponsor}`;
        const group = dotGroups.get(key) ?? [drug];
        const idxInGroup = group.findIndex((d) => d.drug_name === drug.drug_name);
        const angle = jitterAngle(sectorMid, sectorSpan, drug, idxInGroup, group.length);
        const r = RING_MIDPOINT(drug.phase) + radialJitter(drug, RING_BAND(drug.phase));
        const pos = polar(CX, CY, r, angle);
        const color = colorOf(drug.group_value);

        // Compact label: up to 8 chars, radially offset outward from the dot
        const MAX_LABEL = 15;
        const label =
          drug.drug_name.length > MAX_LABEL
            ? drug.drug_name.slice(0, MAX_LABEL - 1) + '…'
            : drug.drug_name;
        // Offset label center radially outward by dot radius + 14 SVG units
        const labelOffset = 7 + 14;
        const labelPos = polar(CX, CY, r + labelOffset, angle);

        return (
          <g
            key={drug.drug_name}
            className="cursor-pointer"
            onMouseEnter={() => {
              const svg = svgRef.current;
              if (!svg) return;
              const rect = svg.getBoundingClientRect();
              const scale = rect.width / VIEWBOX_SIZE;
              onHoverDrug(
                drug,
                (pos.x - VIEWBOX_MIN) * scale + rect.left,
                (pos.y - VIEWBOX_MIN) * scale + rect.top,
              );
            }}
            onMouseLeave={() => onHoverDrug(null, 0, 0)}
            onClick={() => onClickDrug(drug)}
          >
            <circle
              cx={pos.x}
              cy={pos.y}
              r={7}
              fill={color}
              filter="url(#bullseye-dot-shadow)"
            />
            <circle
              cx={pos.x}
              cy={pos.y}
              r={7}
              fill="none"
              stroke="#ffffff"
              strokeWidth={1.5}
            />
            {/* Drug name text */}
            <text
              x={labelPos.x}
              y={labelPos.y}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={8}
              fill="#334155"
              fontWeight={500}
              fontFamily="ui-sans-serif, system-ui, sans-serif"
              letterSpacing="0.01em"
            >
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
