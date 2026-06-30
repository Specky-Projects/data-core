# ADR — ScientificIdentity Contract
**ID:** ADR-SCIENTIFIC-IDENTITY-2026-06-30
**Status:** ACCEPTED
**Deciders:** Arquiteto-Chefe Científico
**Phase:** 2.2 — Scientific Foundation Consolidation

---

## Contexto

O ecossistema possui múltiplos identificadores locais independentes:
- `canonical_decision_id` (SIP)
- `outcome_id` (ExecutionRuntime)
- `claimId` (BusinessOS)
- `entity_id` (Knowledge)
- `session_id` (ExecutionRuntime)

Nenhum conecta integralmente o ciclo de vida de uma decisão desde a
primeira observação até o conhecimento final. Isso torna impossível
rastrear a cadeia completa: Observation → Evidence → Decision → Outcome → Learning → Knowledge.

---

## Decisão

Criar `ScientificIdentity` como identidade científica universal para toda
entidade produzida pela plataforma.

### Princípios

1. **Determinística** — o mesmo `entity_type + entity_id + lineage_id + producer + schema_version` produz sempre o mesmo `scientific_id`. Seguro para replay.
2. **Imutável** — `ScientificIdentity` é um `dataclass(frozen=True)`. Nunca alterada após criação.
3. **Chain** — `ScientificIdentityChain` conecta entidades do mesmo `lineage_id` em ordem de produção.
4. **Adapter-first** — nenhum objeto existente é modificado. Adapters convertem legacy → ScientificIdentity.
5. **Não intrusiva** — a identidade existe em paralelo às implementações operacionais. Não substitui nenhuma delas.

### Entity Types suportados

OBSERVATION | CONTEXT | EVIDENCE | CLAIM | DECISION | COMMITTEE |
PREVIEW | EXECUTION | OUTCOME | REPLAY | LEARNING | EXPERIMENT | KNOWLEDGE

### Fluxo canonical esperado

```
OBSERVATION → CONTEXT → EVIDENCE → CLAIM → DECISION → COMMITTEE →
PREVIEW → EXECUTION → OUTCOME → REPLAY → LEARNING → EXPERIMENT → KNOWLEDGE
```

O `ScientificIdentityValidator` avisa (WARNING, não ERROR) quando a cadeia
não respeita esta ordem — sem bloquear operação.

---

## Consequências

### Positivo
- Rastreabilidade cross-module sem modificar implementações existentes
- `scientific_id` é replayável — pode ser reconstruído a qualquer tempo
- `lineage_id` conecta entidades de diferentes módulos sem acoplamento direto
- `ScientificIdentityChain.chain_hash` fornece fingerprint imutável de toda a cadeia

### Negativo
- Requer que novos produtores adotem o builder para persistir identidades
- Migração gradual — consumidores legados não são forçados a migrar imediatamente

---

## Alternativas consideradas

| Alternativa | Motivo de rejeição |
|---|---|
| Usar `canonical_decision_id` (SIP) como ID universal | Cobre apenas decisões, não observações/conhecimento |
| Banco de dados de identidade centralizado | Viola princípio de determinismo/replay sem estado externo |
| UUID random por entidade | Não determinístico — incompatível com replay |

---

## Implementação

```
data-core/app/scientific_identity/
├── contract.py    — ScientificIdentity, ScientificIdentityChain
├── builder.py     — ScientificIdentityBuilder
├── repository.py  — Protocol + InMemoryScientificIdentityRepository
├── adapter.py     — Adapters for SIP, ExecutionRuntime, BusinessOS
├── validator.py   — ScientificIdentityValidator
└── tests/
    └── test_scientific_identity.py
```

**Testes:** 17/17 passing
**Comportamento operacional alterado:** ZERO
