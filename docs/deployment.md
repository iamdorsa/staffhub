# راهنمای استقرار StaffHub (Deployment Guide)

این سند مراحل کامل استقرار پروژه StaffHub شامل بک‌اند (FastAPI)، فرانت‌اند (React) و دیتابیس (MariaDB) را با Docker Compose توضیح می‌دهد.

---

## فهرست مطالب

1. [پیش‌نیازها](#1-پیش‌نیازها)
2. [ساختار پروژه](#2-ساختار-پروژه)
3. [تنظیمات محیطی (Environment Variables)](#3-تنظیمات-محیطی)
4. [استقرار سریع (Quick Start)](#4-استقرار-سریع)
5. [توضیح سرویس‌ها](#5-توضیح-سرویس‌ها)
6. [مایگریشن‌ها (Migrations)](#6-مایگریشن‌ها)
7. [سیدینگ دیتابیس (Seeding)](#7-سیدینگ-دیتابیس)
8. [استقرار فرانت‌اند](#8-استقرار-فرانت‌اند)
9. [دستورات مفید](#9-دستورات-مفید)
10. [استقرار در محیط پروداکشن](#10-استقرار-در-محیط-پروداکشن)
11. [عیب‌یابی (Troubleshooting)](#11-عیب‌یابی)
12. [استقرار بدون Docker](#12-استقرار-بدون-docker)

---

## 1. پیش‌نیازها

نرم‌افزارهای مورد نیاز روی سرور یا ماشین شما:

| نرم‌افزار | نسخه حداقل | دستور بررسی |
|-----------|-----------|-------------|
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.20+ (plugin) | `docker compose version` |
| Git | 2.x | `git --version` |

> **نکته:** نسخه‌های جدید Docker، plugin `compose` را به صورت پیش‌فرض دارند. اگر `docker compose` کار نکرد، از `docker-compose` (با خط تیره) استفاده کنید.

### بررسی سریع

```bash
docker --version
docker compose version
```

---

## 2. ساختار پروژه

```
staffhub/                        ← بک‌اند (FastAPI)
├── Dockerfile                   ← Docker image بک‌اند
├── docker-compose.yml           ← اصلی — همه سرویس‌ها
├── docker-entrypoint.sh         ← نقطه ورود کانتینر
├── .env                         ← تنظیمات محیطی (ساخته می‌شود)
├── .env.example                 ← الگوی تنظیمات
├── requirements.txt             ← وابستگی‌های Python
├── src/                         ← کد اصلی FastAPI
│   ├── main.py                  ← Entry point
│   ├── config.py                ← تنظیمات (از .env می‌خواند)
│   ├── core/                    ← database, security, exceptions
│   └── modules/                 ← auth, users, accommodation
├── db/                          ← مدل‌ها و مایگریشن‌ها
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/            ← 8 مایگریشن
│   └── models/                  ← SQLAlchemy models
└── scripts/                     ← سید و جاب‌ها
    ├── seed_admin.py
    ├── seed_mock_data.py
    └── expire_reservations.py

staffhub-ui-v2/                  ← فرانت‌اند (React)
├── Dockerfile                   ← Multi-stage build + Nginx
├── nginx.conf                   ← پراکسی /api به بک‌اند
├── package.json
├── vite.config.ts
├── src/                         ← کد React
└── dist/                        ← خروجی build
```

---

## 3. تنظیمات محیطی

### ساخت فایل `.env`

```bash
cd staffhub/
cp .env.example .env
```

فایل `.env` را ویرایش کنید:

```env
# ── الزامی ──────────────────────────────────────────────────
SECRET_KEY=your-very-long-random-secret-key-at-least-32-chars

# ── دیتابیس (Docker Compose) ───────────────────────────────
DB_ROOT_PASSWORD=your-strong-db-password
DB_NAME=staffhub_db

# ── پورت‌ها ──────────────────────────────────────────────────
DB_PORT=3306
API_PORT=8000
WEB_PORT=80
PMA_PORT=8080

# ── API ──────────────────────────────────────────────────────
API_WORKERS=4

# ── SMS (اختیاری) ───────────────────────────────────────────
# SMS_PROVIDER=console
# SMS_API_KEY=your-sms-api-key
```

### ایجاد SECRET_KEY امن

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

یا:

```bash
openssl rand -base64 48
```

### جدول کامل متغیرها

| متغیر | الزامی | پیش‌فرض | توضیح |
|--------|--------|---------|-------|
| `SECRET_KEY` | بله | — | کلید رمزنگاری JWT |
| `DB_ROOT_PASSWORD` | بله | `root` | رمز root دیتابیس |
| `DB_NAME` | خیر | `staffhub_db` | نام دیتابیس |
| `DB_PORT` | خیر | `3306` | پورت MariaDB |
| `API_PORT` | خیر | `8000` | پورت API (دسترسی مستقیم) |
| `API_WORKERS` | خیر | `4` | تعداد worker های Gunicorn |
| `WEB_PORT` | خیر | `80` | پورت وب (Nginx) |
| `PMA_PORT` | خیر | `8080` | پورت phpMyAdmin |
| `SMS_PROVIDER` | خیر | `console` | ارائه‌دهنده SMS |
| `SMS_API_KEY` | خیر | — | کلید API اس‌ام‌اس |

---

## 4. استقرار سریع

### گام ۱: کلون کردن پروژه‌ها

```bash
git clone <repo-url>/staffhub.git
git clone <repo-url>/staffhub-ui-v2.git
```

> **مهم:** هر دو پروژه باید در کنار هم باشند:
> ```
> my-projects/
> ├── staffhub/
> └── staffhub-ui-v2/
> ```

### گام ۲: تنظیمات

```bash
cd staffhub/
cp .env.example .env
# ویرایش .env و تنظیم SECRET_KEY و DB_ROOT_PASSWORD
```

### گام ۳: بیلد و اجرا

```bash
# بیلد تمام image ها
docker compose build

# اجرای سرویس‌ها (دیتابیس + مایگریشن + سید admin + API + فرانت‌اند)
docker compose up -d
```

### گام ۴: بررسی وضعیت

```bash
docker compose ps
```

خروجی مورد انتظار:

```
NAME              SERVICE     STATUS
staffhub-mariadb  mariadb     running (healthy)
staffhub-migrate  migrate     exited (0)        ← موفق
staffhub-seed-admin seed-admin exited (0)        ← موفق
staffhub-api      api         running (healthy)
staffhub-web      web         running
```

### گام ۵: تست

```bash
# بررسی API
curl http://localhost:8000/health
# خروجی: {"status":"ok"}

# بررسی فرانت‌اند
curl -s http://localhost/ | head -5
```

اکنون اپلیکیشن در آدرس‌های زیر در دسترس است:

| سرویس | آدرس |
|--------|------|
| فرانت‌اند | http://localhost |
| API مستقیم | http://localhost:8000 |
| API Docs (Swagger) | http://localhost/docs |
| Health Check | http://localhost/health |

**ورود اولیه:**
- نام کاربری: `admin`
- رمز عبور: `admin`

---

## 5. توضیح سرویس‌ها

### `mariadb` — دیتابیس

- **Image:** `mariadb:11`
- **نقش:** ذخیره‌سازی تمام داده‌های اپلیکیشن
- **Volume:** `mariadb_data` — داده‌ها بین ریستارت‌ها حفظ می‌شوند
- **Healthcheck:** بررسی اتصال و آمادگی InnoDB

### `migrate` — مایگریشن (run-once)

- **نقش:** اجرای Alembic migrations
- **وابستگی:** منتظر healthy شدن `mariadb`
- **رفتار:** اجرا و خروج — کانتینر بعد از اتمام متوقف می‌شود

### `seed-admin` — سید ادمین (run-once)

- **نقش:** ایجاد کاربر admin اولیه و سازمان HQ
- **وابستگی:** منتظر اتمام موفق `migrate`
- **رفتار:** اجرا و خروج

### `api` — بک‌اند

- **نقش:** سرور FastAPI (Gunicorn + Uvicorn workers)
- **پورت:** `8000`
- **وابستگی:** منتظر اتمام موفق `migrate`
- **Healthcheck:** بررسی endpoint `/health`

### `web` — فرانت‌اند

- **نقش:** سرو فایل‌های React (Nginx) + پراکسی `/api` به بک‌اند
- **پورت:** `80`
- **وابستگی:** منتظر healthy شدن `api`
- **Build:** Multi-stage (Node build → Nginx serve)

### `seed-mock` — داده تستی (اختیاری)

- **Profile:** `seed` — فقط با فلگ `--profile seed` اجرا می‌شود
- **نقش:** ایجاد اقامتگاه‌ها، اتاق‌ها، تعرفه‌ها و امتیازات نمونه

### `cron` — جاب زمان‌بندی شده (اختیاری)

- **Profile:** `cron` — فقط با فلگ `--profile cron` اجرا می‌شود
- **نقش:** هر ساعت رزروهای منقضی شده را بررسی می‌کند

### `phpmyadmin` — مدیریت دیتابیس (اختیاری)

- **Profile:** `dev` — فقط با فلگ `--profile dev` اجرا می‌شود
- **پورت:** `8080`

---

## 6. مایگریشن‌ها

### اجرای خودکار

مایگریشن‌ها با `docker compose up` به صورت خودکار اجرا می‌شوند (سرویس `migrate`).

### اجرای دستی

```bash
# اجرای مایگریشن‌ها
docker compose run --rm migrate

# بررسی وضعیت فعلی مایگریشن‌ها
docker compose run --rm api bash -c "cd /app/db && python -m alembic current"

# مشاهده تاریخچه مایگریشن‌ها
docker compose run --rm api bash -c "cd /app/db && python -m alembic history"
```

### ایجاد مایگریشن جدید

```bash
# ابتدا مدل را تغییر دهید، سپس:
docker compose run --rm api bash -c "cd /app/db && python -m alembic revision -m 'description_of_change'"
```

### رول‌بک مایگریشن

```bash
# برگشت یک مرحله
docker compose run --rm api bash -c "cd /app/db && python -m alembic downgrade -1"

# برگشت به revision خاص
docker compose run --rm api bash -c "cd /app/db && python -m alembic downgrade <revision_id>"
```

### لیست مایگریشن‌ها

| شماره | فایل | توضیح |
|-------|------|-------|
| 001 | `create_identity_access_tables` | جداول سازمان، کاربر، نقش، مجوز |
| 002 | `create_accommodation_tables` | جداول اقامتگاه، اتاق، تعرفه، رزرو |
| 003 | `seed_default_roles_permissions` | سید نقش‌ها و مجوزهای پیش‌فرض |
| 004 | `refactor_special_plans_to_org_level` | بازسازی پلن‌های ویژه به سطح سازمان |
| 005 | `add_spouse_fields_to_user_profiles` | فیلدهای همسر در پروفایل |
| 006 | `add_is_vip_to_place_rooms` | فلگ VIP برای اتاق‌ها |
| 007 | `add_name_to_place_rooms` | نام اختصاصی اتاق‌ها |
| 008 | `create_place_ratings` | سیستم امتیازدهی اقامتگاه |

---

## 7. سیدینگ دیتابیس

### سید ادمین (خودکار)

سید admin به صورت خودکار با `docker compose up` اجرا می‌شود.

**اطلاعات ادمین:**
- نام کاربری: `admin`
- رمز عبور: `admin`
- نقش: `SUPER_ADMIN`
- سازمان: `HQ` (Headquarters)

> **هشدار:** بلافاصله بعد از اولین ورود، رمز ادمین را تغییر دهید.

### سید داده تستی (اختیاری)

```bash
# اجرا با profile seed
docker compose --profile seed up seed-mock

# یا اجرای مستقیم
docker compose run --rm seed-mock
```

**داده‌های تستی شامل:**
- ۵ اقامتگاه (کیش، مشهد، اصفهان، شیراز، رامسر)
- اتاق‌های تک‌خوابه و دوخوابه برای هر اقامتگاه
- سوئیت VIP برای هر اقامتگاه
- تعرفه‌های کارمند و مهمان
- دسترسی سازمان HQ به تمام اقامتگاه‌ها
- امتیازات نمونه

### اجرای دستی seed ها

```bash
# seed admin
docker compose run --rm api python -m scripts.seed_admin

# seed mock data
docker compose run --rm api python -m scripts.seed_mock_data

# اجرای دستی expiry job
docker compose run --rm api python -m scripts.expire_reservations
```

---

## 8. استقرار فرانت‌اند

### نحوه عملکرد

فرانت‌اند یک SPA (Single Page Application) است:

1. **Build stage:** Node.js کد TypeScript/React را به فایل‌های استاتیک (`dist/`) کامپایل می‌کند
2. **Serve stage:** Nginx فایل‌های استاتیک را سرو می‌کند و درخواست‌های `/api` را به بک‌اند پراکسی می‌کند

### Build process

```
staffhub-ui-v2/
├── src/          →  npm run build  →  dist/
│   ├── App.tsx                        ├── index.html
│   ├── main.tsx                       ├── assets/
│   └── ...                            │   ├── index-xxxx.js
│                                      │   └── index-xxxx.css
│                                      ├── favicon.svg
│                                      └── icons.svg
```

### Nginx Routing

| مسیر | هدف |
|------|-----|
| `/api/*` | پراکسی به `http://api:8000` (بک‌اند) |
| `/health` | پراکسی به بک‌اند |
| `/docs` | پراکسی به Swagger UI |
| `/assets/*` | فایل‌های استاتیک با کش ۱ ساله |
| `/*` (بقیه) | `index.html` — SPA routing |

### بیلد جداگانه فرانت‌اند

اگر فقط فرانت‌اند را تغییر داده‌اید:

```bash
# بازسازی فقط image فرانت‌اند
docker compose build web

# ریستارت فرانت‌اند
docker compose up -d web
```

### بیلد لوکال (بدون Docker)

```bash
cd staffhub-ui-v2/
npm install
npm run build
# خروجی در dist/ — آپلود به هر وب‌سرور
```

---

## 9. دستورات مفید

### مدیریت سرویس‌ها

```bash
# اجرای تمام سرویس‌ها
docker compose up -d

# اجرای تمام سرویس‌ها + phpMyAdmin + داده تستی
docker compose --profile dev --profile seed up -d

# اجرا با cron job
docker compose --profile cron up -d

# متوقف کردن تمام سرویس‌ها
docker compose down

# متوقف کردن + حذف volumeها (پاک شدن دیتابیس!)
docker compose down -v

# ریستارت یک سرویس
docker compose restart api

# مشاهده لاگ‌ها
docker compose logs -f api
docker compose logs -f web
docker compose logs migrate seed-admin

# مشاهده وضعیت
docker compose ps
```

### بازسازی (Rebuild)

```bash
# بازسازی تمام imageها
docker compose build

# بازسازی بدون کش
docker compose build --no-cache

# بازسازی و اجرا
docker compose up -d --build

# بازسازی فقط یک سرویس
docker compose build api
docker compose build web
```

### دسترسی به Shell

```bash
# shell بک‌اند
docker compose exec api bash

# shell دیتابیس
docker compose exec mariadb mysql -u root -p staffhub_db

# shell فرانت‌اند (Nginx)
docker compose exec web sh
```

### مانیتورینگ

```bash
# مصرف منابع
docker compose top
docker stats

# بررسی سلامت
curl http://localhost/health
curl http://localhost:8000/health
```

---

## 10. استقرار در محیط پروداکشن

### چک‌لیست امنیتی

- [ ] `SECRET_KEY` تصادفی و قوی تنظیم شده (حداقل ۶۴ کاراکتر)
- [ ] `DB_ROOT_PASSWORD` قوی تنظیم شده
- [ ] پورت `3306` (دیتابیس) از بیرون بسته شده
- [ ] پورت `8000` (API مستقیم) از بیرون بسته شده
- [ ] پورت `8080` (phpMyAdmin) غیرفعال شده (profile `dev` را استفاده نکنید)
- [ ] رمز ادمین پیش‌فرض تغییر داده شده
- [ ] HTTPS فعال شده (SSL/TLS)
- [ ] فایل `.env` در `.gitignore` است

### تنظیم HTTPS

گزینه ۱: Nginx خارجی با Certbot

```nginx
# /etc/nginx/sites-available/staffhub
server {
    listen 80;
    server_name staffhub.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name staffhub.example.com;

    ssl_certificate /etc/letsencrypt/live/staffhub.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staffhub.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

گزینه ۲: Traefik یا Caddy به عنوان reverse proxy

### بستن پورت‌های غیرضروری

در `docker-compose.yml` فقط پورت `80` (یا `443`) را expose کنید:

```yaml
services:
  mariadb:
    # ports: را حذف کنید
  api:
    # ports: را حذف کنید — فقط از طریق Nginx
  web:
    ports:
      - "80:80"
```

### تنظیم تعداد Worker ها

```env
# به ازای هر CPU core تقریبا 2 worker
# سرور 2 core: API_WORKERS=4
# سرور 4 core: API_WORKERS=8
API_WORKERS=4
```

### بک‌آپ دیتابیس

```bash
# بک‌آپ
docker compose exec mariadb mysqldump -u root -p staffhub_db > backup_$(date +%Y%m%d).sql

# بازیابی
docker compose exec -i mariadb mysql -u root -p staffhub_db < backup_20260514.sql
```

---

## 11. عیب‌یابی

### مشکل: مایگریشن شکست می‌خورد

```bash
# بررسی لاگ
docker compose logs migrate

# علت احتمالی: دیتابیس هنوز آماده نیست
# راه‌حل: دوباره اجرا کنید
docker compose run --rm migrate
```

### مشکل: فرانت‌اند API را پیدا نمی‌کند

```bash
# بررسی ارتباط Nginx با API
docker compose exec web wget -qO- http://api:8000/health

# بررسی لاگ Nginx
docker compose logs web
```

### مشکل: خطای اتصال دیتابیس

```bash
# بررسی سلامت دیتابیس
docker compose exec mariadb mysql -u root -proot -e "SELECT 1"

# بررسی network
docker compose exec api python -c "
from src.core.database import engine
with engine.connect() as c:
    print(c.execute('SELECT 1').scalar())
    print('Connection OK')
"
```

### مشکل: فونت‌ها لود نمی‌شوند

فرانت‌اند از Google Fonts CDN استفاده می‌کند. اگر سرور به اینترنت دسترسی ندارد:

1. فونت‌ها را دانلود کنید
2. در `public/fonts/` قرار دهید
3. `index.html` را ویرایش کنید تا از فایل لوکال استفاده کند

### ریست کامل

```bash
# حذف همه چیز و شروع از صفر
docker compose down -v
docker compose up -d --build
```

---

## 12. استقرار بدون Docker

اگر Docker استفاده نمی‌کنید:

### الف) دیتابیس

```bash
# نصب MariaDB 11
sudo apt install mariadb-server

# ساخت دیتابیس
mysql -u root -p -e "CREATE DATABASE staffhub_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### ب) بک‌اند

```bash
cd staffhub/

# ساخت virtual environment
python3.13 -m venv venv
source venv/bin/activate

# نصب وابستگی‌ها
pip install -r requirements.txt gunicorn

# تنظیم محیط
cp .env.example .env
# ویرایش .env

# مایگریشن
cd db/
DATABASE_URL="mysql+pymysql://root:root@localhost:3306/staffhub_db?charset=utf8mb4" python -m alembic upgrade head
cd ..

# سید ادمین
python -m scripts.seed_admin

# سید داده تستی (اختیاری)
python -m scripts.seed_mock_data

# اجرای سرور (development)
uvicorn src.main:app --reload --port 8000

# اجرای سرور (production)
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### ج) فرانت‌اند

```bash
cd staffhub-ui-v2/

# نصب وابستگی‌ها
npm install

# اجرای development server
npm run dev
# → http://localhost:5173 (پراکسی /api به localhost:8000)

# بیلد production
npm run build
# → خروجی در dist/
```

سرو فایل‌های `dist/` با Nginx:

```bash
sudo cp -r dist/* /var/www/staffhub/
```

```nginx
# /etc/nginx/sites-available/staffhub
server {
    listen 80;
    server_name staffhub.example.com;
    root /var/www/staffhub;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### د) Cron Job برای انقضای رزروها

```bash
# اضافه به crontab
crontab -e

# هر ساعت اجرا شود
0 * * * * cd /path/to/staffhub && /path/to/venv/bin/python -m scripts.expire_reservations >> /var/log/staffhub-cron.log 2>&1
```

---

## خلاصه دستورات

| کار | دستور |
|-----|-------|
| اجرای کل سیستم | `docker compose up -d` |
| اجرا + داده تستی | `docker compose --profile seed up -d` |
| اجرا + phpMyAdmin | `docker compose --profile dev up -d` |
| اجرا + cron job | `docker compose --profile cron up -d` |
| همه چیز | `docker compose --profile dev --profile seed --profile cron up -d` |
| فقط مایگریشن | `docker compose run --rm migrate` |
| فقط سید ادمین | `docker compose run --rm seed-admin` |
| فقط سید تستی | `docker compose run --rm seed-mock` |
| بازسازی | `docker compose up -d --build` |
| لاگ‌ها | `docker compose logs -f` |
| توقف | `docker compose down` |
| ریست کامل | `docker compose down -v && docker compose up -d --build` |
