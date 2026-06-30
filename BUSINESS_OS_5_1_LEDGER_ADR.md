# ADR — Business OS 5.1: Universal Execution Log → Universal Execution Ledger

**Status:** ACCEPTED  
**Date:** 2026-06-29  
**Author:** Principal Software Architect / Business OS Core Team  
**Supersedes:** BUSINESS_OS_5_0_UEL_ADR.md (promoted, not replaced)

---

## Contexto

O Business OS 5.0 entregou o Universal Execution Log com contrato canônico e
repository in-memory (32/32 testes). A promoção para Ledger transforma essa
infraestrutura em fonte oficial de verdade, com persistência transacional.

---

## Decisão

Promover o Universal Execution Log para **Universal Execution Ledger (UEL)**.

O Ledger é a fonte oficial, imutável e auditável de todas as execuções do
ecossistema Business OS.

---

## Arquitetura pós-promoção

```
Poupi Crypto          Poupi Baby         Sinalo          Business OS
     │                    │                 │                 │
CryptoUELAdapter    BabyUELAdapter   SinaloUELAdapter   BusinessOSUELAdapter
     └────────────────────┴─────────────────┴─────────────────┘
                                    │
                         UELLedgerProtocol (Protocol)
                          /                    \
               UELRepository            UELDBRepository
             (in-memory, testes)    (SQLAlchemy, produção)
                                    │
                       universal_executions (PostgreSQL/Neon)
                                    │
                         ScientificLedgerBridge
                          /        |        \
               Replay Engine    Research   Knowledge
```

---

## Componentes entregues

| Componente | Arquivo | Função |
|------------|---------|--------|
| Protocolo | `protocol.py` | `UELLedgerProtocol` — interface estrutural |
| Ledger DB | `ledger.py` | `UELDBRepository` — SQLAlchemy persistente |
| Bridge | `scientific_bridge.py` | Read-only facade para Scientific Kernel |
| Health | `health.py` | `compute_uel_health()` + `UELHealthReport` |
| Tests | `tests/test_uel_ledger_stage_5_1.py` | 33 testes |

---

## Garantias do Ledger

| Garantia | Implementação |
|----------|---------------|
| Imutabilidade | Campos de identidade são write-once; apenas status transitions |
| Idempotência | `emit_execution()` retorna existente se `execution_id` duplicado |
| Determinismo | `build_execution_id()` SHA-256; `_ensure_utc()` para tz safety |
| Transacional | Caller controla commit/rollback (unit-of-work) |
| Intercambiabilidade | `UELLedgerProtocol` é satisfeito por ambas implementações |
| Performance | SQL-level aggregation no dashboard (sem full-table Python iteration) |

---

## Scientific Bridge

`ScientificLedgerBridge` expõe o Ledger ao Scientific Kernel via read-only projections:

- `load_execution_memory()` → Execution Memory ingestion
- `load_replay_corpus()` → Replay Engine
- `load_counterfactual_baseline()` → Counterfactual Engine
- `evidence_feed()` → Opportunity Discovery
- `learning_feed()` → Learning pipeline
- `research_feed()` → Research pipeline
- `opportunity_evidence()` → Mission-level outcome summary
- `load_experiments()`, `load_simulations()` → Experiment/Simulation views

---

## Compatibilidade

- API pública inalterada (nenhuma função removida ou assinatura alterada)
- `UELRepository` (in-memory) continua sendo a implementação padrão para testes
- `UELDBRepository` é drop-in replacement em produção via Protocol
- Adapters (Crypto, Baby, Sinalo, BusinessOS) aceitam ambos via duck typing

---

## Testes

| Suite | Testes | Status |
|-------|--------|--------|
| Stage 5.0 (in-memory) | 32 | 32/32 PASS |
| Stage 5.1 (SQLAlchemy) | 33 | 33/33 PASS |
| **Total** | **65** | **65/65 PASS** |

---

## Banco de dados

Migration: `0104_universal_execution_log` (corrigida: `PG_UUID` import)  
Tabela: `universal_executions`  
14 indexes (4 compostos + 1 partial)

---

## Veredito

```
STATUS: GO WITH OBSERVATIONS

Observações:
1. Deploy VPS/Coolify ainda pendente (migration não aplicada em produção)
2. Scientific Kernel não integrado (bridge preparada, integração é próximo passo)
3. Performance em alta concorrência não testada em PostgreSQL real

Bloqueadores: NENHUM para certificação local
```
