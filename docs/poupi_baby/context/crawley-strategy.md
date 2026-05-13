# Crawler Strategy

## Objetivo

Coletar precos, disponibilidade e metadados basicos de ofertas infantis em um conjunto pequeno e curado de URLs.

O crawler do Poupi Baby deve ser deterministico: cada job recebe uma oferta conhecida, acessa a URL configurada, aplica uma estrategia de extracao previsivel e grava o resultado com rastreabilidade.

## Principios

- Monitorar 100 a 300 SKUs curados no inicio
- Nao varrer catalogo inteiro
- Nao fazer discovery automatico de produtos no MVP
- Usar scraping por URL de produto
- Preferir JSON-LD, dados estruturados e seletores estaveis
- Registrar falhas por loja para pausar scrapers ruins
- Preservar historico append-only quando houver mudanca de preco

## Lojas iniciais

- Drogasil
- Droga Raia
- Amazon Brasil
- Pague Menos

## Fluxo

1. Scheduler seleciona ofertas vencidas pelo intervalo de monitoramento
2. BullMQ enfileira jobs por oferta
3. Worker executa o scraper da loja detectada
4. Resultado e normalizado para `ScrapedProduct`
5. Oferta atual e atualizada
6. `PriceHistory` e criado se o preco mudou
7. Eventos de dominio disparam alertas e calculos deterministas

## Frequencia

O intervalo inicial deve considerar:

- ofertas com alertas ativos
- saude recente do scraper
- criticidade da categoria
- estabilidade historica do preco

O MVP pode comecar com intervalos conservadores para reduzir bloqueio e preservar confiabilidade.

## Deteccao de promocao real

Sem IA inicialmente.

As primeiras regras devem usar:

- menor preco historico
- media dos ultimos dias
- percentual de queda frente ao preco recente
- recorrencia de promocao
- disponibilidade atual

## Anti-bloqueio

Os crawlers devem:

- respeitar rate limit por dominio
- evitar chamadas agressivas
- usar retries com backoff
- registrar CAPTCHA, 403, 429 e timeouts
- permitir desativacao temporaria por marketplace

## Evolucao futura

- browser automation pontual para lojas que exigirem renderizacao
- pipelines separados por vertical
- normalizacao mais sofisticada de SKUs
- modelos de IA para classificacao e insights, apenas depois de historico confiavel
