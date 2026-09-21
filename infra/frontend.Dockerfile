# syntax=docker/dockerfile:1
# SÂNDÉ frontend — TanStack Start (Vite) dev server running under Bun.
#
# The repo's bun.lock resolves every package (including @lovable.dev/*) from the
# public npm registry since 2026-09-21, so a plain `bun install` is enough — the
# overrides injection that used to work around the Lovable-sandbox tarball was
# removed. If the lockfile ever regresses to a private tarball URL, `bun install`
# will fail loudly here instead of silently drifting from the repo's lockfile.
FROM oven/bun:1

WORKDIR /app

ENV DOCKER=1

COPY vogue-vintage-vibes/package.json vogue-vintage-vibes/bun.lock vogue-vintage-vibes/bunfig.toml ./

RUN bun install

# Source comes from the bind mount in docker-compose (hot reload);
# node_modules from this image is preserved by an anonymous volume.
EXPOSE 5173

CMD ["bun", "x", "vite", "dev", "--host", "0.0.0.0", "--port", "5173"]
