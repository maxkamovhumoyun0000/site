# Deploy Runbook

Bu loyiha production serverda ishlaydi:

- Server: `root@31.220.87.193`
- SSH key: `/home/xumoyun-maxkamov/.ssh/myserver.key`
- Server path: `/root/diamond-site`

## Muhim Eslatma

- Backup olinmasin.
- Data papkalar yangilanmasin.
- Media/upload/runtime fayllarga tegilmasin.
- `--delete` ishlatilmasin.
- `.env`, `data/`, upload/media papkalar, `.venv/`, `node_modules/`, `.next/` serverda o'z holicha qolsin.
- Deploy faqat kod fayllarni serverga yuborish uchun ishlatiladi.

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
