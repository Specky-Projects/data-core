# Poupi Baby Domain

Backend interface migrada do projeto `poupi`.

Este dominio preserva a interface backend NestJS e o worker de filas como referencia operacional e contrato de produto, sem trazer frontend para o Data Core.

## Mapa

```text
domains/poupi_baby/
  backend/          # NestJS backend original: controllers, services, modules, Prisma
  worker/           # Worker Node/BullMQ original
  interface.py      # Manifest Python usado pelo Data Core e por agentes de IA
```

## Interface no Data Core

- `GET /api/v1/poupi-baby`
- `GET /api/v1/poupi-baby/modules`
- `GET /api/v1/poupi-baby/endpoints`

## Regras

- Nao mover frontend para este dominio.
- Nao versionar `.env`, `node_modules`, builds, bancos locais ou logs.
- Codigo novo do Data Core deve integrar este dominio por adaptadores em `api/`, `collectors/` ou `workers/`.
- O backend TypeScript migrado e referencia/contrato. Runtime principal deste repositorio continua Python/FastAPI.
- Se uma feature do Poupi Baby virar collector, crie um adapter Python em `collectors/ecommerce`.

