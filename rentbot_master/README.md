# RentBot Master — Bot-arenda tizimi

Master bot orqali mijozlar o'z Telegram do'kon botini "ijaraga oladi". Har bir mijoz
o'z bot tokeni, admin ID va bot username'ini kiritadi → bot avtomatik 15 kun bepul
sinov bilan ishga tushadi → muddat tugagach pullik tarif (oylik/yillik) taklif qilinadi.

## ⚠️ MUHIM: hosting talabi

Bu tizim **doimiy ishlaydigan Python process** talab qiladi (Master bot + har bir
mijoz uchun alohida child-bot, bittasi process ichida asyncio orqali parallel).

**fhost.uz kabi oddiy "shared hosting" (cPanel, faqat PHP/MySQL/disk asosida tariflar)
bu turdagi botlarni ishlata olmaydi** — ular faqat HTTP so'rovi kelganda PHP skript
ishga tushiradigan tizim, lekin uzluksiz "doim tirik" Python jarayonini saqlay olmaydi.

Bu kod ishlashi uchun quyidagilardan biri kerak:
- **VPS** (masalan: Hetzner, DigitalOcean, Beget, yoki O'zbekiston VPS provayderlari) — SSH orqali kirib, `python main.py`ni systemd/screen/tmux orqali doimiy ishlatish
- **Render.com**, Railway, Fly.io kabi "background worker" / "web service" qo'llab-quvvatlaydigan PaaS xizmatlar

Agar fhost.uz'da **VPS** xizmati ham bo'lsa (ko'pchilik o'zbek hosting kompaniyalari
buni alohida sotadi, "shared hosting"dan farqli), o'shanda bu kod ishlaydi — VPS bo'limi
uchun pastdagi "VPS'ga joylash" yo'riqnomasidan foydalaning.

---

## Loyiha tuzilishi

```
config.py                   — Master bot sozlamalari (token, owner ID, webhook)
states.py                   — Master bot conversation holatlari
master_db.py                 — Master DB: mijozlar, to'lovlar, tariflar, karta raqami
user_flow.py                  — Mijoz oqimi: forma to'ldirish, sinov, to'lov
master_admin.py               — Bosh admin: to'lovlarni tasdiqlash, tariflar, mijozlar
child_bot_manager.py          — Child-botlarni dinamik ishga tushirish/to'xtatish
scheduler.py                  — Muddati tugaganlarni avtomatik to'xtatish (fon vazifasi)
main.py                       — Bosh ishga tushiruvchi fayl
requirements.txt              — kutubxonalar
render.yaml                   — Render.com konfiguratsiyasi (agar shu platforma tanlansa)

child_bot/                    — Har bir mijoz botiga yuklanadigan kod
├── child_db.py                — SQLite: adminlar, kategoriya, mahsulot, savat, buyurtma, keshbek
├── child_states.py             — conversation holatlari
├── child_owner.py              — 1-daraja (bot egasi): admin qo'shish, sozlamalar
├── child_shop_admin.py         — kategoriya/mahsulot/buyurtma boshqaruvi (1 va 2-daraja)
└── child_user.py                — mijoz: katalog, savat, lokatsiya, keshbek, referal, TOP10
```

## O'rnatish (VPS yoki SSH kirish mavjud serverda)

```bash
# 1. Python 3.11+ borligini tekshirish
python3 --version

# 2. Kerakli kutubxonalar
pip install -r requirements.txt --break-system-packages

# 3. config.py ni sozlash (yoki muhit o'zgaruvchilari orqali)
export MASTER_BOT_TOKEN="sizning_yangi_master_bot_tokeningiz"
export OWNER_IDS="sizning_telegram_id_raqamingiz"
export ADMIN_CONTACT_USERNAME="sizning_username"

# 4. Ishga tushirish (test uchun)
python3 main.py
```

`WEBHOOK_BASE_URL` berilmagan bo'lsa, bot **polling** rejimida ishlaydi — VPS uchun
eng oson va ishonchli usul shu.

### Doimiy ishlashi uchun (VPS'da 24/7)

```bash
# screen bilan oddiy usul
screen -S rentbot
python3 main.py
# Ctrl+A keyin D bosib chiqing (bot fonda davom etadi)

# Yoki systemd service (tavsiya etiladi, server qayta yuklanganda ham avtomatik ishga tushadi)
sudo nano /etc/systemd/system/rentbot.service
```

systemd fayl namunasi:
```ini
[Unit]
Description=RentBot Master
After=network.target

[Service]
User=root
WorkingDirectory=/root/rentbot_master
ExecStart=/usr/bin/python3 main.py
Restart=always
Environment=MASTER_BOT_TOKEN=sizning_tokeningiz
Environment=OWNER_IDS=sizning_id_raqamingiz

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable rentbot
sudo systemctl start rentbot
sudo systemctl status rentbot   # holatni tekshirish
journalctl -u rentbot -f         # jonli loglarni ko'rish
```

## ⚠️ Xavfsizlik: token haqida

Hech qachon bot tokenini chatda, kodda yoki ochiq joyda yubormang. Agar biror token
tasodifan oshkor bo'lib qolgan bo'lsa, darhol @BotFather → `/mybots` → **Revoke token**
qiling va yangisini oling.

## ⚠️ MUHIM: token va ID'lar qayerga kiritiladi

Bu loyihada 2 xil token/ID bor — ularni adashtirmang:

**1. Master bot** (sizning asosiy botingiz) — Render Environment Variables yoki `.env`
faylga kiritiladi, kodga yozilmaydi:
- `MASTER_BOT_TOKEN` — Master botning o'z tokeni
- `OWNER_IDS` — sizning (bosh adminning) Telegram ID raqami(lari)

**2. Child-bot** (har bir mijozning o'z do'kon boti) — bu hech qachon faylga yoki
kodga yozilmaydi. Mijoz buni Master botga kirib, "⚙️ Bot ma'lumotlarini to'ldirish"
formasi orqali **chatda** kiritadi (bot tokeni, bot admin ID, bot username). Bu
ma'lumotlar avtomatik Master DB'ga saqlanadi va siz tasdiqlagach, tizim child-botni
shu token bilan dinamik ishga tushiradi — sizdan qo'lda hech narsa kiritish talab
qilinmaydi.

## Mijoz oqimi (yangilangan)

1. Mijoz Master botga kiradi → forma to'ldiradi (do'kon nomi, bot tokeni, bot admin
   ID, bot username)
2. Forma **admin (siz) tasdiqlamaguncha** sinov BERILMAYDI — sizga (bosh adminga)
   "✅ Tasdiqlash / ❌ Rad etish" tugmasi bilan so'rovnoma keladi
3. Tasdiqlasangiz → sinov muddati beriladi, child-bot darhol ishga tushadi
4. Rad etsangiz → hech narsa berilmaydi, bot ishlamaydi
5. Mijozlar ro'yxatida (👥 Mijozlar) har bir mijozning muddatini siz: +7/+30/+365 kun
   uzaytirishingiz, -7/-30 kun qisqartirishingiz, yoki "⏹ Hozir tugatish" orqali
   muddatdan oldin butunlay to'xtatishingiz mumkin

## Child-bot: birlashtirilgan admin panel

Endi child-bot ichida alohida "Owner panel" va "Admin panel" yo'q — bittasi:
- Asosiy menyuda **faqat adminlarga** (owner yoki u qo'shgan do'kon adminlarga)
  "🛠 Admin panel" tugmasi ko'rinadi (oddiy mijozlar buni ko'rmaydi)
- Hammaga (owner + do'kon admin): Katalog, Mahsulot, Buyurtmalar boshqaruvi
- Faqat ownerga: Do'kon admin qo'shish, Yetkazib berish narxi (km/so'm), Lokatsiya,
  Karta raqami, Qo'llanma, Aloqa username

## Yetkazib berish narxi — km asosida

Owner "Yetkazib berish narxi (km/so'm)" orqali **1 km uchun narxni** kiritadi
(masalan 2000 so'm/km) va do'kon lokatsiyasini belgilaydi. Mijoz "🚚 Yetkazib berish
narxi" tugmasini bosganda lokatsiyasini yuboradi, tizim masofani (km) hisoblab,
**masofa × narx** formulasi bilan summani ko'rsatadi. Bu natija keshlanadi — agar
mijoz keyin shu seansda buyurtma bersa, lokatsiya qayta so'ralmaydi.

## Buyurtma kelganda admin nima ko'radi

Mijoz buyurtma berganda, barcha adminlarga (owner + do'kon adminlar) darhol xabar
boradi:
- Mijozning ismi va telefon raqami
- Lokatsiya — Google Maps havolasi sifatida (bosilganda xaritada ochiladi)
- Masofa (km)
- Mahsulotlar ro'yxati va umumiy summa
- **👍 Qabul qilish** / **❌ Rad etish** tugmalari — to'g'ridan-to'g'ri shu xabardan
  bosish mumkin, alohida "Buyurtmalar" ro'yxatiga kirish shart emas

## Mijoz huquqlari (do'kon admin)

Sizning so'rovingizga ko'ra, child-bot ichida **do'kon admin (bot egasi va u qo'shgan
2-daraja adminlar) deyarli hamma narsani qila oladi**:
- Kategoriya (katalog) qo'shish, tahrirlash, o'chirish
- Mahsulot qo'shish (nomi, birlik turi: dona/kg, olish/sotish narxi, rasm), tahrirlash, o'chirish
- Buyurtmalarni ko'rish, lokatsiyasini ko'rish, qabul qilish, rad etish, "yetkazildi" deb belgilash
- (faqat bot egasi/owner) Yangi do'kon admin qo'shish, yetkazib berish narxini va do'kon
  lokatsiyasini, karta raqamini, qo'llanma matnini sozlash

## Asosiy oqim qisqacha

1. Mijoz Master botga kiradi → "⚙️ Bot ma'lumotlarini to'ldirish" → forma (do'kon nomi,
   bot tokeni, bot admin ID, bot username) → **avtomatik 15 kun bepul sinov** boshlanadi,
   bot **darhol** ishga tushadi
2. Mijoz o'z botida /owner orqali sozlamalarni, /admin orqali kategoriya/mahsulot/buyurtmalarni boshqaradi
3. Sinov tugaganda bot avtomatik to'xtaydi (scheduler), mijozga eslatma boriladi
4. Mijoz Master botda "💳 Arenda to'lovi" → tarif tanlaydi → karta raqami ko'rinadi →
   chek yuboradi → siz (bosh admin) tasdiqlaysiz → muddat uzayadi, bot qayta ishga tushadi
5. Agar mijoz o'z botini Telegram'da o'chirsa/bloklasa, child-bot avtomatik aniqlab
   to'xtaydi (status "suspended" bo'ladi)

## Keyingi qadamlar (xohlasangiz qo'shiladi)

- PostgreSQL'ga o'tish (agar bir nechta server/instance kerak bo'lsa)
- To'lovni avtomatik tekshirish (hozir chek screenshot orqali qo'lda tasdiqlanadi)
- Mijozlar uchun statistik dashboard (savdo hajmi, eng faol botlar)
