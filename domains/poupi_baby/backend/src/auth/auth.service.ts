import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
  UnauthorizedException,
  UnprocessableEntityException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcrypt';
import { PrismaService } from '../prisma/prisma.service';
import { SignupDto } from './dto/signup.dto';
import { LoginDto } from './dto/login.dto';
import { GoogleAuthDto } from './dto/google-auth.dto';

function isMissingColumnError(error: unknown): boolean {
  return typeof error === 'object' && error !== null && (error as { code?: string }).code === 'P2022';
}

@Injectable()
export class AuthService {

  constructor(
    private prisma: PrismaService,

    private jwtService: JwtService,
  ) {}

  async signup(data: SignupDto) {

    const existingUser =
      await this.prisma.user.findUnique({
        where: {
          email: data.email,
        },
      });

    if (existingUser) {
      throw new ConflictException(
        'Email already exists',
      );
    }

    const passwordHash =
      await bcrypt.hash(
        data.password,
        10,
      );

    const user =
      await this.prisma.user.create({
        data: {
          name: data.name,

          email: data.email,

          passwordHash,
        },
      });

    const token = await this.jwtService.signAsync({
      sub:   user.id,
      email: user.email,
      role:  user.role,
    });

    return {
      token,
      user: { id: user.id, name: user.name, email: user.email, role: user.role },
    };
  }

  /**
   * Sync interno servidor-a-servidor (Next.js → NestJS).
   * Encontra ou cria usuário pelo email OAuth verificado.
   * Requer header X-Internal-Secret para evitar uso externo.
   */
  async syncOAuthUser(email: string, name: string) {
    let user = await this.prisma.user.findUnique({ where: { email } });

    if (!user) {
      const passwordHash = await bcrypt.hash(crypto.randomUUID(), 10);
      user = await this.prisma.user.create({
        data: { name: name || email.split('@')[0], email, passwordHash },
      });
    }

    const token = await this.jwtService.signAsync({ sub: user.id, email: user.email, role: user.role });
    return { token, user: { id: user.id, name: user.name, email: user.email, role: user.role } };
  }

  async googleAuth(data: GoogleAuthDto) {
    // Valida o id_token com a API do Google
    const googleRes = await fetch(
      `https://oauth2.googleapis.com/tokeninfo?id_token=${data.idToken}`,
    );

    if (!googleRes.ok) {
      throw new UnprocessableEntityException('Token Google inválido');
    }

    const payload = await googleRes.json();

    if (!payload.email_verified) {
      throw new UnprocessableEntityException('Email Google não verificado');
    }

    const email: string = payload.email;
    const name: string = payload.name || email.split('@')[0];

    // Upsert: cria usuário se não existir
    let user = await this.prisma.user.findUnique({ where: { email } });

    if (!user) {
      // Senha aleatória — usuário Google não faz login por senha
      const passwordHash = await bcrypt.hash(crypto.randomUUID(), 10);

      user = await this.prisma.user.create({
        data: { name, email, passwordHash },
      });
    }

    const token = await this.jwtService.signAsync({ sub: user.id, email: user.email, role: user.role });
    return { token, user: { id: user.id, name: user.name, email: user.email, role: user.role } };
  }

  async login(data: LoginDto) {

  const user =
    await this.prisma.user.findUnique({
      where: {
        email: data.email,
      },
    });

  if (!user) {
    throw new UnauthorizedException(
      'Invalid credentials',
    );
  }

  const passwordMatch =
    await bcrypt.compare(
      data.password,
      user.passwordHash,
    );

  if (!passwordMatch) {
    throw new UnauthorizedException(
      'Invalid credentials',
    );
  }

  const token = await this.jwtService.signAsync({ sub: user.id, email: user.email, role: user.role });
  return { token, user: { id: user.id, name: user.name, email: user.email, role: user.role } };
}

  async getProfile(userId: string) {
    try {
      const user = await this.prisma.user.findUnique({
        where: { id: userId },
        select: {
          id: true,
          name: true,
          email: true,
          phone: true,
          role: true,
          emailVerifiedAt: true,
          createdAt: true,
        },
      });
      if (!user) throw new NotFoundException('Usuário não encontrado');
      return {
        ...user,
        emailVerified: Boolean(user.emailVerifiedAt),
      };
    } catch (error) {
      if (!isMissingColumnError(error)) throw error;
      const user = await this.prisma.user.findUnique({
        where: { id: userId },
        select: {
          id: true,
          name: true,
          email: true,
          role: true,
          createdAt: true,
        },
      });
      if (!user) throw new NotFoundException('Usuário não encontrado');
      return { ...user, phone: null, emailVerifiedAt: null, emailVerified: false };
    }
  }

  async updateProfile(userId: string, data: { name?: string; email?: string; phone?: string | null }) {
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new NotFoundException('Usuário não encontrado');

    const nextName = typeof data.name === 'string' ? data.name.trim() : undefined;
    const nextEmail = typeof data.email === 'string' ? data.email.trim().toLowerCase() : undefined;
    const nextPhone = typeof data.phone === 'string' ? data.phone.trim() : data.phone;

    if (nextName !== undefined && nextName.length < 1) {
      throw new BadRequestException('Informe um nome válido');
    }
    if (nextName && nextName.length > 150) {
      throw new BadRequestException('O nome deve ter até 150 caracteres');
    }
    if (nextEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(nextEmail)) {
      throw new BadRequestException('Informe um e-mail válido');
    }
    if (nextEmail && nextEmail !== user.email) {
      const existing = await this.prisma.user.findUnique({ where: { email: nextEmail } });
      if (existing) throw new ConflictException('Este e-mail já está em uso');
    }

    const emailChanged = Boolean(nextEmail && nextEmail !== user.email);
    try {
      const updated = await this.prisma.user.update({
        where: { id: userId },
        data: {
          ...(nextName !== undefined ? { name: nextName } : {}),
          ...(nextEmail !== undefined ? { email: nextEmail } : {}),
          ...(nextPhone !== undefined ? { phone: nextPhone || null } : {}),
          ...(emailChanged
            ? {
                emailVerifiedAt: null,
                emailVerificationCode: null,
                emailVerificationExpiresAt: null,
              }
            : {}),
        },
        select: {
          id: true,
          name: true,
          email: true,
          phone: true,
          role: true,
          emailVerifiedAt: true,
          createdAt: true,
        },
      });

      return { ...updated, emailVerified: Boolean(updated.emailVerifiedAt) };
    } catch (error) {
      if (!isMissingColumnError(error)) throw error;
      const updated = await this.prisma.user.update({
        where: { id: userId },
        data: {
          ...(nextName !== undefined ? { name: nextName } : {}),
          ...(nextEmail !== undefined ? { email: nextEmail } : {}),
        },
        select: {
          id: true,
          name: true,
          email: true,
          role: true,
          createdAt: true,
        },
      });
      return { ...updated, phone: null, emailVerifiedAt: null, emailVerified: false };
    }
  }

  async updatePassword(userId: string, currentPassword: string, newPassword: string) {
    if (!newPassword || newPassword.length < 6) {
      throw new BadRequestException('A nova senha deve ter pelo menos 6 caracteres');
    }
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new NotFoundException('Usuário não encontrado');

    const passwordMatch = await bcrypt.compare(currentPassword ?? '', user.passwordHash);
    if (!passwordMatch) throw new UnauthorizedException('Senha atual incorreta');

    const passwordHash = await bcrypt.hash(newPassword, 10);
    await this.prisma.user.update({ where: { id: userId }, data: { passwordHash } });
    return { ok: true };
  }

  async requestEmailConfirmation(userId: string) {
    const code = String(Math.floor(100000 + Math.random() * 900000));
    const expiresAt = new Date(Date.now() + 30 * 60_000);

    await this.prisma.user.update({
      where: { id: userId },
      data: {
        emailVerificationCode: code,
        emailVerificationExpiresAt: expiresAt,
      },
    });

    return {
      ok: true,
      message: 'Código de confirmação gerado.',
      expiresAt,
      devCode: process.env.NODE_ENV === 'production' ? undefined : code,
    };
  }

  async confirmEmail(userId: string, code: string) {
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new NotFoundException('Usuário não encontrado');
    if (!user.emailVerificationCode || !user.emailVerificationExpiresAt) {
      throw new BadRequestException('Solicite um novo código de confirmação');
    }
    if (user.emailVerificationExpiresAt < new Date()) {
      throw new BadRequestException('Código expirado. Solicite um novo código');
    }
    if (user.emailVerificationCode !== String(code ?? '').trim()) {
      throw new BadRequestException('Código inválido');
    }

    await this.prisma.user.update({
      where: { id: userId },
      data: {
        emailVerifiedAt: new Date(),
        emailVerificationCode: null,
        emailVerificationExpiresAt: null,
      },
    });
    return { ok: true };
  }

}
