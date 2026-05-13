import { Injectable, Logger } from '@nestjs/common';
import * as nodemailer from 'nodemailer';

export interface PriceAlertPayload {
  email: string;
  userName: string;
  productTitle: string;
  productUrl: string;
  productImageUrl?: string | null;
  currentPrice: number;
  previousPrice: number;
  targetPrice: number;
  marketplace: string;
}

export interface SmartAlertPayload {
  email: string;
  userName: string;
  productTitle: string;
  productUrl: string;
  productImageUrl?: string | null;
  currentPrice: number;
  previousPrice: number | null;
  marketplace: string;
  type: 'NEW_LOWEST_PRICE' | 'PRICE_DROP' | 'RESTOCKED';
  reason: string;
}

@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  private transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
      user: process.env.GMAIL_USER,
      pass: process.env.GMAIL_APP_PASSWORD,
    },
  });

  // ── Alerta de queda de preço ──────────────────────────────────────────────

  async sendPriceAlert(payload: PriceAlertPayload): Promise<void> {
    const {
      email, userName, productTitle, productUrl, productImageUrl,
      currentPrice, previousPrice, targetPrice, marketplace,
    } = payload;

    const drop = previousPrice - currentPrice;
    const dropPct = Math.round((drop / previousPrice) * 100);
    const fmt = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const dashboardUrl = process.env.FRONTEND_URL ?? 'http://localhost:3000';

    const html = `
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:system-ui,-apple-system,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;margin:32px auto;">
    <tr><td style="background:#13172a;border:1px solid #1e2540;border-radius:12px;padding:32px;">

      <!-- Logo -->
      <div style="margin-bottom:24px;">
        <span style="font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.5px;">
          <span style="color:#6C2BD9">P</span>oupi
        </span>
      </div>

      <!-- Badge -->
      <div style="background:#0f2d1a;border:1px solid #22C55E;border-radius:8px;padding:8px 14px;display:inline-block;margin-bottom:20px;">
        <span style="color:#22C55E;font-size:13px;font-weight:600;">🔥 Preço atingiu sua meta!</span>
      </div>

      <!-- Title -->
      <h1 style="color:#e2e8f0;font-size:17px;font-weight:600;margin:0 0 6px 0;line-height:1.4;">
        ${productTitle.slice(0, 80)}${productTitle.length > 80 ? '…' : ''}
      </h1>
      <p style="color:#64748b;font-size:13px;margin:0 0 24px 0;">${marketplace}</p>

      <!-- Image -->
      ${productImageUrl ? `
      <div style="text-align:center;margin-bottom:20px;">
        <img src="${productImageUrl}" alt="produto" style="max-height:120px;max-width:200px;border-radius:8px;object-fit:contain;">
      </div>` : ''}

      <!-- Price block -->
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#0c1020;border-radius:10px;padding:20px;margin-bottom:24px;">
        <tr>
          <td style="text-align:center;border-right:1px solid #1e2540;padding-right:20px;">
            <div style="color:#64748b;font-size:11px;margin-bottom:4px;">Preço anterior</div>
            <div style="color:#94a3b8;font-size:18px;text-decoration:line-through;">${fmt(previousPrice)}</div>
          </td>
          <td style="text-align:center;padding-left:20px;">
            <div style="color:#64748b;font-size:11px;margin-bottom:4px;">Preço atual</div>
            <div style="color:#22C55E;font-size:26px;font-weight:700;">${fmt(currentPrice)}</div>
          </td>
        </tr>
        <tr><td colspan="2" style="padding-top:12px;text-align:center;">
          <span style="background:#2d0f0f;color:#f87171;font-size:12px;border-radius:4px;padding:3px 10px;">
            −${fmt(drop)} (${dropPct}% de desconto)
          </span>
          &nbsp;
          <span style="background:#0f2d1a;color:#22C55E;font-size:12px;border-radius:4px;padding:3px 10px;">
            Meta: ${fmt(targetPrice)}
          </span>
        </td></tr>
      </table>

      <!-- CTA -->
      <div style="text-align:center;margin-bottom:28px;">
        <a href="${productUrl}" style="background:#6C2BD9;color:#fff;text-decoration:none;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;display:inline-block;">
          Ver produto →
        </a>
        &nbsp;&nbsp;
        <a href="${dashboardUrl}/dashboard" style="background:#1a2040;color:#94a3b8;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:13px;display:inline-block;border:1px solid #1e2540;">
          Meu painel
        </a>
      </div>

      <!-- Footer -->
      <hr style="border:none;border-top:1px solid #1e2540;margin:0 0 16px 0;">
      <p style="color:#3a4460;font-size:11px;margin:0;text-align:center;">
        Olá, ${userName}. Você recebeu este email porque criou um alerta no Poupi.<br>
        <a href="${dashboardUrl}/dashboard" style="color:#6C2BD9;">Gerenciar alertas</a>
      </p>

    </td></tr>
  </table>
</body>
</html>`;

    try {
      await this.transporter.sendMail({
        from: `Poupi Alertas <${process.env.GMAIL_USER}>`,
        to: email,
        subject: `🔥 Preço caiu ${dropPct}% — ${productTitle.slice(0, 50)}`,
        html,
        text: `Olá ${userName}!\n\nO preço de "${productTitle}" caiu para ${fmt(currentPrice)} (era ${fmt(previousPrice)}).\n\nSua meta era ${fmt(targetPrice)}.\n\nVer produto: ${productUrl}`,
      });
      this.logger.log(`Alerta enviado → ${email} | ${productTitle.slice(0, 40)} | ${fmt(currentPrice)}`);
    } catch (err) {
      this.logger.error(`Falha ao enviar email para ${email}: ${(err as Error).message}`);
    }
  }

  async sendSmartAlert(payload: SmartAlertPayload): Promise<void> {
    const fmt = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const labels: Record<SmartAlertPayload['type'], string> = {
      NEW_LOWEST_PRICE: 'Nova minima historica',
      PRICE_DROP: 'Preco caiu',
      RESTOCKED: 'Produto voltou ao estoque',
    };
    const previous = payload.previousPrice ? `Antes: ${fmt(payload.previousPrice)}\n` : '';

    try {
      await this.transporter.sendMail({
        from: `Poupi Alertas <${process.env.GMAIL_USER}>`,
        to: payload.email,
        subject: `${labels[payload.type]} - ${payload.productTitle.slice(0, 50)}`,
        text: [
          `Ola ${payload.userName},`,
          ``,
          `${labels[payload.type]} em ${payload.marketplace}.`,
          `Produto: ${payload.productTitle}`,
          previous + `Preco atual: ${fmt(payload.currentPrice)}`,
          `Motivo: ${payload.reason}`,
          ``,
          `Ver produto: ${payload.productUrl}`,
        ].join('\n'),
      });
      this.logger.log(`Smart alert enviado -> ${payload.email} | ${payload.type}`);
    } catch (err) {
      this.logger.error(`Falha ao enviar smart alert: ${(err as Error).message}`);
    }
  }

  // ── Deal Score alto ───────────────────────────────────────────────────────

  async sendDealHighScore(payload: {
    email:        string;
    productTitle: string;
    productUrl:   string;
    score:        number;
    label:        string;
    currentPrice: number;
    discountVsAvg: number | null;
  }): Promise<void> {
    const { email, productTitle, productUrl, score, label, currentPrice, discountVsAvg } = payload;
    const fmt = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const discountStr = discountVsAvg != null ? ` (${Math.round(discountVsAvg)}% abaixo da média)` : '';

    try {
      await this.transporter.sendMail({
        from:    `Poupi Alertas <${process.env.GMAIL_USER}>`,
        to:      email,
        subject: `🎯 Deal Score ${score}/100 — ${productTitle.slice(0, 50)}`,
        text: [
          `Deal Score: ${score}/100 — ${label}`,
          `Produto: ${productTitle}`,
          `Preço atual: ${fmt(currentPrice)}${discountStr}`,
          `Ver oferta: ${productUrl}`,
        ].join('\n'),
      });
      this.logger.log(`Deal score email enviado → ${email} | score=${score}`);
    } catch (err) {
      this.logger.error(`Falha ao enviar deal score email: ${(err as Error).message}`);
    }
  }

  // ── Trust Score baixo ─────────────────────────────────────────────────────

  async sendTrustLowScore(payload: {
    email:        string;
    productTitle: string;
    marketplace:  string;
    trustScore:   number;
    trustLabel:   string;
  }): Promise<void> {
    const { email, productTitle, marketplace, trustScore, trustLabel } = payload;

    try {
      await this.transporter.sendMail({
        from:    `Poupi Alertas <${process.env.GMAIL_USER}>`,
        to:      email,
        subject: `⚠️ Trust Score baixo — ${productTitle.slice(0, 50)}`,
        text: [
          `O produto "${productTitle}" em ${marketplace} tem Trust Score: ${trustScore}/100 (${trustLabel}).`,
          `Isso pode indicar reviews suspeitos ou problemas de qualidade.',`,
          `Recomendamos verificar as avaliações antes de comprar.`,
        ].join('\n'),
      });
      this.logger.log(`Trust score alert enviado → ${email} | score=${trustScore}`);
    } catch (err) {
      this.logger.error(`Falha ao enviar trust score alert: ${(err as Error).message}`);
    }
  }

  // ── Incidente de scraping (admin) ─────────────────────────────────────────

  async sendIncidentAlert(payload: {
    incidentId:  string;
    marketplace: string;
    severity:    string;
    rootCause:   string;
    suggestions: string[];
  }): Promise<void> {
    const { incidentId, marketplace, severity, rootCause, suggestions } = payload;
    const adminEmail = process.env.ADMIN_EMAIL;
    if (!adminEmail) return; // sem email de admin configurado

    try {
      await this.transporter.sendMail({
        from:    `Poupi Ops <${process.env.GMAIL_USER}>`,
        to:      adminEmail,
        subject: `🚨 [${severity.toUpperCase()}] Incidente detectado — ${marketplace}`,
        text: [
          `Incidente ID: ${incidentId}`,
          `Marketplace: ${marketplace}`,
          `Severidade: ${severity}`,
          ``,
          `Causa raiz:`,
          rootCause,
          ``,
          `Sugestões:`,
          ...suggestions.map((s, i) => `${i + 1}. ${s}`),
        ].join('\n'),
      });
      this.logger.log(`Incident alert enviado → ${adminEmail} | ${marketplace} ${severity}`);
    } catch (err) {
      this.logger.error(`Falha ao enviar incident alert: ${(err as Error).message}`);
    }
  }
}
