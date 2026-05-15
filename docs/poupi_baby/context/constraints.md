# Constraints

## Technical Constraints

- MVP must use modular monolith architecture
- APIs must follow REST standards
- PostgreSQL is the primary database
- Infrastructure must prioritize low operational cost
- Crawlers must support async processing
- Services must be containerized with Docker


## Product Constraints

- MVP is web-only
- Initial integrations are limited
- AI features will be basic initially
- Free plan has limited alerts and history


## Operational Constraints

- Crawlers must respect rate limits
- Price updates are not real-time guaranteed
- System must tolerate temporary marketplace failures


## Scalability Constraints

- Crawlers must scale independently
- Heavy processes must be async
- Cache layer must reduce repetitive queries