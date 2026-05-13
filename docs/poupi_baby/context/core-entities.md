# Core Entities

Entidades principais do sistema Poupi. Cada entidade representa um objeto central do produto — a base lógica sobre a qual toda a lógica de negócio é construída.

Legenda de campos:
- ✅ MVP — deve existir desde o início
- 🟡 Futuro — documentado, implementar depois

---

## User

Representa o usuário cadastrado na plataforma. Pode ser gratuito ou premium, e está associado a alertas e assinaturas.

### Responsibilities

- autenticar e identificar usuários na plataforma
- controlar acesso a features por plano (`role`)
- ser o ponto central de associação com alertas e assinaturas
- suportar auditoria e histórico via soft delete

### Fields

| Campo | Tipo | Status | Descrição |
|---|---|---|---|
| `id` | `uuid` | ✅ MVP | Identificador único (PK) |
| `name` | `varchar(150)` | ✅ MVP | Nome completo |
| `email` | `varchar(255)` | ✅ MVP | Email único para login |
| `password_hash` | `varchar(255)` | ✅ MVP | Senha criptografada (bcrypt) |
| `role` | `enum` | ✅ MVP | `free` · `premium` · `admin` |
| `created_at` | `timestamptz` | ✅ MVP | Data de cadastro |
| `deleted_at` | `timestamptz` | ✅ MVP | Soft delete — `null` = ativo |

### Rules

- `email` deve ser único no sistema
- `password_hash` nunca é retornado nas respostas da API
- `role` determina quais features o usuário pode acessar
- registros com `deleted_at != null` são tratados como inativos em todas as queries

---

## Product

Produto normalizado e unificado entre marketplaces. Não representa uma oferta específica — é o produto canônico que agrupa todas as ofertas de diferentes lojas.

### Responsibilities

- agregar ofertas de múltiplos marketplaces em um único produto canônico
- centralizar a normalização e deduplicação de títulos
- servir como âncora para alertas de preço
- suportar busca, autocomplete e recomendações por IA
- suportar análise histórica de preços

### Fields

| Campo | Tipo | Status | Descrição |
|---|---|---|---|
| `id` | `uuid` | ✅ MVP | Identificador único (PK) |
| `title` | `varchar(500)` | ✅ MVP | Título original do produto |
| `normalized_title` | `varchar(500)` | ✅ MVP | Título normalizado para matching e deduplicação |
| `slug` | `varchar(500)` | ✅ MVP | URL amigável (único) |
| `brand` | `varchar(150)` | ✅ MVP | Marca do produto |
| `category` | `varchar(150)` | ✅ MVP | Categoria principal |
| `image_url` | `text` | ✅ MVP | Imagem principal |
| `created_at` | `timestamptz` | ✅ MVP | Data de cadastro |
| `deleted_at` | `timestamptz` | ✅ MVP | Soft delete — `null` = ativo |
| `search_keywords` | `text[]` | 🟡 Futuro | Keywords para busca e IA (ex: `["iphone", "apple", "ios"]`) |
| `search_vector` | `tsvector` | 🟡 Futuro | Índice de full-text search nativo do PostgreSQL |

### Rules

- `slug` deve ser único e gerado automaticamente a partir do `title`
- `normalized_title` é gerado automaticamente: lowercase, sem acentos, sem stopwords, sem emojis
- a combinação `normalized_title + brand` é o principal critério de deduplicação
- `search_keywords` pode ser gerado automaticamente por IA futuramente
- `search_vector` deve ser atualizado via trigger ao salvar `title` e `search_keywords`

### normalized_title — como funciona

```
title:            "Apple iPhone 15 Azul 128 GB 🔥 Promoção!"
normalized_title: "iphone 15 128gb azul"
```

Transformações aplicadas: lowercase → remove emojis → remove stopwords → normaliza acentos → colapsa espaços.

---

## Marketplace

Representa um marketplace integrado ao Poupi, como Mercado Livre, Amazon ou Magazine Luiza.

### Responsibilities

- registrar e configurar cada marketplace integrado
- fornecer metadados para o crawler (URL base, estratégia)
- controlar quais marketplaces estão ativos no ciclo de crawling

### Fields

| Campo | Tipo | Status | Descrição |
|---|---|---|---|
| `id` | `uuid` | ✅ MVP | Identificador único (PK) |
| `name` | `varchar(150)` | ✅ MVP | Nome do marketplace |
| `base_url` | `varchar(255)` | ✅ MVP | URL base para crawling |
| `logo_url` | `text` | ✅ MVP | Logo para exibição |
| `active` | `boolean` | ✅ MVP | Se está ativo no sistema |
| `crawl_strategy` | `enum` | 🟡 Futuro | `api` · `scraping` · `browser` |

### Rules

- apenas marketplaces com `active = true` são incluídos no crawling
- `crawl_strategy` determinará qual worker/adapter será utilizado pelo crawler
- `base_url` é utilizado como ponto de partida do crawler

---

## Offer

Oferta específica de um produto em um marketplace. Contém preço atual, frete, disponibilidade e URL de compra. É a entidade mais atualizada do sistema — modificada a cada ciclo de crawling.

### Responsibilities

- registrar o estado atual de um produto em um marketplace
- distinguir entre "preço mudou" (`updated_at`) e "crawler verificou" (`last_checked_at`)
- servir de base para o histórico de preços
- identificar unicamente ofertas pelo ID externo do marketplace (`external_id`)
- disparar eventos de atualização de preço para o sistema de alertas

### Fields

| Campo | Tipo | Status | Descrição |
|---|---|---|---|
| `id` | `uuid` | ✅ MVP | Identificador único (PK) |
| `product_id` | `uuid` | ✅ MVP | Referência ao produto (FK) |
| `marketplace_id` | `uuid` | ✅ MVP | Referência ao marketplace (FK) |
| `external_id` | `varchar(255)` | ✅ MVP | ID da oferta no marketplace (ASIN, SKU, item_id) |
| `price` | `decimal(10,2)` | ✅ MVP | Preço atual |
| `freight_price` | `decimal(10,2)` | ✅ MVP | Valor do frete (`0` = frete grátis) |
| `product_url` | `text` | ✅ MVP | Link direto da oferta |
| `availability` | `boolean` | ✅ MVP | Se está disponível para compra |
| `updated_at` | `timestamptz` | ✅ MVP | Última vez que o preço mudou |
| `last_checked_at` | `timestamptz` | ✅ MVP | Última verificação pelo crawler |
| `deleted_at` | `timestamptz` | ✅ MVP | Soft delete — `null` = ativo |

### Rules

- `(marketplace_id, external_id)` deve ser único — é a chave de deduplicação real
- toda mudança de `price` gera um novo registro em `PriceHistory`
- `last_checked_at` é atualizado em todo ciclo de crawling, independente de mudança de preço
- `updated_at` é atualizado apenas quando `price` ou `availability` muda
- `freight_price = 0` representa frete grátis — nunca `null`
- ofertas com `last_checked_at` muito antigo podem indicar falha no crawler

### updated_at vs last_checked_at

```
Crawler verifica oferta → preço igual ao anterior:
  last_checked_at ✅ atualiza
  updated_at      ✗ não muda

Crawler verifica oferta → preço mudou:
  last_checked_at ✅ atualiza
  updated_at      ✅ atualiza
  PriceHistory    ✅ novo registro inserido
```

---

## PriceHistory

Registro append-only de cada variação de preço de uma oferta. Permite gráficos de evolução, cálculo de menor preço histórico e detecção de tendências.

### Responsibilities

- preservar o histórico completo e imutável de preços por oferta
- servir de base para gráficos de evolução de preço
- permitir cálculo de menor preço histórico, média e tendência
- alimentar o motor de recomendações e IA

### Fields

| Campo | Tipo | Status | Descrição |
|---|---|---|---|
| `id` | `uuid` | ✅ MVP | Identificador único (PK) |
| `offer_id` | `uuid` | ✅ MVP | Referência à oferta (FK) |
| `price` | `decimal(10,2)` | ✅ MVP | Preço no momento da captura |
| `captured_at` | `timestamptz` | ✅ MVP | Momento exato da captura |

### Rules

- registros são **somente inserção** — nunca atualizados ou deletados
- um novo registro é criado apenas quando o preço muda em relação ao anterior
- índice em `(offer_id, captured_at DESC)` para consultas de histórico ordenado

---

## Alert

Regra de monitoramento criada pelo usuário. Quando o preço de qualquer oferta de um produto atinge o valor-alvo, o sistema dispara uma notificação.

### Responsibilities

- registrar a intenção do usuário de ser notificado sobre um preço
- ser consultado pelo sistema a cada atualização de preço
- controlar o estado do alerta (ativo / inativo)
- suportar múltiplos canais de notificação futuramente

### Fields

| Campo | Tipo | Status | Descrição |
|---|---|---|---|
| `id` | `uuid` | ✅ MVP | Identificador único (PK) |
| `user_id` | `uuid` | ✅ MVP | Referência ao usuário (FK) |
| `product_id` | `uuid` | ✅ MVP | Produto monitorado (FK) |
| `target_price` | `decimal(10,2)` | ✅ MVP | Preço desejado para disparo |
| `active` | `boolean` | ✅ MVP | Se o alerta está ativo |
| `created_at` | `timestamptz` | ✅ MVP | Data de criação |
| `notification_channel` | `enum` | 🟡 Futuro | `email` · `push` · `telegram` · `discord` |

### Rules

- alerta aponta para `Product` (não `Offer`) — monitora independente do marketplace
- usuários `free` têm limite de alertas ativos (regra de negócio, não constraint no banco)
- MVP notifica apenas por email — `notification_channel` será adicionado futuramente
- após disparo, o alerta pode ser desativado ou mantido ativo (configurável por produto)
- índice em `(product_id, active)` para validação eficiente durante crawling

---

## Subscription

Controla o plano do usuário e a integração com o gateway de pagamento. Determina quais features estão disponíveis — histórico avançado, mais alertas e recomendações por IA.

### Responsibilities

- controlar o plano ativo do usuário e suas permissões
- integrar com gateways de pagamento via `provider` e `provider_subscription_id`
- receber e processar webhooks de pagamento
- registrar histórico de assinaturas ao longo do tempo
- ser desacoplada de `User` para facilitar mudança de plano e auditoria

### Fields

| Campo | Tipo | Status | Descrição |
|---|---|---|---|
| `id` | `uuid` | ✅ MVP | Identificador único (PK) |
| `user_id` | `uuid` | ✅ MVP | Referência ao usuário (FK) |
| `plan` | `enum` | ✅ MVP | `free` · `pro` · `enterprise` |
| `status` | `enum` | ✅ MVP | `active` · `canceled` · `expired` |
| `provider` | `varchar(50)` | ✅ MVP | Gateway usado: `stripe` · `mercadopago` · `asaas` |
| `provider_subscription_id` | `varchar(255)` | ✅ MVP | ID da assinatura no gateway (para webhooks) |
| `expires_at` | `timestamptz` | ✅ MVP | Data de expiração do plano |
| `created_at` | `timestamptz` | ✅ MVP | Data de início da assinatura |

### Rules

- um usuário pode ter apenas uma assinatura com `status = active` por vez
- `provider_subscription_id` é obrigatório quando `provider != null`
- webhooks do gateway atualizam `status` e `expires_at` via endpoint dedicado
- `Subscription` é separada de `User` para preservar histórico de planos

---

## Relacionamentos

```
User         ──< Alert        (um usuário tem vários alertas)
User         ──< Subscription (um usuário tem várias assinaturas ao longo do tempo)
Product      ──< Offer        (um produto tem ofertas em vários marketplaces)
Product      ──< Alert        (um produto pode ser monitorado por vários alertas)
Marketplace  ──< Offer        (um marketplace tem várias ofertas)
Offer        ──< PriceHistory (uma oferta tem histórico de preços — append-only)
```

---

## Campos futuros consolidados

| Campo | Entidade | Motivo |
|---|---|---|
| `search_keywords` | Product | Autocomplete, busca semântica, IA |
| `search_vector` | Product | Full-text search nativo PostgreSQL |
| `crawl_strategy` | Marketplace | Arquitetura de workers: api · scraping · browser |
| `notification_channel` | Alert | Multi-canal: email · push · telegram · discord |