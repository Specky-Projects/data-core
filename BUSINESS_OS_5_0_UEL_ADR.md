# ADR — Business OS 5.0: Universal Execution Log (UEL)

**Status:** ACCEPTED  
**Date:** 2026-06-29  
**Author:** Principal Software Architect / Business OS Core Team  
**Supersedes:** None (new layer above 4.5 Scientific Kernel)

---

## Contexto

O Business OS administra múltiplos projetos (Poupi Crypto, Poupi Baby, Sinalo, futuros) e cada um
possui seus próprios eventos, logs, auditorias e históricos. Isso impede que o ecossistema enxergue
todas as execuções de forma uniforme e impossibilita aprendizado cruzado.

A camada 4.5 (Scientific Kernel) unificou evidência científica. A camada 5.0 unifica a *execução*
em si — toda ação realizada por qualquer projeto, representada por um único contrato canônico.

---

## Decisão

Criar o **Universal Execution Log (UEL)** como Business OS 5.0.

O UEL é a "caixa-preta" (flight recorder) oficial do ecossistema. Nenhum projeto o possui.
Todos o utilizam via adapter.

---

## Arquitetura

```
Poupi Crypto          Poupi Baby         Sinalo          [futuros]
     │                    │                 │                 │
CryptoUELAdapter    BabyUELAdapter   SinaloUELAdapter   UELAdapter
     └────────────────────┴─────────────────┴─────────────────┘
                                    │
                             UELRepository
                                    │
                         UniversalExecution (DTO)
                                    │
                       universal_executions (DB table)
```

### Princípios arquiteturais

| Princípio | Implementação |
|-----------|---------------|
| Canônico | `UniversalExecution` é o único contrato; nenhum projeto cria outro |
| Imutável | Status transitions são os únicos updates permitidos |
| Determinístico | `build_execution_id()` via SHA-256 sobre conteúdo — sem wall-clock |
| Versionado | `schema_version = "uel-v1-5.0"`, `uel_version = "business-os-5.0-..."` |
| Auditável | `lineage_hash`, `correlation_id`, `parent_execution_id` em todo registro |
| Independente do domínio | `ExecutionSurface` cobre Trading, SEO, Content, Affiliate, Social, Analytics, Research, Replay, Experiment, Simulation, Manual, API, Scheduler, Human Review, Autonomous, Workflow, External |

---

## Contrato canônico

```python
UniversalExecution(
    execution_id,          # uel:<sha256> — determinístico
    schema_version,        # uel-v1-5.0
    mission_id,
    portfolio_id,
    project_id,            # ProjectId enum
    capability_id,
    lineage,               # ExecutionLineage com lineage_hash
    execution_surface,     # ExecutionSurface enum (17 valores)
    execution_type,        # ExecutionType enum (23 valores)
    actor, planner, reviewer, executor,
    execution_plan_id, correlation_id, parent_execution_id, relation,
    timestamp, started_at, finished_at, duration_ms,
    status,                # UELStatus enum (11 estados)
    decision,              # UELDecision snapshot
    outcome,               # UELOutcome snapshot
    evidence_ids,          # lista de IDs (deduplicated)
    knowledge_ids,
    learning_ids,
    metrics,               # UELMetrics (latency, items, cost, quality)
    tags,                  # dict[str, str]
    uel_version,
)
```

---

## API canônica

```python
# Write
repo.emit_execution(EmitExecutionRequest)        # → UniversalExecution
repo.complete_execution(CompleteExecutionRequest) # → UniversalExecution
repo.fail_execution(FailExecutionRequest)         # → UniversalExecution
repo.rollback_execution(RollbackExecutionRequest) # → UniversalExecution
repo.attach_evidence(AttachRequest)               # → UniversalExecution
repo.attach_knowledge(AttachRequest)              # → UniversalExecution
repo.attach_learning(AttachRequest)               # → UniversalExecution

# Read
repo.query_execution(execution_id)               # → UniversalExecution | None
repo.query_executions(ExecutionQuery)            # → list[UniversalExecution]
repo.query_by_mission(mission_id)               # → list[UniversalExecution]
repo.query_by_capability(capability_id)         # → list[UniversalExecution]
repo.query_children(parent_execution_id)        # → list[UniversalExecution]
repo.dashboard()                                 # → UELDashboardReport
```

---

## Adapters por projeto

| Projeto | Adapter | Surface default | Type default |
|---------|---------|-----------------|--------------|
| Poupi Crypto | `CryptoUELAdapter` | TRADING | SIGNAL |
| Poupi Baby | `BabyUELAdapter` | ANALYTICS | DISCOVERY |
| Sinalo | `SinaloUELAdapter` | SEO | PUBLISH |
| Business OS interno | `BusinessOSUELAdapter` | AUTONOMOUS_DECISION | ORCHESTRATE |
| Futuros | `UELAdapter` (subclasse) | UNKNOWN | UNKNOWN |

---

## Estado da execução

```
PLANNED → APPROVED → RUNNING → SUCCESS
                             → FAILED
                             → ROLLBACK
                             → CANCELLED
                             → PARTIAL
SHADOW (paralelo, sem efeito)
SIMULATION (dry-run com saída)
ADVISORY (recomendação sem execução)
```

---

## Relações entre execuções

| Relação | Semântica |
|---------|-----------|
| PARENT / CHILD | Decomposição de execução |
| RETRY | Reexecução após falha |
| REPLAY | Reprodução determinística |
| ROLLBACK | Reversão para estado anterior |
| DERIVED | Execução gerada por outra |
| COUNTERFACTUAL | Hipótese alternativa |
| PARALLEL | Execução simultânea independente |

---

## Compatibilidade

O UEL **não substitui**:
- Logs específicos do Crypto (signal_outcomes, mirror trades)
- Auditorias do SIP (execution_runtime/auditor.py)
- Métricas do Omega
- Observabilidade do Poupi Baby

Ele atua como camada canônica **acima** deles, via adapter.

---

## Banco de dados

Tabela: `universal_executions`  
Migration: `0104_universal_execution_log`  
Down revision: `0033_merge_wnba_telegram`

Indexes principais:
- `uq_uel_execution_id` (unique)
- `ix_uel_project_surface` (composite)
- `ix_uel_project_status` (composite)
- `ix_uel_mission_capability` (composite)
- `ix_uel_timestamp_status` (composite)
- `ix_uel_active` (partial: status IN planned/approved/running)

---

## Alternativas consideradas

| Alternativa | Razão para rejeitar |
|-------------|---------------------|
| Cada projeto mantém seu log e um agregador lê todos | Não garante contrato canônico; quebra com novos projetos |
| Estender `collection_runs` com campos genéricos | JSONB overload; mistura semântica de coleta e execução |
| Estender `execution_runtime/persistence.py` | Esse módulo é específico do runtime 3.x; não serve para Sinalo/Baby |
| Log centralizado via Kafka/stream | Infraestrutura adicional; overkill para o estágio atual |

---

## Consequências

**Positivas:**
- Toda execução do ecossistema tem representação uniforme
- Dashboard cross-project nativo
- Lineage completa de qualquer decisão até seu resultado
- Replay e counterfactual por design
- Novos projetos adicionam apenas um adapter de poucas linhas

**Negativas / restrições:**
- Adapters precisam ser mantidos sincronizados com mudanças nos projetos
- `UELRepository` em memória — persistência real exige sessão SQLAlchemy + `UniversalExecutionRecord`
- Não substitui logs de baixo nível (debugging, stack traces)

---

## Arquivos criados

```
data-core/app/universal_execution_log/
├── __init__.py          — exports públicos
├── models.py            — contrato canônico (Pydantic DTOs)
├── db_models.py         — ORM SQLAlchemy (UniversalExecutionRecord)
├── repository.py        — UELRepository (in-memory)
├── adapters.py          — UELAdapter base + CryptoUELAdapter, BabyUELAdapter,
│                          SinaloUELAdapter, BusinessOSUELAdapter
└── tests/
    └── test_uel_stage_5_0.py   — 32 testes (32/32 passing)

data-core/alembic/versions/
└── 0104_universal_execution_log.py   — migration
```
