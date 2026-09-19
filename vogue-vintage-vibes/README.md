# SÂNDÉ — frontend (`vogue-vintage-vibes/`)

The store UI: TanStack Start (React 19) + TypeScript + Tailwind CSS 4 +
shadcn/ui, talking to the FastAPI backend in `../backend` (the sole backend — no
Supabase).

## Documents

- [FEATURES.md](./FEATURES.md) — full feature list (Persian) and known gaps.
- [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) — design tokens, component inventory,
  and UI conventions. **Read this before adding UI.**
- [src/routes/README.md](./src/routes/README.md) — file-based routing rules.
- [AGENTS.md](./AGENTS.md) — Lovable sync note (don't rewrite pushed history).

## Development

This project uses **Bun** (`bun.lock`). You can also run it via the container
stack in `../infra`.

```sh
bun install
bun run dev          # dev server on http://localhost:5173
bun run build
bun run lint
bun run format
```

The API base is read from `VITE_API_URL` (SSR fallback `VITE_BACKEND_URL`,
default `http://localhost:8000`). See `src/lib/api.ts` — the single data layer
for every backend endpoint.

> `bun.lock` pins `@lovable.dev/vite-tanstack-config` to a Lovable-sandbox-only
> tarball; `../infra/frontend.Dockerfile` overrides it for the public registry.
> `vite.config.ts` is intentionally minimal — the Lovable config injects the
> plugins, so don't add them manually.
