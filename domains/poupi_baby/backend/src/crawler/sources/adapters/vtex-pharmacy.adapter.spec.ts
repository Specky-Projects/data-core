import { VtexPharmacyAdapter } from './vtex-pharmacy.adapter';
import { ScrapeContext } from '../source-adapter.interface';

class TestVtexAdapter extends VtexPharmacyAdapter {
  constructor() {
    super('drogasil', ['drogasil.com.br']);
  }

  parseFixture(html: string) {
    return this.parseHtml(
      { html, finalUrl: 'https://www.drogasil.com.br/produto.html', statusCode: 200 },
      {
        url: 'https://www.drogasil.com.br/produto.html',
        marketplace: 'drogasil',
        attempt: 1,
        priority: 'manual',
      } satisfies ScrapeContext,
    );
  }
}

describe('VtexPharmacyAdapter parser', () => {
  const adapter = new TestVtexAdapter();

  it('extracts product data from JSON-LD fixture', () => {
    const result = adapter.parseFixture(`
      <html>
        <body>
          <h1>Formula Infantil Teste 800g</h1>
          <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "Product",
              "name": "Formula Infantil Teste 800g",
              "image": "https://img.test/produto.jpg",
              "offers": {
                "@type": "Offer",
                "price": "89.90",
                "priceCurrency": "BRL",
                "availability": "https://schema.org/InStock"
              }
            }
          </script>
        </body>
      </html>
    `);

    expect(result.success).toBe(true);
    expect(result.price).toBe(89.9);
    expect(result.name).toBe('Formula Infantil Teste 800g');
    expect(result.availability).toBe(true);
  });

  it('classifies parser failure when price is missing', () => {
    const result = adapter.parseFixture(`
      <html>
        <body>
          <h1>Produto sem preco</h1>
          <p>Descricao longa de produto infantil usada como fixture estavel para validar parser sem depender do site ao vivo.</p>
          <p>Conteudo suficiente para nao ser tratado como resposta vazia ou bloqueada.</p>
          <p>Marca teste, embalagem 800g, categoria formulas infantis.</p>
        </body>
      </html>
    `);

    expect(result.success).toBe(false);
    expect(result.errorType).toBe('PARSER_FAILED');
    expect(result.htmlSnapshot).toContain('Produto sem preco');
  });
});
