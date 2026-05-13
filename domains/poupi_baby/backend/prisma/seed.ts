/**
 * prisma/seed.ts
 *
 * Seed inicial do banco de dados.
 * Execução: npx prisma db seed
 *
 * O que faz:
 *   1. Cria (ou atualiza) o usuário admin.poupi@gmail.com com role=admin
 *   2. Cria os marketplaces padrão se não existirem
 */

import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';

const prisma = new PrismaClient();

// ── Admins ────────────────────────────────────────────────────────────────────

const ADMIN_USERS = [
  { email: 'admin.poupi@gmail.com', name: 'Admin Poupi' },
];

// ── Marketplaces padrão ───────────────────────────────────────────────────────

const DEFAULT_MARKETPLACES = [
  { name: 'Amazon Brasil', baseUrl: 'https://www.amazon.com.br' },
  { name: 'Drogasil',      baseUrl: 'https://www.drogasil.com.br' },
  { name: 'Droga Raia',    baseUrl: 'https://www.drogaraia.com.br' },
  { name: 'Pague Menos',   baseUrl: 'https://www.paguemenos.com.br' },
];

// ─────────────────────────────────────────────────────────────────────────────

async function main() {
  console.log('🌱 Iniciando seed...\n');

  // 1. Upsert admin users
  for (const admin of ADMIN_USERS) {
    const existing = await prisma.user.findUnique({ where: { email: admin.email } });

    if (existing) {
      await prisma.user.update({
        where: { email: admin.email },
        data:  { role: 'admin' },
      });
      console.log(`✅ Admin atualizado: ${admin.email} → role=admin`);
    } else {
      // Cria com senha aleatória — acesso via Google OAuth
      const passwordHash = await bcrypt.hash(crypto.randomUUID(), 12);
      await prisma.user.create({
        data: {
          name:         admin.name,
          email:        admin.email,
          passwordHash,
          role:         'admin',
        },
      });
      console.log(`✅ Admin criado: ${admin.email}`);
    }
  }

  console.log('');

  // 2. Upsert marketplaces padrão
  for (const mp of DEFAULT_MARKETPLACES) {
    const existing = await prisma.marketplace.findFirst({ where: { name: mp.name } });

    if (!existing) {
      await prisma.marketplace.create({ data: mp });
      console.log(`✅ Marketplace criado: ${mp.name}`);
    } else {
      console.log(`⏭  Marketplace já existe: ${mp.name}`);
    }
  }

  console.log('\n✨ Seed concluído.');
}

main()
  .catch((e) => {
    console.error('❌ Erro no seed:', e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
