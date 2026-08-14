# Cogmerge — brand

The palette is not decorative: four of the six colours carry a **meaning the
product already uses**, so a verdict looks the same in the terminal, in the
diagram, and on a badge.

## Palette

| Token | Hex | Meaning |
|---|---|---|
| **Cogmerge Violet** | `#6D4AFF` | Primary. Memory, the graph, anything Cogmerge stores or recalls. |
| **Signal Amber** | `#FFB020` | Attention. `MEDIUM` findings, landmines, the agent tier. |
| **Contradiction Red** | `#FF4D5E` | `HIGH` findings — a merge that must stop. Also Qdrant in diagrams. |
| **Merge Green** | `#2ECC8F` | All clear. `unrelated` verdicts, passing state. |
| **Graphite** | `#12121A` | Base surface. Diagram backgrounds, dark badges. |
| **Mist** | `#F4F4F8` | Light surface, primary text on Graphite. |

Supporting greys: `#1C1C28` (raised panel), `#2E2E42` (border), `#9A9AB0`
(secondary text).

### Why violet

Cognee's memory tier and Qdrant's vector tier both needed to be visible without
one swallowing the other. Violet reads as "memory / reasoning", Qdrant keeps the
red it owns, and amber is reserved so a warning never competes with brand chrome.

## Usage rules

1. **Violet is Cogmerge itself** — never use it for a verdict. A violet box means
   "this is our system", not "this is fine".
2. **Red only ever means a blocked merge.** Do not use it for generic errors.
3. **Green is earned.** Only for a real all-clear, never as a neutral accent —
   the product's credibility rests on `unrelated` being the honest common answer.
4. Diagrams sit on Graphite with a solid background so they render identically in
   GitHub's light and dark themes. Never rely on `prefers-color-scheme` inside an
   SVG embedded as `<img>` — GitHub follows the OS setting, not the page theme.

## Badges

shields.io, `style=flat-square`, colour picked by what the badge is *about*:

```markdown
![Cognee](https://img.shields.io/badge/memory-Cognee-6D4AFF?style=flat-square)
![Qdrant](https://img.shields.io/badge/vectors-Qdrant-FF4D5E?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-2ECC8F?style=flat-square)
```

## Type

System stack everywhere — `ui-sans-serif, system-ui, -apple-system, "Segoe UI",
Roboto, Helvetica, Arial, sans-serif`. SVGs are rendered as images by GitHub, so
no webfont will load; anything else silently falls back and breaks the layout.

## Assets

- [`workflow.svg`](./workflow.svg) — the SEAL / CHECK architecture diagram.
