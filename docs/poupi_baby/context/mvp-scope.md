# MVP Scope

## Funcionalidades do MVP

- Base curada com 100 a 300 SKUs
- Produtos das categorias formulas, fraldas e lencos
- Ofertas nas lojas Drogasil, Droga Raia, Amazon Brasil e Pague Menos
- Scraping deterministico por URL de produto
- Historico de precos por oferta
- Alertas por preco-alvo
- Deteccao inicial de promocao real por regras deterministicas
- Dashboard operacional de crawler, filas e saude dos scrapers
- Backend unico multi-vertical, iniciando pela vertical baby

## Regras de escopo

- Monitorar somente produtos previamente curados
- Nao descobrir nem importar catalogo inteiro das lojas
- Priorizar confiabilidade do historico em vez de cobertura ampla
- Manter normalizacao simples e auditavel no inicio
- Evitar IA na primeira fase

## Fora do MVP

- IA generativa ou recomendacao por modelo
- App mobile
- Extensao de navegador
- Marketplace proprio
- Checkout interno
- API publica
- Descoberta automatica de catalogo
- Scraping com browser automation como dependencia principal
- Multi-tenant enterprise
