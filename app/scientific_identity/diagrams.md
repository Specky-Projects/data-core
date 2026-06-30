# ScientificIdentity — Diagrams
**Phase 2.2**

---

## 1. Lifecycle Flow

```
Producer (SIP / ResearchPlatform / BusinessOS / ExecutionRuntime)
    │
    ▼
ScientificIdentityBuilder
    │  .with_parent(parent_scientific_id)
    │  .build(entity_type, entity_id, produced_at)
    │
    ▼
ScientificIdentity (frozen)
    ├── entity_type: ScientificEntityType
    ├── entity_id: str               ← domain-specific ID
    ├── lineage_id: str              ← shared across all chain entries
    ├── producer: str
    ├── produced_at: str (ISO8601)
    ├── parent_scientific_id: str?   ← set by builder automatically
    ├── schema_version: str
    ├── metadata: dict
    │
    └── scientific_id: str           ← DETERMINISTIC (sha256 of key fields)
        = stable_hash({
              entity_type, entity_id, lineage_id, producer, schema_version
          })
```

---

## 2. Chain Topology

```
lineage_id: "lin-abc"
│
├── OBSERVATION  [scientific_id: a1b2...]  parent: None
│       │
├── CONTEXT      [scientific_id: c3d4...]  parent: a1b2...
│       │
├── EVIDENCE     [scientific_id: e5f6...]  parent: c3d4...
│       │
├── CLAIM        [scientific_id: g7h8...]  parent: e5f6...
│       │
├── DECISION     [scientific_id: i9j0...]  parent: g7h8...
│       │
├── COMMITTEE    [scientific_id: k1l2...]  parent: i9j0...
│       │
├── PREVIEW      [scientific_id: m3n4...]  parent: k1l2...
│       │
├── EXECUTION    [scientific_id: o5p6...]  parent: m3n4...
│       │
├── OUTCOME      [scientific_id: q7r8...]  parent: o5p6...
│       │
├── REPLAY       [scientific_id: s9t0...]  parent: q7r8...
│       │
├── LEARNING     [scientific_id: u1v2...]  parent: s9t0...
│       │
├── EXPERIMENT   [scientific_id: w3x4...]  parent: u1v2...
│       │
└── KNOWLEDGE    [scientific_id: y5z6...]  parent: w3x4...

chain_hash = stable_hash([a1b2, c3d4, e5f6, g7h8, i9j0, ...])
```

---

## 3. Module Structure

```
data-core/app/scientific_identity/
├── __init__.py
├── contract.py
│   ├── ScientificEntityType (StrEnum, 13 types)
│   ├── ScientificIdentity (frozen dataclass)
│   └── ScientificIdentityChain (frozen dataclass)
├── builder.py
│   └── ScientificIdentityBuilder
│       ├── build(entity_type, entity_id, produced_at) → ScientificIdentity
│       ├── build_chain(...) → (ScientificIdentity, ScientificIdentityChain)
│       ├── derive_lineage_id(*parts) → str  [static]
│       └── new_chain(lineage_id) → ScientificIdentityChain  [static]
├── repository.py
│   ├── ScientificIdentityRepositoryProtocol  [Protocol]
│   └── InMemoryScientificIdentityRepository
├── adapter.py
│   ├── from_canonical_decision_record(record) → ScientificIdentity
│   ├── from_execution_outcome(outcome, lineage_id) → ScientificIdentity
│   ├── from_business_os_claim(claim_id, capability_id, lineage_id) → ScientificIdentity
│   └── from_event(...) → ScientificIdentity
├── validator.py
│   ├── ScientificIdentityValidator
│   │   ├── validate_identity(identity) → ValidationResult
│   │   └── validate_chain(chain) → ValidationResult
│   └── ValidationResult
│       ├── valid: bool
│       ├── errors() → list[ValidationFinding]
│       └── warnings() → list[ValidationFinding]
└── tests/
    └── test_scientific_identity.py  [17 tests]
```

---

## 4. Adapter Topology

```
SIP CanonicalDecisionRecord
        │
        └─ from_canonical_decision_record() ──────► ScientificIdentity
                                                           │
ExecutionRuntime ExecutionOutcome                          │
        │                                                  │
        └─ from_execution_outcome() ─────────────────────►│
                                                           │
BusinessOS ScientificClaimDto                              │
        │                                                  │
        └─ from_business_os_claim() ────────────────────► │
                                                           │
Any Event                                                  │
        │                                                  │
        └─ from_event() ────────────────────────────────► │
                                                           ▼
                                               ScientificIdentityRepository
                                               ScientificIdentityChain
```

---

## 5. Validation Rules

```
Identity Level:
  ERROR:   entity_id empty
  ERROR:   lineage_id empty
  ERROR:   producer empty
  ERROR:   produced_at empty
  WARNING: metadata empty (for most entity types)

Chain Level:
  WARNING: chain[0].entity_type != OBSERVATION
  WARNING: entity type order violates canonical sequence
  WARNING: chain has no entries
```
