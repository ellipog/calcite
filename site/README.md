# Calcite's website

The public site, and the brand guide and component sheet behind it. It's a Next.js app, built with bun, that reads the rest of the repo as it builds: the guide's Markdown, the plan, the benchmark results, the rig's cases and the sample plugins. Change those and the site follows on its next build. There's nothing to keep in sync by hand.

## Running it

```sh
cd site
bun install
bun run dev
```

The site is then at http://localhost:3000. Under `next dev` it also serves two internal pages, which a production build leaves out:

- `/brand`, the brand guide: the mark, colors, type, the Bayer patterns, motion and the charts;
- `/components`, every component the site is built from, in each of its states.

| Command | What it does |
|---|---|
| `bun run dev` | The site and the internal pages, reloading as files change |
| `bun run build` | Regenerates `src/lib/data.ts`, then builds the public site |
| `bun run build:internal` | The same, with the internal pages in it |
| `bun run start` | Serves the last build |
| `bun run typecheck` | TypeScript, without building |
| `bun run lint` | ESLint |
| `bun run data` | Regenerates `src/lib/data.ts` only |
| `bun run tiles` | Redraws the Bayer tiles in `src/styles/tiles.css` and the icons in `src/app/` |
| `bun run banner` | Redraws the repo README's banner, `assets/logo/calcite-banner.png` |

## Where each page comes from

| Page | Source |
|---|---|
| `/` | `src/app/(site)/page.tsx`, with numbers from `src/lib/data.ts`, the phases from `docs/PLAN.md`, the count of differences from `rig/differences/`, the count of cases for each step of world generation from `cases/<probe>/*.json` and the homes sample |
| `/benchmarks` | `src/lib/data.ts` |
| `/docs` and `/docs/*` | `docs/guide/*.md`, `docs/pregen.md` and `plugins/api/HOST_API.md`, in the order `docs/guide/README.md` lists them |
| `/plugins` | Sections of `plugins/api/HOST_API.md` and `plugins/samples/README.md`, and the samples' code |
| `/roadmap` | `docs/PLAN.md`'s table and phase sections, and the status line in the top-level `README.md` |

### Benchmark numbers

`scripts/data.ts` writes `src/lib/data.ts` from `bench/results/*.json` and from two places in `bench/README.md`: the light table, and the line that starts "At 868e0a0 these were". If either moves or changes shape the script stops with an error saying which, rather than build a page with wrong numbers. `src/lib/data.ts` is committed, so the site builds without running it, but `bun run build` always runs it first.

A newly recorded run (`py -I bench/<name>.py --record`) shows on the site with the next build.

### The guide

The pages in `docs/guide/` are plain Markdown and read fine on GitHub. On the site they're drawn by `src/lib/markdown.ts` and `src/components/markdown.tsx`, which handle what the repo's Markdown uses: headings, paragraphs, lists, tables, fenced code, quotes, links, inline code, bold and italics.

- A page's title and description come from its front matter. Without front matter, as in `docs/pregen.md`, the title is the first heading and the description is the first paragraph.
- Links to another file in the repo go to that file's page on the site if it has one, and to GitHub if not.
- A decision's id, such as D16, links to `docs/decisions.md` and shows the decision when pointed at.
- A line holding only an HTML comment is a directive that the page fills in. `<!-- calcite.properties -->` becomes a table of every setting in `calcite.properties`, read from `default_text()` in `src/server/config.calx`. `<!-- differences -->` becomes the list of deliberate differences from `rig/differences/`.

To add a page, write it in `docs/guide/` with front matter and add it to the list under "Pages" in `docs/guide/README.md`.

### The home page's world

The hero fills the first screen with a forest flown over. The flight itself, the camera, the chunks loading and the pacing, is `src/lib/brand/hero.ts`, which has no DOM in it. It runs in a worker, `src/lib/brand/hero.worker.ts`, on an OffscreenCanvas that `src/components/flyover.tsx` hands over, so drawing never holds up the page's scrolling or input. Where a worker can't draw, it runs on the page instead, and the same happens if the worker fails to start. The component makes a new canvas each time it mounts, since a canvas can be handed over only once. It's a new world on every visit, from a random seed, generated a chunk at a time by `src/lib/brand/blocks.ts`: rolling grass hills, rivers and lakes, sand on the shores, oaks and birches in vanilla's shape. Chunks load around the camera nearest first at the rate of the fastest recorded worldgen run, `DATA.worldgen.runs`' last, so the view fills in a fraction of a second and the chips under it say how many have loaded and how fast. It's drawn as voxel-space, one ray a screen column, with each block's top and sides shaded apart, fog toward the edge of the view and a flat layer of clouds. The camera flies where the pointer points: left or right of the middle of the picture turns the flight, faster the further out (at most 0.9 radians a second, at the picture's side), past a little room in the middle that flies straight, and the view leans a little into the turn. The flight keeps 24 blocks over the ground ahead whichever way it goes. On a touch screen a sideways drag steers. With no pointer the flight drifts on its own. Chunks load around wherever the camera has turned.

Each ray walks the block grid, visiting every block it crosses once, from the distance it comes in to the distance it leaves, so faces are drawn from their exact edges. Each column of blocks is one 32-bit word, so a ray reads memory once a block. A column stops once nothing in view could rise above what it has drawn. Every pixel is worked out once and written straight into the canvas's image as ink or nothing, with the edges' fade and the Bayer threshold folded into one table a row, so there's no tone buffer, no fade pass and no dither pass. The sky and clouds are worked out only where the land leaves them showing. The chunk store, about 2.4 MB for a window of 32×32 chunks, is allocated on first use rather than when the module loads.

If a reader hasn't scrolled after a few seconds, a chip at the bottom shows a block being mined, in ten stages of cracks, that crumbles into an arrow down, beside "more below"; pressing it scrolls to the next section. With reduced motion the world is drawn once and the chip shows the arrow.

The flight is paced to what a frame costs, so it doesn't drain a phone. In V8 on a fast desktop CPU, a frame takes about 1.8 ms at a phone's size, 5.3 ms at a laptop's, 6.5 ms at a desktop's and 14 ms at 4K, against 2.8, 7.6, 9.7 and 25.5 ms before the renderer was rewritten. A chunk takes about 40 µs to generate, and a frame generates at most 4 ms of them. On a screen big enough for more than 240,000 cells, the cells grow a pixel so the frame rate holds. It runs at 60 frames a second while a frame takes under 12 ms, 30 when it takes more and 20 past 24, and never more than 30 on a touch screen. The pointer's easing goes by time rather than by frame, so the camera turns as quickly at 30 frames a second as at 60.

With the flight in a worker, the page's main thread stays free. Measured on the production build in headless Edge over 8 seconds with the CPU slowed 4×, the page's frames came a median of 5.3 ms apart with four long tasks, all while loading. With the flight on the main thread they came 52 to 58 ms apart, with 79 to 91 long tasks blocking it for 5.2 to 5.6 of the 8 seconds. A touch screen's flight also rests after 30 seconds without a touch, holding its last frame, and a touch starts it again. With reduced motion, or with the browser's Save-Data on, it draws one still frame with the whole view generated. It stops whenever it's off screen or the tab is hidden.

### The strip of steps and the ground

By "Vanilla parity" a strip of a world runs across the window (`src/components/site/gen-steps.tsx`), each chunk a step further through vanilla's generation than the one to its left: structure starts, biomes, noise, surface, carvers, features and light, with chunks not yet begun to the left and finished ones to the right, out to the window's edges. The steps start on the frame's left edge, one to a chunk, with the rig's count of cases for each under it. Each step's chunk replays its step every 6.4 seconds, a little after the one before: a structure's box is drawn edge by edge, biomes arrive a 4×4 quart at a time, stone rises, grass and sand sweep across, a tunnel is bored along the chunk's front, ores are set and oaks grow log by log and then leaves, and light darkens the caves and the ground under the trees. Pointing at a chunk holds it finished. With reduced motion every chunk is drawn finished. Where seven chunks don't fit at a readable size, as on a phone, the strip scrolls sideways.

The world and its drawing are `src/lib/brand/slab.ts`, which has no DOM. The world is made once, with each step's blocks kept, and when each block changes within its step, so a chunk part way through a step is a lookup. The drawing is oblique: a block's front is square and its top and right side are seen at half depth. Faces are toned from above (tops lightest, right sides darkest) on the 4×4 Bayer matrix, aligned to the screen so a slanted top doesn't shear into stripes, and each block kind has its own marks: grass's ragged band down the sides and tufts on top, ore lumps, bark, holes in leaves, ripples and level lines on water, pebbles in gravel. Every cell keeps which plane of which block it shows and how near it is, and wherever two neighbouring cells differ the nearer gets an ink edge. So a terrace, a tree, an ore or a cave's mouth is a shape with an outline rather than a field of dots, and chunk borders show on the ground as the game's chunk-border view draws them. A face that looks into air under the ground is in a cave, and dark. The blocks are drawn nearest first, each face filling only the cells nothing nearer has, so a hidden cell is never worked out. On a fast desktop CPU a frame of the strip at 1920 px wide takes about 4 ms to draw, and about 6 ms with copying it to the canvas in a development build. It draws at most 15 frames a second, since blocks change one at a time, skips a frame in which no chunk has moved, and stops when it's out of view.

The footer's ground (`src/components/site/ground.tsx`) is a cut through another world from the same file, seen square on, from the treetops to bedrock, as wide as the window. It draws the first four blocks back, fainter in the open the further back they are, and the far walls of any cave or tunnel behind them, dark. Holding the pointer on a block mines it: ten stages of the same cracks as the hero's chip (`cracks()` in `slab.ts`), for about as long as a hand takes on that block, from 0.3 s for leaves to 2.6 s for deepslate. Then the block is gone and what's behind it shows, and if the pointer is still held the next one starts after a quarter of a second, as in the game. Bedrock and water can't be mined. The block under the pointer has a crisp outline, ink round it and paper just inside, so it shows on any block. The count of blocks mined replaces the hint in the corner. The world is made once the footer is within half a screen of the view, and the cut is drawn again only when something changes.

By "Performance" a band across the window is one tick (`src/components/site/tick-band.tsx`): its 50 ms are the window's width, and what 100 players took of it is marked to scale at its left end, solid to the mean, half-tone to the 99th percentile and a line at the longest, from `DATA.bots.windows`. It's plain CSS.

### The 404 page

An address with no page (`src/app/not-found.tsx`) shows a strip of a finished world across the window with one chunk missing in the middle, the chunk the address would be in (`src/components/site/lost-chunk.tsx`). A hash of the address picks the world's seed and the chunk's coordinates, within the world border, so each wrong address is somewhere else. After a moment the server generates the chunk anyway, a step every 1.25 s, as the home page's strip shows them, while a log under it ticks each step off. Its structure is the page's number: structure starts reserves its box, and features builds "404" in bricks a course at a time (`build()` in `slab.ts`). Its chunk is levelled first and kept clear of trees (`open` in the `Slab` constructor), as the game's terrain adaptation levels the ground around a village, so the number stands on flat grass against little else. The other chunks are drawn under half strength with dotted edges (`focus` in the view), so the eye goes to the hole. "Generate it again" replays the steps, and "go somewhere else" goes to another address that isn't a page, `/nowhere/` and six random letters, so another world. With reduced motion the chunk is drawn generated, with the whole log.

### The roadmap

`/roadmap` is rebuilt at most once an hour. On a rebuild it also reads Acta's public feed for the board and shows its tasks under "From the board", if any are marked public. With none, that section doesn't appear.

### Search and link previews

Each public page's title is its own name and then ` · calcite Minecraft server` (`SUFFIX` in `src/lib/meta.ts`), the words people search with; the home page's is `SITE.title`. Its description is cut to 160 characters, at a sentence's end where one ends late enough, so a search result shows all of it. The benchmarks, plugins and roadmap pages keep their titles and descriptions in `src/lib/pages.ts`; the docs take theirs from each page's front matter, or its heading and first paragraph. `meta()` gives every page its canonical address and the same title and description for link previews.

Every page has its own card, the picture a link to it shows: the mark and the name, the section, the page's title and what it's about, over a strip of the world, from `src/lib/og-card.tsx`. Each page's `opengraph-image.tsx` sits beside it, since a page that sets its own preview text no longer inherits a card from above it; the docs' pages share one, `docs/[slug]/opengraph-image.tsx`, made for each page as the site builds. Its alt text is the same for every page: `generateImageMetadata` would name each, but with it Next leaves the slug to request time, and the card can't read the docs from outside `site/` once it's deployed (CAL-171). The home page's card, `src/app/opengraph-image.tsx`, has the name large instead, and `(site)/opengraph-image.tsx` is the same card for the home page.

Each page also says what it is in structured data, a JSON-LD script from `src/lib/ld.tsx`. The home page describes the site, Aaen Studios and Calcite itself, as software for Minecraft: Java Edition under the Business Source License 1.1, linking the repository's LICENSE. Every other page gives its trail from the home page (`trail()`), and the docs' pages are articles about Calcite (`article()`), with the site and the studio again, as a search engine reads each page alone. A page of the docs is an article in link previews too, and it and the sitemap say when its file last changed in git (`changed()` in `src/lib/repo.ts`). In a shallow clone, as a host may build from, there's no date, since a file untouched since the clone's oldest commit would look as new as that commit.

`src/app/manifest.ts` tells a browser or a phone's home screen the site's name, icons and paper.

The repo README's banner, drawn by `scripts/banner.tsx`, is the home page's first screen, 1600 by 704: the kicker and the name on the left, the lead (`SITE.lead`) on the right, and under them the hero's own flight, its first frame over the world `BANNER_SEED` makes (`firstFrame()` in `src/lib/brand/hero.ts`), which shares the hero's look, so a change to the hero shows in the banner the next time it's drawn. The lead is set in Bricolage's regular weight, from `src/app/fonts/BricolageGrotesque-Regular.woff`, Google Fonts' Latin subset. The brand guide draws the same header live.

## How it's laid out

```text
src/app/(site)/        the public pages, with their header and footer
src/app/(internal)/    the brand guide and the component sheet (*.internal.tsx)
src/app/               the root layout, icons, the site's card, robots.txt and the sitemap
src/components/ui/     the components, each drawn in the brand's dither
src/components/site/   pieces of the public pages: the header, the footer and its ground, the strip of steps, the tick band, the charts, the page and docs navs
src/lib/               the brand's math and tiles, the Markdown parser, what's read from the repo
scripts/               data.ts, tiles.ts and banner.tsx
```

The internal pages' files end in `.internal.tsx`, which `next.config.ts` only counts as a page extension under `next dev` or with `CALCITE_INTERNAL=1`. A production build doesn't see them at all.

The footer's bottom bar credits Aaen Studios, which makes Calcite and Calx, and links to its site, `SITE.studio` in `src/lib/site.ts`. The studio's mark, in `src/components/aaen-mark.tsx`, is traced from `logo-mark.png` on aaenz.no and drawn in the footer's ink. Calx's site has the same credit.

### The frame

The public pages span the window. Their content sits in a frame up to 1920 px wide (`--frame` in `src/app/globals.css`), with `--side` between it and each edge of the window: the gutter on a narrow screen, and whatever is left over on a wider one. The `wrap` utility pads a block by `--side`, so its content is in the frame. Paragraphs keep their own measure, about 60 to 70 characters, however wide the frame gets. The extra width goes to structure:

- Each section of the home page and the plugins page is a `Band` (`src/components/site/parts.tsx`), whose dotted rule runs from one edge of the window to the other. So do the roadmap's phases, with the phase in progress on a solid rule.
- A wide head is split as the hero is, with the title on the left and the lead on the right: `SectionHead` with `split`, and `PageHead`. Anything beside a table or a chart under such a head uses the same columns (`SPLIT_XL`), so text in the right-hand column starts on the lead's line down the whole page.
- The `bleed-r`, `bleed-l` and `bleed` utilities take something in the frame out to the window's edge. The home page's stats run their rules across the window (`Stats` with `bleed`), as do the tick band by "Performance" and the strip of steps by "Vanilla parity", whose chunks run out to both edges.
- Grids get more columns as the width grows: the home page's features go four across, the plugin API's needs go as many across as fill every row, and a roadmap phase's checklist sits beside its gate.
- On a wide screen the benchmarks page lists its sections in a sticky column on the left (`src/components/site/page-nav.tsx`), marking the one being read. On a narrower one they're a row of chips under the head.
- The footer's ground runs from one edge of the window to the other and stands on the bottom bar's rule.

The docs, being for reading, keep the old 1200 px frame, as do the internal pages: an element with `data-frame="narrow"` sets `--frame` and `--side` again for everything in it. The header and footer still span the window there.

### Speed

PageSpeed Insights gave the home page 100 for performance on desktop and 99 on mobile on 2026-11-05, and 100 for accessibility, best practices and SEO on both. Lighthouse 13.6 run locally on the production build gives the same. What it still points out, and why it stays:

- **Render-blocking CSS.** The stylesheet is one file, about 15 KB compressed. Next's experimental `inlineCss` would put it in the HTML instead, but three times over, once as `<style>` and twice in the RSC payload, so 104 KB of HTML became 328 KB. On Lighthouse's mobile run the first paint then came 120 ms later and blocking time went from 24 to 123 ms, so it's off (`next.config.ts`).
- **Legacy JavaScript, 14 KiB.** Next's own polyfill module, which every app gets. It checks for each feature before adding it, so a current browser runs none of it.
- **Unused JavaScript, 28 KiB.** In React and Next's shared chunk.
- **A long task about 3 s in.** React hydrating the page, about 25 ms on a fast desktop CPU.
- **Two non-composited animations, on mobile.** The marches (`march-8` and `march-16` in `globals.css`) are the work-under-way patterns on the phase in progress and the "running" tag. Where a CSS pixel is a whole number of the screen's pixels, as at 100% and 200%, a march slides a `::before` with a transform, which the compositor runs without painting. Elsewhere, as at 125%, 150% or Lighthouse's emulated 175% phone, the compositor resamples that layer and the dots blur: up to 78% of a cell's pixels came out neither ink nor paper. So there the background moves instead, as it always did, painted on the main thread. `MarchWatch` (`src/components/ui/march-watch.tsx`) holds every march still while it's off screen, so a phase strip far down the page doesn't have the page painted 12 times a second.

Bricolage Grotesque is loaded with its weight and optical-size axes only. The type is never condensed, and the width axis was 54 KB of the 131 KB font file.

The panels of `Tabs` dissolve in only when picked, not as the page loads.

Every page also sends `Strict-Transport-Security` for the domain and its subdomains, `Cross-Origin-Opener-Policy: same-origin`, and a content security policy that allows no plugins, no `<base>`, forms only to this site and no framing. It doesn't restrict scripts: that would take a nonce on each of Next's inline scripts, which makes every page dynamic. HSTS isn't marked `preload`, since getting on browsers' preload list is a separate request that's hard to undo.

## Deploying

The site is built to deploy on Vercel, but any host that runs Next.js 16 works. On Vercel:

- **Root directory:** `site`.
- **Include files outside the root directory in the build step:** on. The site reads `../docs`, `../bench`, `../cases`, `../plugins`, `../rig` and `../src` as it builds, so the whole repo has to be checked out.
- **Install command:** `bun install`. **Build command:** `bun run build`.
- **Environment:** nothing. The site's address, `https://calcitemc.com`, is `SITE.url` in `src/lib/site.ts`; canonical links, the sitemap, robots.txt and the cards' addresses use it from every build, preview deploys and local ones included.

Every page is static except `/roadmap`, which is regenerated in the background when it's more than an hour old.
