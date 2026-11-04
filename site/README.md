# Calcite's website

The public site, and the brand guide and component sheet behind it. It's a Next.js app, built with bun, that reads the rest of the repo as it builds: the guide's Markdown, the plan, the benchmark results and the sample plugins. Change those and the site follows on its next build. There's nothing to keep in sync by hand.

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

## Where each page comes from

| Page | Source |
|---|---|
| `/` | `src/app/(site)/page.tsx`, with numbers from `src/lib/data.ts`, the phases from `docs/PLAN.md`, the count of differences from `rig/differences/` and the homes sample |
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

The hero fills the first screen with a forest flown over. The flight itself, the camera, the chunks loading and the pacing, is `src/lib/brand/hero.ts`, which has no DOM in it. It runs in a worker, `src/lib/brand/hero.worker.ts`, on an OffscreenCanvas that `src/components/flyover.tsx` hands over, so drawing never holds up the page's scrolling or input. Where a worker can't draw, it runs on the page instead, and the same happens if the worker fails to start. The component makes a new canvas each time it mounts, since a canvas can be handed over only once. It's a new world on every visit, from a random seed, generated a chunk at a time by `src/lib/brand/blocks.ts`: rolling grass hills, rivers and lakes, sand on the shores, oaks and birches in vanilla's shape. Chunks load around the camera nearest first at the rate of the fastest recorded worldgen run, `DATA.worldgen.runs`' last, so the view fills in a fraction of a second and the chips under it say how many have loaded and how fast. It's drawn as voxel-space, one ray a screen column, with each block's top and sides shaded apart, fog toward the edge of the view and a flat layer of clouds. The pointer turns the camera.

Each ray walks the block grid, visiting every block it crosses once, from the distance it comes in to the distance it leaves, so faces are drawn from their exact edges. Each column of blocks is one 32-bit word, so a ray reads memory once a block. A column stops once nothing in view could rise above what it has drawn. Every pixel is worked out once and written straight into the canvas's image as ink or nothing, with the edges' fade and the Bayer threshold folded into one table a row, so there's no tone buffer, no fade pass and no dither pass. The sky and clouds are worked out only where the land leaves them showing. The chunk store, about 2.4 MB for a window of 32×32 chunks, is allocated on first use rather than when the module loads.

If a reader hasn't scrolled after a few seconds, a chip at the bottom shows a block being mined, in ten stages of cracks, that crumbles into an arrow down, beside "more below"; pressing it scrolls to the next section. With reduced motion the world is drawn once and the chip shows the arrow.

The flight is paced to what a frame costs, so it doesn't drain a phone. In V8 on a fast desktop CPU, a frame takes about 1.8 ms at a phone's size, 5.3 ms at a laptop's, 6.5 ms at a desktop's and 14 ms at 4K, against 2.8, 7.6, 9.7 and 25.5 ms before the renderer was rewritten. A chunk takes about 40 µs to generate, and a frame generates at most 4 ms of them. On a screen big enough for more than 240,000 cells, the cells grow a pixel so the frame rate holds. It runs at 60 frames a second while a frame takes under 12 ms, 30 when it takes more and 20 past 24, and never more than 30 on a touch screen. The pointer's easing goes by time rather than by frame, so the camera turns as quickly at 30 frames a second as at 60.

With the flight in a worker, the page's main thread stays free. Measured on the production build in headless Edge over 8 seconds with the CPU slowed 4×, the page's frames came a median of 5.3 ms apart with four long tasks, all while loading. With the flight on the main thread they came 52 to 58 ms apart, with 79 to 91 long tasks blocking it for 5.2 to 5.6 of the 8 seconds. A touch screen's flight also rests after 30 seconds without a touch, holding its last frame, and a touch starts it again. With reduced motion, or with the browser's Save-Data on, it draws one still frame with the whole view generated. It stops whenever it's off screen or the tab is hidden.

The other pictures drawn on the page, such as the relief map by "Vanilla parity", wait until they're within a screen of the view and then for the browser to be idle, so the world they're built from (about 55 ms of work) isn't made while the page is loading.

### The roadmap

`/roadmap` is rebuilt at most once an hour. On a rebuild it also reads Acta's public feed for the board and shows its tasks under "From the board", if any are marked public. With none, that section doesn't appear.

## How it's laid out

```text
src/app/(site)/        the public pages, with their header and footer
src/app/(internal)/    the brand guide and the component sheet (*.internal.tsx)
src/app/               the root layout, icons, the social card, robots.txt and the sitemap
src/components/ui/     the components, each drawn in the brand's dither
src/components/site/   pieces of the public pages: the header, the footer, the charts, the docs nav
src/lib/               the brand's math and tiles, the Markdown parser, what's read from the repo
scripts/               data.ts and tiles.ts
```

The internal pages' files end in `.internal.tsx`, which `next.config.ts` only counts as a page extension under `next dev` or with `CALCITE_INTERNAL=1`. A production build doesn't see them at all.

The footer's bottom bar credits Aaen Studios, which makes Calcite and Calx, and links to its site, `SITE.studio` in `src/lib/site.ts`. The studio's mark, in `src/components/aaen-mark.tsx`, is traced from `logo-mark.png` on aaenz.no and drawn in the footer's ink. Calx's site has the same credit.

## Deploying

The site is built to deploy on Vercel, but any host that runs Next.js 16 works. On Vercel:

- **Root directory:** `site`.
- **Include files outside the root directory in the build step:** on. The site reads `../docs`, `../bench`, `../plugins`, `../rig` and `../src` as it builds, so the whole repo has to be checked out.
- **Install command:** `bun install`. **Build command:** `bun run build`.
- **Environment:** `SITE_URL`, the site's address with no trailing slash, such as `https://calcite.example`. Canonical links, the sitemap and the social card's address use it. Without it Vercel's production address is used.

Every page is static except `/roadmap`, which is regenerated in the background when it's more than an hour old.
