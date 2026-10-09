export interface Segment {
  text: string;
  hit: boolean;
}

/** Split `text` into segments, marking words that start with a query term (so "king" marks "kings"). */
export function highlight(text: string, terms: string[]): Segment[] {
  const roots = terms
    .map((t) => (t.length > 4 && t.endsWith('s') ? t.slice(0, -1) : t))
    .filter((t) => t.length > 1)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!roots.length) return [{ text, hit: false }];

  const re = new RegExp(`\\b(?:${roots.join('|')})\\w*`, 'gi');
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), hit: false });
    out.push({ text: m[0], hit: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), hit: false });
  return out;
}
