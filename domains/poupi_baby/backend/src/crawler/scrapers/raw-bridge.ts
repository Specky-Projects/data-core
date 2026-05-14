import { scrapeProduct } from './dispatcher';
import { detectStoreName } from './registry';

async function main() {
  const url = process.argv[2];
  const store = process.argv[3];

  if (!url) {
    console.error(JSON.stringify({ success: false, error: 'missing_url' }));
    process.exit(2);
  }

  try {
    const detectedStore = store ?? detectStoreName(url);
    const product = await scrapeProduct(url, store);
    process.stdout.write(
      JSON.stringify({
        success: product.success,
        source: detectedStore ?? product.store,
        targetUrl: url,
        scrapedProduct: product,
        scrapedAt: new Date().toISOString(),
      }),
    );
  } catch (error) {
    process.stdout.write(
      JSON.stringify({
        success: false,
        targetUrl: url,
        error: error instanceof Error ? error.message : String(error),
        scrapedAt: new Date().toISOString(),
      }),
    );
    process.exit(1);
  }
}

void main();
