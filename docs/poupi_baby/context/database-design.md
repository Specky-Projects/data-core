# Database Design

## Database Engine
PostgreSQL

# Database Principles

- Relational structure
- Historical data persistence
- Normalized entities
- Scalable indexing strategy

---
# Core Entities

## User

### Fields

- id
- name
- email
- password_hash
- role
- created_at

## Product

### Fields
- id
- title
- slug
- brand
- category
- image_url
- created_at

## Marketplace

### Fields
- id
- name
- base_url
- active

## Offer
- updated_at

## PriceHistory

### Fields
- id
- offer_id
- price
- captured_at


## Alert

### Fields
- id
- user_id
- product_id
- target_price
- active

## Subscription

### Fields

- id
- user_id
- plan
- status
- expires_at

---
---

# Relationships

- User → Alerts
- User → Subscription
- Product → Offers
- Offer → PriceHistory
- Marketplace → Offers

---
---

# Database Strategy

- Use indexes for heavy queries
- Cache expensive operations with Redis
- Historical data should be append-only
- Use soft delete when possible

---
---
# Future Improvements

- Full-text search
- Read replicas
- Table partitioning
- Analytics warehouse