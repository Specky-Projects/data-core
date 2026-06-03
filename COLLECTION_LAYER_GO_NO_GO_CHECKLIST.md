# Collection Layer Go No-Go Checklist

Data: 2026-05-31

## Infra

| Item | Status | Evidencia |
|---|---|---|
| servidor acessivel | DEGRADED | TCP/22 ok, mas SSH banner timeout apos replay |
| containers principais up | PASS inicial | `docker ps` mostrou API/scheduler/worker healthy |
| restart policies corretas | PASS | `unless-stopped` em api/scheduler/worker |
| portas publicas justificadas | PASS parcial | 80/443 via Traefik, Coolify local, Alertmanager local |
| secrets nao expostos | PASS | envs apenas auditados por presenca/redacao |

## Banco

| Item | Status | Evidencia |
|---|---|---|
| migrations aplicadas | PARTIAL | `alembic_version=0020`; enum `jobs` aplicado manualmente |
| tabelas necessarias existem | PASS | `collection_runs`, `raw_collections`, `collector_errors`, `collector_definitions` |
| dados persistem apos restart | NOT VALIDATED | sem restart/restore nesta missao |
| backup minimo validado | NOT VALIDATED | script existe, restore nao testado |

## Coleta

| Item | Status | Evidencia |
|---|---|---|
| collectors registrados | PARTIAL | hot patch registra Real Estate/Jobs, imagem original nao |
| scheduler ativo | PASS parcial | container healthy, logs rodando jobs |
| runs recentes | PASS para crypto | crypto gera runs recentes |
| raw_saved_count > 0 | PASS para crypto, FAIL para Real Estate/Jobs | Real Estate direct/JOBS sem raw persistido |
| error_count monitorado | PARTIAL | collector_errors existe, mas readiness degradado |
| logs consultaveis | PASS inicial | logs scheduler/worker acessados |

## Real Estate

| Item | Status | Evidencia |
|---|---|---|
| run real validado | FAIL | direct_agencies falhou/timeouts |
| fontes uteis ativas | PARTIAL | config core_sources aplicada, sem sucesso persistido |
| raw persistido | FAIL | `direct_agencies=0` no servidor |
| freshness READY | FAIL | Apolar legado latest 2026-05-27 |

## Jobs

| Item | Status | Evidencia |
|---|---|---|
| collector foundation validado | PARTIAL | codigo copiado/hot patch, enum jobs aplicado |
| pelo menos uma fonte real coletando | FAIL | sem run jobs concluido |
| raw persistido | FAIL | `module=jobs` vazio |
| logs e runs disponiveis | FAIL | sem collection_runs jobs.* |

## Local

| Item | Status | Evidencia |
|---|---|---|
| notebook nao e dependencia operacional | FAIL | hot patch/scp partiu do notebook |
| local apenas desenvolvimento | FAIL | servidor nao tinha codigo atual |

## Veredito

**NO-GO — SERVER DEPENDENCY OR COLLECTION FAILURE**

Motivos:

- Real Estate prioritario nao coletou de ponta a ponta no servidor.
- Jobs nao possui evidencia de raw persistence no servidor.
- Redis do data-core esta degradado.
- Imagem server-side esta stale em relacao ao codigo local.
- Servidor degradou durante replay longo.

Proxima acao de maior ROI tecnico:

```text
Criar deploy duravel do data-core atualizado no Coolify com perfil server-first de coletores limitado por fonte, Redis interno/sem quota para data-core e smoke command curto para Real Estate e Jobs antes de reativar scheduler amplo.
```

