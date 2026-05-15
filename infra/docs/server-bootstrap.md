# Server Bootstrap

Base sugerida:

- Hetzner Cloud;
- Ubuntu 24.04 LTS;
- volume separado opcional para dados/backups;
- usuario admin com SSH key.

## 1. Primeiro acesso

```bash
ssh root@IP_DO_SERVIDOR
apt update && apt upgrade -y
timedatectl set-timezone America/Sao_Paulo
```

## 2. Usuario operacional

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

## 3. Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status verbose
```

## 4. Coolify

O instalador oficial atual do Coolify e:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash
```

Evite Docker instalado via snap. O instalador oficial instala/configura Docker quando necessario.

## 5. SSH hardening

Apos confirmar que o usuario `deploy` acessa por chave:

```bash
sudoedit /etc/ssh/sshd_config
```

Recomendado:

```text
PasswordAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
```

Depois:

```bash
systemctl reload ssh
```

Mantenha uma sessao SSH aberta enquanto testa outra.
