![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-blue)

# 🛍️ lavka.global — Backend

Multi-tenant SaaS e-commerce platform for social media sellers (Instagram, WhatsApp).

### 🚀 About
 
**[lavka.global](https://lavka.global)** is a platform between a link-in-bio tool and full e-commerce — simpler and cheaper than Shopify. It allows sellers to create product catalogs on subdomains with WhatsApp/Telegram order routing.

### ⚙️ Tech Stack
 
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (Python) |
| Database | PostgreSQL |
| Cache | Redis |
| Storage | S3-compatible bucket (Railway) |
| Email | Resend |
| Payments | Robokassa |
| Monitoring | Sentry |
| Hosting | Railway |
 
### ✨ Features
 
- 🔐 **Auth** — Magic link + Google OAuth, JWT in httpOnly cookies with refresh token rotation
- 🏪 **Multi-tenant** — Each seller gets their own subdomain storefront
- 🖼️ **Products** — Up to 5 images per product, WebP compression via Pillow, S3 storage
- 💳 **Payments** — Robokassa integration with webhook validation, international card support
- 📧 **Email** — Transactional emails via Resend
- 🔄 **Caching** — Redis caching with cache invalidation across seller and public showcase keys
- ⏰ **Scheduler** — APScheduler for subscription lifecycle management
- 🗄️ **Migrations** — Alembic migrations on PostgreSQL
- 🔍 **Monitoring** — Error tracking and logging via Sentry

## 📬 Contact
 
- Telegram: [@vasilevdima](https://t.me/vasilevdima)
- GitHub: [Vasilev-Dmitry](https://github.com/Vasilev-Dmitry)
