# Architecture

Poupi Baby uses a modular monorepo with a single backend prepared for multiple verticals. The first vertical is baby products.

## Stack

- Node.js
- TypeScript
- NestJS
- PostgreSQL
- Redis
- BullMQ

## Shape

- `systems/backend`: NestJS API, domain modules, schedulers and queue producers
- `systems/worker`: worker runtime for background processing
- `systems/frontend`: Next.js frontend
- `prisma`: shared database schema and migrations
- `docs`: product and system context

## Backend

The backend is the source of truth for products, offers, alerts, price history, marketplaces and operational state.

It should stay as a single modular service during the MVP. Modules communicate through service boundaries and domain events instead of direct cross-module orchestration wherever practical.

## Event-Driven Flow

Price collection produces domain events such as price updates, back-in-stock and out-of-stock changes.

Listeners react asynchronously to:

- check alerts
- update deal scoring
- record analytics
- notify users

## Crawling

The crawler monitors only curated offers. It does not crawl full catalogs.

Each job targets one known offer URL and uses a deterministic scraper strategy for the matching store.

## Database

PostgreSQL stores:

- users
- products
- marketplaces
- offers
- price history
- alerts
- subscriptions
- operational scraper metrics

## Cache and Queues

Redis supports:

- BullMQ queues
- crawler rate limiting
- temporary price cache
- short-lived operational state

## Future Evolution

Future verticals should reuse the same backend primitives: product, offer, marketplace, price history and alert.

Microservices, AI pipelines and catalog discovery are future options, not MVP requirements.
