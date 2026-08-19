import { trialRoute } from '@/lib/constants';
import { NCT_ID_SOURCE } from './groundedness';

/**
 * Turns every bare NCT number in an answer into a link to its trial page.
 *
 * The agent is required to cite the identifier a tool result carried, so those
 * identifiers are the most navigable thing on the page - and until now they
 * were dead text.
 */

/** Only the fields this plugin reads. The full mdast types are not worth a dependency. */
interface MdastNode {
  type: string;
  value?: string;
  url?: string;
  children?: MdastNode[];
}

/**
 * Nodes whose text must be left alone: an NCT number inside a link is already
 * linked, and one inside code is being shown as literal text.
 */
const OPAQUE = new Set(['link', 'linkReference', 'definition', 'code', 'inlineCode']);

function splitOnNctIds(value: string, categorySlug: string): MdastNode[] {
  const pattern = new RegExp(NCT_ID_SOURCE, 'g');
  const parts: MdastNode[] = [];
  let cursor = 0;

  for (const match of value.matchAll(pattern)) {
    const start = match.index ?? 0;
    const nctId = match[0];
    if (start > cursor) parts.push({ type: 'text', value: value.slice(cursor, start) });
    parts.push({
      type: 'link',
      url: trialRoute(nctId, categorySlug),
      children: [{ type: 'text', value: nctId }],
    });
    cursor = start + nctId.length;
  }

  if (parts.length === 0) return [{ type: 'text', value }];
  if (cursor < value.length) parts.push({ type: 'text', value: value.slice(cursor) });
  return parts;
}

function linkifyChildren(parent: MdastNode, categorySlug: string): void {
  if (!parent.children) return;

  const next: MdastNode[] = [];
  for (const child of parent.children) {
    if (child.type === 'text' && child.value) {
      next.push(...splitOnNctIds(child.value, categorySlug));
      continue;
    }
    if (!OPAQUE.has(child.type)) linkifyChildren(child, categorySlug);
    next.push(child);
  }
  parent.children = next;
}

/** `remarkPlugins={[remarkGfm, remarkNctLinks(cancerType)]}` */
export function remarkNctLinks(categorySlug: string) {
  return () => (tree: MdastNode) => {
    linkifyChildren(tree, categorySlug);
  };
}
