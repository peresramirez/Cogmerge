# Cogmerge — brand

The palette is not decorative: four of the six colours carry a **meaning the
product already uses**, so a verdict looks the same in the terminal, in the
diagram, and on a badge.

## Palette

Two brand colours, one alarm colour, two surfaces. Nothing else.

| Token | Hex | Meaning |
|---|---|---|
| **Cogmerge Violet** | `#6D4AFF` | Primary. Memory, the graph, anything Cogmerge stores or recalls. |
| **Signal Amber** | `#FFB020` | The join key, and attention. The one shared node; `MEDIUM` findings. |
| **Contradiction Red** | `#FF4D5E` | `HIGH` findings — a merge that must stop. Nothing else, ever. |
| **Graphite** | `#12121A` | Base surface. Diagram backgrounds, the app tile, dark badges. |
| **Mist** | `#F4F4F8` | Light surface, primary text on Graphite. |

Supporting greys: `#1C1C28` (raised panel), `#2E2E42` (border), `#9A9AB0`
(secondary text).

### Why violet, and why no green

Violet reads as "memory / reasoning" and belongs to neither sponsor, so Cognee
and Qdrant can both appear without one swallowing the other. Amber is held back
for the single most important thing on any surface — the shared node — so a
highlight never competes with brand chrome.

Green was retired. It only ever meant "all clear", which is the *absence* of a
finding — and absence needs no colour. Dropping it takes the palette to three
inks and makes red unmistakable, because it is now the only alarm on the page.

## Usage rules

1. **Violet is Cogmerge itself** — never use it for a verdict. A violet box means
   "this is our system", not "this is fine".
2. **Red only ever means a blocked merge.** Never for generic errors.
3. **Amber marks the one thing that matters** in a given view. Two ambers on one
   surface means neither is the point.
4. Diagrams sit on Graphite with a solid background so they render identically in
   GitHub's light and dark themes. Never rely on `prefers-color-scheme` inside an
   SVG embedded as `<img>` — GitHub follows the OS setting, not the page theme.

## Badges

shields.io, `style=flat-square`, colour picked by what the badge is *about*:

```markdown
![Cognee](https://img.shields.io/badge/memory-Cognee-6D4AFF?style=flat-square)
![editors](https://img.shields.io/badge/works%20with-Claude%20Code%20%C2%B7%20Cursor-FFB020?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-12121A?style=flat-square)
```

Red is not a badge colour. A badge is a fact, not an alarm.

## Type

System stack everywhere — `ui-sans-serif, system-ui, -apple-system, "Segoe UI",
Roboto, Helvetica, Arial, sans-serif`. SVGs are rendered as images by GitHub, so
no webfont will load; anything else silently falls back and breaks the layout.

## Assets

| File | Use |
|---|---|
| [`logo.svg`](./logo.svg) | The mark. Transparent, no fills — reads on white and on dark. README, docs, slides. |
| [`logo-tile.svg`](./logo-tile.svg) | The mark on a Graphite tile. App icons, favicons, anywhere a background is composited for you. |
| [`logo-slack.png`](./logo-slack.png) | 1024×1024 render of the tile. Slack requires PNG, 512px minimum. |
| [`workflow.svg`](./workflow.svg) | The SEAL / CHECK architecture diagram. |

### The mark

A brain at a glance; a git merge up close. Two branches converge into one node,
and that node is amber because it *is* the product — the single code surface
where two developers who never spoke meet.

It is deliberately **not** a cog. A gear reads as "settings" or "build config",
which is the wrong promise: Cogmerge is about reasoning, not configuration. The
"cog" in the name is Cognee, and it does not need to be drawn.

Regenerate the PNG after editing the tile:

```bash
cd docs && qlmanage -t -s 1024 -o . logo-tile.svg && mv logo-tile.svg.png logo-slack.png
```
