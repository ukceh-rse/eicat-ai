import type { Element as HastElement, ElementContent, Root, RootContent, Text } from 'hast'

// Maps rendered paper text back to character offsets in the paper markdown (design D8). Every hast text node is
// wrapped in <span data-n data-o>: data-n indexes the node's value-to-source offset map in the registry, data-o is
// where this piece starts within the node's value (a node is split into pieces where highlights begin and end).

export interface SourceSpan { start: number; end: number }

export interface OffsetRegistry {
  // per text node: source offset of each value character, or null when the node has no usable position
  maps: (number[] | null)[]
  // per text node: source start offset of the node, or of its nearest positioned ancestor
  starts: number[]
}

export const newRegistry = (): OffsetRegistry => ({ maps: [], starts: [] })

const TABLE_PARTS = new Set(['table', 'thead', 'tbody', 'tfoot', 'tr'])

const isSpace = (c: string) => c === ' ' || c === '\n' || c === '\t' || c === '\r'

// Rendered text drops characters from its source (backslash escapes, entity syntax, continuation-line indentation,
// code-span backticks), so align greedily: each value character takes the next matching source character.
export function align(value: string, src: string, base: number): number[] | null {
  const map: number[] = []
  let j = 0
  // index by UTF-16 unit, as DOM selection offsets are
  for (const c of value.split('')) {
    while (j < src.length && src[j] !== c && !(isSpace(c) && isSpace(src[j]))) j++
    if (j >= src.length) return null
    map.push(base + j++)
  }
  return map
}

function covered(map: number[] | null, start: number, end: number, i: number, spans: SourceSpan[]) {
  if (map) return spans.some((s) => map[i] >= s.start && map[i] < s.end)
  return spans.some((s) => s.start < end && s.end > start)
}

export function rehypeSourceOffsets(options: { markdown: string; registry: OffsetRegistry; highlights?: SourceSpan[] }) {
  const { markdown, registry, highlights = [] } = options
  return (tree: Root) => {
    registry.maps.length = 0
    registry.starts.length = 0
    const walk = (node: Root | HastElement, inherited: number) => {
      const start = node.position?.start.offset ?? inherited
      node.children = (node.children as (RootContent | ElementContent)[]).flatMap((child): (RootContent | ElementContent)[] => {
        if (child.type === 'element') {
          walk(child, start)
          return [child]
        }
        if (child.type !== 'text') return [child]
        // a span is not allowed between table rows and cells, and the renderer drops this whitespace anyway
        if (node.type === 'element' && TABLE_PARTS.has(node.tagName) && !child.value.trim()) return [child]
        return wrap(child, start)
      }) as typeof node.children
    }
    const wrap = (text: Text, inherited: number): HastElement[] => {
      const p = text.position
      const s = p?.start.offset
      const e = p?.end.offset
      const map = s !== undefined && e !== undefined ? align(text.value, markdown.slice(s, e), s) : null
      const n = registry.maps.length
      registry.maps.push(map)
      registry.starts.push(s ?? inherited)
      // split the value into runs that are uniformly inside or outside the highlights
      const pieces: HastElement[] = []
      let from = 0
      for (let i = 1; i <= text.value.length; i++) {
        const prev = covered(map, s ?? inherited, e ?? inherited, i - 1, highlights)
        if (i < text.value.length && covered(map, s ?? inherited, e ?? inherited, i, highlights) === prev) continue
        const piece: Text = { type: 'text', value: text.value.slice(from, i) }
        pieces.push({
          type: 'element',
          tagName: 'span',
          properties: { dataN: n, dataO: from },
          children: prev ? [{ type: 'element', tagName: 'mark', properties: {}, children: [piece] }] : [piece],
        })
        from = i
      }
      return pieces
    }
    walk(tree, 0)
  }
}

function mapOf(registry: OffsetRegistry, text: Node): number[] | null {
  const wrapper = text.parentElement?.closest<HTMLElement>('[data-n]')
  const map = wrapper ? registry.maps[Number(wrapper.dataset.n)] : null
  return map && map.length > 0 ? map : null
}

// Resolves a DOM selection endpoint to a source offset, or null when the endpoint's node cannot be mapped.
function endpointOffset(registry: OffsetRegistry, root: HTMLElement, node: Node, offset: number, isEnd: boolean): number | null {
  // an endpoint on an element points between its children: move to the nearest text node inside the selection
  if (node.nodeType !== Node.TEXT_NODE) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    const boundary = document.createRange()
    boundary.setStart(node, offset)
    let pick: Node | null = null
    while (walker.nextNode()) {
      // skip the unpositioned whitespace between blocks, e.g. where a triple-click ends on the next paragraph
      if (!mapOf(registry, walker.currentNode) || !walker.currentNode.textContent?.trim()) continue
      const before = boundary.comparePoint(walker.currentNode, 0) < 0
      if (isEnd && before) pick = walker.currentNode
      if (!isEnd && !before) { pick = walker.currentNode; break }
    }
    if (!pick) return null
    node = pick
    offset = isEnd ? (pick.textContent ?? '').length : 0
  }
  const map = mapOf(registry, node)
  if (!map) return null
  const i = Number(node.parentElement!.closest<HTMLElement>('[data-n]')!.dataset.o) + offset
  if (isEnd) return i === 0 ? map[0] : map[i - 1] + 1
  return i < map.length ? map[i] : map[map.length - 1] + 1
}

function nearestStart(registry: OffsetRegistry, node: Node): number {
  const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : (node as HTMLElement)
  const wrapper = el?.closest<HTMLElement>('[data-n]') ?? el?.querySelector<HTMLElement>('[data-n]')
  return wrapper ? registry.starts[Number(wrapper.dataset.n)] : 0
}

// Converts the current selection inside `root` to a span of the markdown. Falls back to searching the markdown
// for the selected text near the selection's start when an endpoint cannot be mapped.
export function selectionToSpan(markdown: string, registry: OffsetRegistry, root: HTMLElement): SourceSpan | null {
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null
  const range = sel.getRangeAt(0)
  if (!root.contains(range.commonAncestorContainer)) return null
  const start = endpointOffset(registry, root, range.startContainer, range.startOffset, false)
  const end = endpointOffset(registry, root, range.endContainer, range.endOffset, true)
  if (start !== null && end !== null && end > start) return { start, end }
  const selected = sel.toString().trim()
  if (!selected) return null
  const near = Math.max(0, nearestStart(registry, range.startContainer) - 200)
  const at = markdown.indexOf(selected, near)
  return at >= 0 ? { start: at, end: at + selected.length } : null
}
