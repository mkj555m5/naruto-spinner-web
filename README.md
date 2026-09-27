# 🍥 NARUTO MULTI-SPINNER — Web Edition (Railway Ready)

لوحة تحكم ويب كاملة لأداة **NARUTO Spinner — OB55 Edition (Multi-Event)**.
المنطق الأصلي بنقل حرفي 1:1 من سكربت التيرمنال إلى تطبيق ويب.

> 👑 **Credit: KAWSAR | x64** — Telegram: [@kawsar449x](https://t.me/kawsar449x)

---

## ✨ المميزات

| الميزة | الوصف |
|--------|-------|
| 🎯 **5 أوضاع سحب** | NARUTO · SKYWIN · FIST · SASUKE · **ALL EVENTS** · CUSTOM HEX |
| 📂 **حمّل الحسابات** | JSON `[{"uid":..,"password":..}]` أو صيغة Blocks النصية |
| ⚡ **تحكم كامل** | Concurrency · Batch Size · Login Retry · البدء من حساب معين |
| 🖥️ **سجل مباشر** | تيرمنال حي داخل المتصفح مع ألوان حسب النتيجة |
| 💎 **إحصائيات حية** | عدادات VERY RARE / RARE / NORMAL لحظة بلحظة |
| 🏆 **لوحة الجوائز** | كل الـ Hits تظهر فوراً مع اسم الحساب والعنصر |
| 📥 **تصدير النتائج** | تحميل تقرير ملخص `NARUTO_spins_summary.txt` |
| 📱 **متجاوب** | يعمل على الجوال والكمبيوتر — واجهة عربية RTL |

---

## 🚀 النشر على Railway

### الطريقة 1: من GitHub (موصى بها)
1. ارفع هذا المستودع إلى GitHub (تم بالفعل ✔)
2. ادخل إلى [railway.app](https://railway.app) → **New Project**
3. اختر **Deploy from GitHub repo** → اختر المستودع
4. Railway سيتعرف تلقائياً على الـ `Dockerfile` وينشر الموقع
5. من تبويب **Settings → Networking → Generate Domain** للحصول على رابط عام

### الطريقة 2: Railway CLI
```bash
railway login
railway init
railway up
```

> ⚙️ **لا حاجة لأي متغيرات بيئة** — المنفذ يُقرأ تلقائياً من `$PORT`

### 🔗 Cloudflare WARP (مفعّل افتراضياً)

الموقع يوجّه طلبات السحب تلقائياً عبر **Cloudflare WARP** (عبر `wgcf` + `wireproxy` — userspace WireGuard بدون صلاحيات خاصة) لحل مشكلة **HTTP 400** الناتجة عن حظر IP مراكز البيانات.

| المتغير | الافتراضي | الوصف |
|---------|-----------|-------|
| `USE_WARP` | `1` | `1` = تفعيل WARP تلقائياً عند الإقلاع، `0` = تعطيل (اتصال مباشر) |
| `PROXY_URL` | فارغ | بروكسي مخصص بدل WARP — يدعم `socks5://host:port` أو `http://host:port` |
| `WARP_SOCKS` | `socks5://127.0.0.1:25344` | عنوان بروكسي WARP المحلي (لا تغيره عادة) |

- الشارة في أعلى الصفحة تعرض حالة الاتصال: **WARP ✓** أو **DIRECT**
- فحص مباشر: `GET /api/proxy` يعرفك بالضبط عبر أي IP تخرج الطلبات
- إذا فشل WARP → الموقع يتحول تلقائياً لوضع Direct مع تحذير في السجل
- 💡 **حفظ حساب WARP**: اربط Volume على `/data` في Railway حتى لا يعاد تسجيل الحساب عند كل إقلاع

### ☁️ حل بديل: بروكسي خارجي
إذا أردت استخدام VPN/بروكسي خاص بدل WARP: أضف متغير `PROXY_URL` في Railway → Variables، مثال:
```
PROXY_URL=socks5://user:pass@host:1080
```

---

## 💻 التشغيل المحلي

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 3000
```
ثم افتح: `http://localhost:3000`

### عبر Docker
```bash
docker build -t naruto-spinner .
docker run -p 3000:8080 naruto-spinner
```

---

## 🗂️ هيكل المشروع

```
naruto-spinner-web/
├── app/
│   ├── main.py            # خادم FastAPI — API + مدير المهام
│   ├── core.py            # منطق السبنر الأصلي (AES · protobuf · events)
│   └── static/
│       ├── index.html     # الواجهة (عربي RTL)
│       ├── css/style.css  # ثيم ناروتو
│       └── js/app.js      # منطق الواجهة + Polling
├── requirements.txt
├── Procfile               # Railway (Python)
├── railway.json           # Railway config (Docker)
├── Dockerfile
└── README.md
```

---

## 🔌 واجهة API

| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/api/parse` | POST | تحليل نص الحسابات وعدّها |
| `/api/start` | POST | بدء مهمة سحب جديدة |
| `/api/stop` | POST | إيقاف المهمة الحالية |
| `/api/state` | GET | الحالة الحية (سجلات + عدادات) |
| `/api/results` | GET | تحميل تقرير النتائج |
| `/api/results.json` | GET | النتائج بصيغة JSON |
| `/api/events` | GET | تعريف الأحداث وعناصرها |

---

## ⚠️ تنويه

هذه الأداة لأغراض تعليمية/شخصية وعلى مسؤولية المستخدم فقط. المؤلف الأصلي للمنطق: **KAWSAR | x64**.
