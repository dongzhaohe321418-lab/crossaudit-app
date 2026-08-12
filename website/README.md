# CrossAudit website

The public product site for CrossAudit. It explains the independent audit loop,
keeps advanced capabilities progressively disclosed, and resolves the current
macOS installer and checksum from the official GitHub Releases API.

Production: <https://crossaudit-v4.vercel.app>

If GitHub's API is unavailable or rate-limited, every download control falls
back to the repository's official `releases/latest` URL rather than a third-party
mirror.

## Local development

```bash
npm ci
npm run dev
```

## Building

Two independent build paths exist; both must work from a clean clone:

- `npm run build` — vinext + Cloudflare Worker runtime (what `npm test`
  serves). It loads `vite.config.ts`, which needs the Sites packaging plugin
  in `lib/sites-vite-plugin.ts`. The plugin lives in `lib/` and not the
  starter's original `build/` directory because the repository root
  `.gitignore` ignores `build/` — the original location was never committed,
  which broke every fresh checkout.
- `npm run build:vercel` — plain `next build` for the Vercel runtime. It
  never loads `vite.config.ts`, so it does not need the plugin.

## Validation

```bash
npm run lint
npm test
npm run build:vercel
```

The production build targets the Sites/Cloudflare Worker runtime declared in
`.openai/hosting.json`. The separate `build:vercel` target validates the same
source with the standard Next.js production runtime before Vercel deployment.
No credentials are needed to build or browse the site.

## Vercel release gate

Only deploy after all three validation commands pass. The local `.vercel`
binding is intentionally ignored by Git and connects this folder to the user's
Vercel project without storing account credentials in the source tree.

```bash
npm run release:vercel
```
