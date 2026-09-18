# syntax=docker/dockerfile:1
# SÂNDÉ frontend — TanStack Start (Vite) dev server running under Bun.
#
# The repo's bun.lock resolves @lovable.dev/vite-tanstack-config from a
# Lovable-sandbox-only tarball URL (403 outside their infra). We pin that one
# package to the same version on the public npm registry via a temporary
# `overrides` entry, so `bun install` works in Docker without touching the
# repo's package.json / bun.lock.
FROM oven/bun:1

WORKDIR /app

ENV DOCKER=1

COPY vogue-vintage-vibes/package.json vogue-vintage-vibes/bun.lock vogue-vintage-vibes/bunfig.toml ./

RUN bun -e "const fs=require('fs');const p=JSON.parse(fs.readFileSync('package.json','utf8'));p.overrides=Object.assign({},p.overrides,{'@lovable.dev/vite-tanstack-config':'2.13.1'});fs.writeFileSync('package.json',JSON.stringify(p,null,2))" \
    && bun install

# Source comes from the bind mount in docker-compose (hot reload);
# node_modules from this image is preserved by an anonymous volume.
EXPOSE 5173

CMD ["bun", "x", "vite", "dev", "--host", "0.0.0.0", "--port", "5173"]
