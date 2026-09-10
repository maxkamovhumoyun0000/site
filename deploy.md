# Deploy Runbook

Bu loyiha production serverda ishlaydi:

- Server: `root@31.220.87.193`
- SSH key: `/home/xumoyun-maxkamov/.ssh/myserver.key`
- Server path: `/root/diamond-site`

## Muhim Eslatma

- **Har qanday sayt deployidan oldin database backup olinishi shart.**
- Data papkalar yangilanmasin.
- Media/upload/runtime fayllarga tegilmasin.
- `--delete` ishlatilmasin.
- `.env`, `data/`, upload/media papkalar, `.venv/`, `node_modules/`, `.next/` serverda o'z holicha qolsin.
- Deploy faqat kod fayllarni serverga yuborish uchun ishlatiladi.

## Majburiy: Deploydan Oldin Database Backup

Saytda kod, dizayn yoki API bilan bog'liq istalgan o'zgarishni productionga
chiqarishdan **oldin** ushbu backup bajariladi. Backup serverning o'zida,
faqat root kira oladigan `/root/diamond-backups/` papkasiga yoziladi; u
`data/`, media va upload fayllariga tegmaydi.

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no root@31.220.87.193 \
  "cd /root/diamond-site && .venv/bin/python - <<'PY'
import os
import subprocess
from datetime import datetime
from pathlib import Path

database_url = ''
for raw in Path('.env').read_text(encoding='utf-8').splitlines():
    line = raw.strip()
    if line.startswith('DATABASE_URL='):
        database_url = line.split('=', 1)[1].strip().strip(chr(34)).strip(chr(39))
        break
if not database_url:
    raise RuntimeError('DATABASE_URL is not configured')
backup_dir = Path('/root/diamond-backups')
backup_dir.mkdir(mode=0o700, exist_ok=True)
backup_path = backup_dir / f\"diamond-site-{datetime.now().strftime('%Y%m%d-%H%M%S')}.dump\"
os.umask(0o077)
subprocess.run(['pg_dump', database_url, '--format=custom', '--file', str(backup_path)], check=True)
if not backup_path.is_file() or backup_path.stat().st_size < 1024:
    raise RuntimeError('Database backup was not created correctly')
print(f'backup:{backup_path.name} size:{backup_path.stat().st_size}')
PY"
```

Backup muvaffaqiyatli yakunlangani tasdiqlanmaguncha keyingi deploy qadami
bajarilmaydi.

## Kodni Serverga Sync Qilish

Lokal project rootdan bajariladi:

```bash
cd /home/xumoyun-maxkamov/Desktop/diamond-site

rsync -az --prune-empty-dirs \
  -e 'ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no' \
  --exclude='.env' --exclude='.env.*' \
  --exclude='data/***' --exclude='logs/***' \
  --exclude='node_modules/***' --exclude='.next/***' \
  --exclude='.venv/***' --exclude='venv/***' --exclude='__pycache__/***' \
  --exclude='*.db' --exclude='*.sqlite' --exclude='*.sqlite3' \
  --exclude='uploads/***' --exclude='media/***' \
  --exclude='public/uploads/***' --exclude='public/media/***' \
  --include='*/' \
  --include='*.py' --include='*.ts' --include='*.tsx' \
  --include='*.js' --include='*.mjs' --include='*.cjs' \
  --include='*.css' --include='*.json' --include='*.lock' \
  --include='*.html' \
  --include='*.ini' --include='*.yml' --include='*.yaml' \
  --include='requirements.txt' --include='deploy.md' \
  --exclude='*' \
  ./ root@31.220.87.193:/root/diamond-site/
```

## Serverda Tekshirish

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no root@31.220.87.193 \
  'cd /root/diamond-site && python3 -m py_compile admin_bot.py student_bot.py teacher_bot.py support_lesson.py attendance_manager.py payment.py db.py backend/main.py bot_runtime.py'
```

Frontend build:

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no root@31.220.87.193 \
  'cd /root/diamond-site && npm run build'
```

## Relaunch

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no root@31.220.87.193 \
  'systemctl restart diamond-site-frontend diamond-site-backend diamond-site-admin-bot diamond-site-student-bot diamond-site-support-bot diamond-site-teacher-bot'
```

## Deploydan Keyingi Smoke Test

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no root@31.220.87.193 \
  "curl -sS -o /dev/null -w 'home:%{http_code}\n' http://127.0.0.1:3000/ && \
   curl -sS -o /dev/null -w 'dashboard:%{http_code}\n' http://127.0.0.1:3000/dashboard && \
   curl -sS -o /dev/null -w 'backend:%{http_code}\n' http://127.0.0.1:3001/health"
```

Servis status:

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no root@31.220.87.193 \
  'systemctl --no-pager --quiet is-active diamond-site-frontend diamond-site-backend diamond-site-admin-bot diamond-site-student-bot diamond-site-support-bot diamond-site-teacher-bot && echo services:active'
```

Restart loop tekshiruvi:

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key -o StrictHostKeyChecking=no root@31.220.87.193 \
  'sleep 20 && systemctl show diamond-site-frontend diamond-site-backend diamond-site-admin-bot diamond-site-student-bot diamond-site-support-bot diamond-site-teacher-bot -p ActiveState -p SubState -p NRestarts --no-pager'
```

## Push Notifications (FCM) — Bir Martalik Sozlash

Push lar allaqachon serverda sozlangan va ishlaydi. Bu bo'lim yangi serverga ko'chirishda yoki xato bo'lsa kerak.

Arxitektura: 4 ta alohida Firebase loyihasi (student/teacher x android/ios), har biri o'z service-account kaliti bilan. Kalitlar `/root/diamond-site/secrets/` ichida emas — to'g'ridan-to'g'ri `/root/` da turadi va `.env` PATH orqali ko'rsatiladi.

### Talab qilinadigan narsalar

1. Server venv'da `firebase-admin` o'rnatilgan bo'lsin (`requirements.txt`da bor):
   ```bash
   ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key root@31.220.87.193 \
     '/root/diamond-site/.venv/bin/pip install firebase-admin==7.5.0'
   ```

2. 4 ta service-account JSON `/root/` da joylashsin (nomlari ahamiyatsiz, `.env`dagi PATH bilan mos bo'lsin bas):

   | Slot | Firebase project |
   |---|---|
   | STUDENT_ANDROID | `diamond-5efdb` |
   | STUDENT_IOS | `diamond-student-ios` |
   | TEACHER_ANDROID | `diamond-teacher-android` |
   | TEACHER_IOS | `diamond-teacher-ios` |

3. `.env`da 4 qator bo'lsin (serverdagi yo'llar bilan):
   ```env
   FIREBASE_SERVICE_ACCOUNT_PATH_STUDENT_ANDROID=/root/diamond-student-android-...json
   FIREBASE_SERVICE_ACCOUNT_PATH_STUDENT_IOS=/root/diamond-student-ios-...json
   FIREBASE_SERVICE_ACCOUNT_PATH_TEACHER_ANDROID=/root/diamond-teacher-android-...json
   FIREBASE_SERVICE_ACCOUNT_PATH_TEACHER_IOS=/root/diamond-teacher-ios-...json
   ```

4. Backend restart: `systemctl restart diamond-site-backend` (Relaunch bo'limidagi buyruq).

### Push ishlashini tekshirish

```bash
# init muvaffaqiyatli bo'lsa har bir slot uchun "initialized" ko'rinadi
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key root@31.220.87.193 \
  'journalctl -u diamond-site-backend --since -1h --no-pager | grep "push_notifications" | tail -10'

# Faol tokenlar soni (0 bo'lsa hech kim ro'yxatdan o'tmagan — ilovada login kerak)
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key root@31.220.87.193 \
  "sqlite3 /root/diamond-site/data/diamond.db \"SELECT app, platform, COUNT(*) FROM push_device_tokens GROUP BY app, platform;\""
```

### Muammolar va yechim

- **`UNREGISTERED` / `NotRegistered` loglari** — normal: foydalanuvchi ilovani o'chirib tashlagan yoki token eskirgan. Backend bunday tokenlarni keyingi yuborishda avtomatik o'chiradi (`push_notifications.py`dagi `_prune_tokens`).
- **`slot=... not configured, skipped`** — o'sha slotning `.env`dagi PATH yoki fayli yo'q/qator.
- **Ilovada push kelmaydi** — telefonda ilova ochiq login qilinganini (token ro'yxatdan o'tishi shart) va Telegram/Instagram'dagi kabi OS darajasida bildirishnomalar ruxsat etilganini tekshiring.

## Qat'iy Taqiqlangan Buyruqlar

Quyidagilarni deploy paytida ishlatmang:

```bash
rsync --delete ...
rm -rf /root/diamond-site/data
rm -rf /root/diamond-site/uploads
rm -rf /root/diamond-site/public/uploads
rm -rf /root/diamond-site/.env
git reset --hard
git checkout -- .
```

## Qisqa Checklist

1. Faqat kod sync qilindi.
2. `data/`, upload/media, `.env`, `.venv`, `node_modules`, `.next` tegilmadi.
3. Backup olinmadi.
4. Python compile OK.
5. `npm run build` OK.
6. Servislar restart qilindi.
7. Smoke test `200`.
8. `NRestarts=0`, servislar `active/running`.
