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
