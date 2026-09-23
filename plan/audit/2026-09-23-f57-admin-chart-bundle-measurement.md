# Audit — F5.7 Admin chart bundle split (2026-09-23)

## Task

`F5.7` (P2, Batch D). The task list says recharts (~553 kB raw) and lodash (~164 kB)
are "pulled into the shared bundle for the dashboard alone". The backlog's required
workflow:

1. measure the production bundle;
2. identify the actual contributors;
3. apply evidence-based splitting;
4. build again;
5. compare.

It also says not to assume lodash is a direct dependency and not to remove
dependencies blindly. Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

The spec names recharts for the dashboard (`[FE-03]` bento/KPI and charts), and that
stays. There is no bundle-budget rule. The stack header is ignored as always.

## Outcome

**No code change.** The problem described no longer exists in this build.

- **Route split already in place.** TanStack Router's automatic route splitting gives
  the dashboard route (`admin.index.tsx`) its own chunk, and recharts and lodash live
  only there.
- **Only `/admin` loads it.** The SSR manifest preloads that chunk only for
  `/_authenticated/admin/`. The entry chunk references it through a lazy `import()`.
- **The experiment was slower.** The one further split available (lazy-loading the
  two charts inside the dashboard) was built and measured on the production build. It
  made the dashboard **slower**, so it was reverted.

## Measurements

### 1. Production bundle (`bun run build`, the committed code)

| Chunk | Raw | Gzip | Loaded by |
| --- | ---: | ---: | --- |
| `index-*.js` (shared entry) | 394.05 kB | 121.49 kB | every page |
| `admin.index-*.js` (dashboard route) | 405.71 kB | 106.31 kB | `/admin` only |
| `utils-*.js` | 27.26 kB | 8.69 kB | every page |
| all client JS (77 files) | 1 254.8 kB | 393.1 kB | — |

The byte signatures `recharts-wrapper` and `__lodash_hash_undefined__` appear **only**
in `admin.index-*.js`.

### 2. Contributors (sourcemap build, bytes attributed per package)

- **`admin.index-*.js`** (396 kB mapped):

  | Package | Size |
  | --- | ---: |
  | recharts | 249.1 kB |
  | lodash | 29.5 kB |
  | react-smooth | 18.4 kB |
  | d3-scale | 14.6 kB |
  | d3-shape | 13.4 kB |
  | decimal.js-light | 12.6 kB |
  | d3-time-format, d3-color, fast-equals, recharts-scale, d3-format, d3-time, d3-array | ≤ 8.8 kB each |
  | dashboard code (`src/routes`) | 6.2 kB |

  lodash is **transitive** through recharts. It is not in `package.json`, and only the
  functions recharts uses are bundled.
- **Shared entry** (385 kB mapped): react-dom 170.9 kB, route definitions 31.9 kB,
  sonner 31.9 kB, `src/components` 20.2 kB, seroval 19.4 kB, then TanStack Query,
  Router and Start, and floating-ui. **No chart code.**
- `src/components/ui/chart.tsx` (the shadcn wrapper) imports recharts but nothing
  imports it, so it is tree-shaken out of every bundle.

### 3. Runtime

Setup: production build served from Node (the `.output` worker's `fetch` plus gzip
static assets). Chromium was throttled to 1.6 Mbps / 150 ms with the cache off, and
signed in as admin. Each `/admin` figure is the median of 5 loads.

`--disable-web-security` was used only because the backend CORS-allows the dev
origin `:5173` and the build was served on `:3999`. Both variants ran identically.

| `/admin` | committed (route chunk preloaded) | experiment (charts lazy, import started on route load) |
| --- | ---: | ---: |
| JS transferred | 295.0 kB | 295.4 kB |
| `GET /admin/kpis` sent | 3 245 ms | 3 260 ms |
| KPI values visible | **3 616 ms** | 4 432 ms |
| latest orders visible | 3 690 ms | 4 694 ms |
| charts visible | **3 713 ms** | 4 756 ms |

| Other pages (unthrottled) | JS transferred | recharts loaded |
| --- | ---: | --- |
| `/` | 198.3 kB | no |
| `/shop` | 206.4 kB | no |
| `/admin/orders` | 202.1 kB | no |
| `/admin/products` | 203.7 kB | no |

### Why the split lost

The KPI requests are gated by auth and the admin shell, at about 3.25 s in both
variants. The route chunk is not on that path: the SSR HTML modulepreloads it next to
the entry, so it has already arrived when the data comes back.

Moving recharts behind a dynamic import removes it from the preload list. Its 104 kB
(gzip) then starts downloading exactly when the KPI and stats requests go out, and
competes with them.

The experiment also moved `tailwind-merge` (27 kB) from `utils-*.js` into the entry.
That is neutral per page (one request fewer, same bytes), and it was reverted with
the rest.

## Files changed

- Code: **none** (the experiment was reverted; the final build is byte-identical,
  with the same chunk hashes as the baseline).
- Docs: this audit, `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`.

## How to verify

1. `cd infra && docker compose exec -T frontend bun run build`. It succeeds, and
   `admin.index-*.js` is the only chunk that contains `recharts-wrapper`:

   ```sh
   grep -l recharts-wrapper .output/public/assets/*.js
   ```

2. `.output/server/_tanstack-start-manifest_v-*.mjs` lists `admin.index-*.js` only
   under `"/_authenticated/admin/"`.
3. In a browser, open `/`, `/shop`, `/admin/orders` and `/admin/products`: no
   `admin.index-*.js` request.

**Verification level:** measured on the production build — no code change needed.

## What is NOT done / open

- The dashboard still downloads about 104 kB gzip of charting. The only ways to cut
  it are a lighter chart library or hand-drawn SVG. That is a product/design choice,
  not a bundling fix, so no backlog item was added.
- The unused `src/components/ui/chart.tsx` was left in place (R12; it costs nothing
  in the bundle).
- `README.md`, `FEATURES.md`, `DESIGN_SYSTEM.md`, `feature-roadmap.md`: untouched.
