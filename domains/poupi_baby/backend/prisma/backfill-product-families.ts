import { PrismaClient } from '@prisma/client';
import { canonicalizeProduct } from '../src/products/product-canonicalizer';

const prisma = new PrismaClient();

async function main() {
  const dryRun = process.argv.includes('--dry-run');
  const products = await prisma.product.findMany({
    where: { deletedAt: null },
    select: {
      id: true,
      title: true,
      canonicalName: true,
      productFamilySlug: true,
    },
    orderBy: { createdAt: 'asc' },
  });

  let changed = 0;
  const samples: Array<Record<string, unknown>> = [];

  for (const product of products) {
    const canonical = canonicalizeProduct(product.canonicalName ?? product.title);
    const needsUpdate =
      product.productFamilySlug !== canonical.productFamilySlug ||
      product.canonicalName !== canonical.canonicalName;

    if (!needsUpdate) continue;
    changed++;

    if (samples.length < 20) {
      samples.push({
        id: product.id,
        before: product.canonicalName ?? product.title,
        canonicalName: canonical.canonicalName,
        family: canonical.productFamilyName,
        variant: canonical.variantLabel,
      });
    }

    if (dryRun) continue;

    await prisma.product.update({
      where: { id: product.id },
      data: {
        title: canonical.canonicalName,
        canonicalName: canonical.canonicalName,
        productFamilyName: canonical.productFamilyName,
        productFamilySlug: canonical.productFamilySlug,
        variantLabel: canonical.variantLabel,
        measureValue: canonical.measureValue,
        measureUnit: canonical.measureUnit,
        normalizedTitle: canonical.normalizedTitle,
        brand: canonical.brand,
        category: canonical.category,
        normalizedSize: canonical.normalizedSize,
        quantity: canonical.quantity,
        unitType: canonical.unitType,
        keywords: JSON.stringify(canonical.keywords),
      },
    });
  }

  console.log(JSON.stringify({
    dryRun,
    scanned: products.length,
    changed,
    samples,
  }, null, 2));
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
