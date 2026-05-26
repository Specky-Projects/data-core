# Frontend Stabilization Plan

Last verified: 2026-05-26

## Scope

This document captures the current operational risks in `poupi-frontend` and the safe path to make frontend deploys reproducible without reintroducing notebook runtime dependency.

The local frontend workspace appears to be a pnpm/turbo monorepo with apps under `apps/*` and shared packages under `packages/*`.

## Current Findings

- A local Git repository now exists at `C:\Users\dev\Documents\Projetos\poupi-frontend`.
- Baseline branch: `main`.
- Baseline commit: `92b2d56 chore: establish frontend baseline`.
- GitHub remote is configured:
  - `https://github.com/poupi-hub/poupi-frontend.git`
- Initial CI workflow exists at `.github/workflows/ci.yml`.
- Branch `main` was pushed to GitHub.
- GitHub Actions CI is green on `main`.
- Latest green run: `26453842683`.
- Branch protection for `main` requires `Frontend checks`, strict status checks, no force pushes and no branch deletion.
- `apps/poupi-baby` now has a production Dockerfile in the frontend monorepo.
- `apps/poupi-baby` exposes a minimal `/health` endpoint.
- Local Docker image build was verified with `docker build -f apps\poupi-baby\Dockerfile -t poupi-frontend-baby:local .`.
- Coolify application `poupi-frontend-baby` exists and deploys from `poupi-hub/poupi-frontend.git` branch `main`.
- Coolify application UUID: `wsp5l6d144vs27lz7p37b1hk`.
- Current generated URL: `http://wsp5l6d144vs27lz7p37b1hk.65.109.239.250.sslip.io`.
- Remote `/health` was verified healthy on 2026-05-26.
- Real `.env.local` files exist under multiple frontend apps:
  - `apps/crypto-dashboard/.env.local`
  - `apps/poupi-baby/.env.local`
  - `apps/quant-dashboard/.env.local`
  - `apps/real-estate-dashboard/.env.local`
  - `apps/sports-dashboard/.env.local`
- Initial audit found multiple code paths falling back to localhost endpoints:
  - `http://localhost:8000`
  - `http://localhost:3001`
- Localhost development fallback is now centralized in helper/client code and fails fast in production.
- `README.md` documents per-app `.env.local` usage, but there is no verified production env contract or CI/CD flow in this local copy.
- Safe env examples were added to the local frontend workspace:
  - root `.env.example`;
  - per-app `.env.local.example` files.
- A production guardrail script was added:
  - `scripts/check-production-localhost.mjs`;
  - root package script `check:prod-env`.
- `npm run check:prod-env` now passes locally.
- `npx --yes pnpm@9.15.0 check:prod-env` passes.
- `npx --yes pnpm@9.15.0 typecheck` passes for the monorepo.
- `npx --yes pnpm@9.15.0 lint` passes for the monorepo with warnings only in `apps/poupi-baby`.
- `npx --yes pnpm@9.15.0 build` passes for the monorepo.

## Operational Risk

Classification: `PARTIAL`

The frontend can likely be developed locally, but it is not yet production-operationally mature because:

- Deploy reproducibility is proven locally, GitHub CI is green, branch protection is active, and the first Coolify deploy is healthy.
- Runtime endpoints were previously able to silently point to localhost if env vars were missing; production now fails fast in the centralized helpers.
- Secrets may remain scattered in local `.env.local` files.
- Different apps may build against different implicit API targets.

## Target State

- `poupi-frontend` is a normal Git repository with a known remote origin.
- Production builds run in CI/CD or on the server, never from an implicit notebook state.
- All production API targets are explicit and injected by the deployment platform.
- Local `.env.local` files contain only non-sensitive local development values.
- Safe examples exist as `.env.example` or `.env.local.example`.
- No production build can silently fallback to localhost.

## Required Environment Contract

Minimum expected variables:

```env
NEXT_PUBLIC_API_URL=https://<public-api-host>
BACKEND_URL=http://<internal-backend-service>:<port>
NEXT_PUBLIC_SITE_URL=https://<public-frontend-host>
NEXT_PUBLIC_SENTRY_DSN=
SENTRY_DSN=
```

Rules:

- `NEXT_PUBLIC_*` values are browser-visible and must not contain secrets.
- `BACKEND_URL` is server-side only and should point to an internal service URL in production.
- Missing production endpoint variables should fail fast during build/startup.
- Localhost fallback is acceptable only under explicit local development mode.

## Migration Plan

### Phase 1 - Version Control

1. Keep `.env.local`, `.env.production`, `.next`, `node_modules`, and build artifacts ignored.
2. Keep Coolify/CI deploy from GitHub.

### Phase 2 - Env Hygiene

1. Move any real local secrets out of the repository tree.
2. Create per-app `.env.local.example` files with safe placeholders.
3. Document production variables in one root `.env.example`.
4. Validate that no secret values are committed.

### Phase 3 - Remove Silent Localhost Fallbacks

1. Introduce a shared config helper that:
   - allows localhost defaults only in development;
   - requires explicit URLs in production;
   - rejects malformed URLs.
2. Keep repeated `process.env.BACKEND_URL || 'http://localhost:3001'` and `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'` patterns out of app routes and pages.
3. Add tests or static checks for prohibited production localhost fallback.

### Phase 4 - Reproducible Build

1. Standardize package manager on pnpm.
2. Verify `pnpm install --frozen-lockfile`.
3. Verify `pnpm build`.
4. Add CI checks for lint, typecheck, and build.
5. Build/deploy from CI or server, not from notebook-only state. Initial Coolify deploy is verified.

### Phase 5 - Deployment

1. Define one deploy target per app.
2. Inject env vars through Coolify/CI secrets.
3. Confirm Traefik routes and TLS for each frontend.
4. Validate `/`, `/health`, and API proxy routes.
5. Replace generated `sslip.io` URL with stable DNS after domain ownership is confirmed.

## Immediate Safe Next Actions

Run these before changing frontend code:

```powershell
Get-ChildItem -Force C:\Users\dev\Documents\Projetos\poupi-frontend
Get-ChildItem -Recurse -Force C:\Users\dev\Documents\Projetos\poupi-frontend -Filter .git
rg -n "localhost|127\.0\.0\.1|BACKEND_URL|NEXT_PUBLIC_API_URL" C:\Users\dev\Documents\Projetos\poupi-frontend
cd C:\Users\dev\Documents\Projetos\poupi-frontend
npm run check:prod-env
```

Then keep verifying:

- GitHub branch protection for `main`.
- Coolify/CI deploy from GitHub rather than notebook-only state.
- Remote frontend health at `http://wsp5l6d144vs27lz7p37b1hk.65.109.239.250.sslip.io/health`.

## Do Not Do Yet

- Do not delete local `.env.local` files until safe examples exist and secrets are moved.
- Do not add new localhost fallbacks outside the centralized helper/client code.
- Do not deploy a frontend build from this local folder outside the Git/Coolify flow.
- Do not expose backend-only URLs as `NEXT_PUBLIC_*`.
