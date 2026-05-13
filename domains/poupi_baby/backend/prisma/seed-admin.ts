/**
 * prisma/seed-admin.ts
 *
 * Concede ou revoga role de admin para um email.
 *
 * Uso:
 *   npm run seed:admin -- grant admin.poupi@gmail.com
 *   npm run seed:admin -- revoke admin.poupi@gmail.com
 *   npm run seed:admin -- list
 */

import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';

const prisma = new PrismaClient();

async function main() {
  const [action, email] = process.argv.slice(2);

  if (action === 'list') {
    const admins = await prisma.user.findMany({
      where:  { role: 'admin' },
      select: { email: true, name: true, createdAt: true },
    });
    console.log(`\n👑 Administradores (${admins.length}):\n`);
    admins.forEach((a) => console.log(`  ${a.email} — ${a.name}`));
    return;
  }

  if (!email || !['grant', 'revoke'].includes(action)) {
    console.error('Uso: npm run seed:admin -- grant|revoke|list [email]');
    process.exit(1);
  }

  if (action === 'grant') {
    const existing = await prisma.user.findUnique({ where: { email } });

    if (existing) {
      await prisma.user.update({
        where: { email },
        data:  { role: 'admin' },
      });
      console.log(`✅ ${email} → role=admin`);
    } else {
      // Cria o usuário admin (acesso normal via Google OAuth)
      const passwordHash = await bcrypt.hash(crypto.randomUUID(), 12);
      await prisma.user.create({
        data: { name: email.split('@')[0], email, passwordHash, role: 'admin' },
      });
      console.log(`✅ Usuário admin criado: ${email}`);
    }
  }

  if (action === 'revoke') {
    const existing = await prisma.user.findUnique({ where: { email } });
    if (!existing) {
      console.error(`Usuário não encontrado: ${email}`);
      process.exit(1);
    }
    await prisma.user.update({
      where: { email },
      data:  { role: 'free' },
    });
    console.log(`⬇️  ${email} → role=free`);
  }
}

main()
  .catch((e) => { console.error(e); process.exit(1); })
  .finally(() => prisma.$disconnect());
