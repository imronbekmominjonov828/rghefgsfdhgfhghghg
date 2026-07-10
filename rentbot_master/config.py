"""
MASTER BOT konfiguratsiyasi.
Bu bot — sizning asosiy botingiz (masalan @Onlinearendabot).
Mijozlar shu botga kirib, "do'kon boti"ni ijaraga oladi.
"""
import os

# Master bot tokeni (BotFather'dan)
MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN", "8730580188:AAEkwXV4LbtKL6vBS_tkoIdIZOXXTIz2gPM")

# Siz (bosh admin) Telegram ID raqami(lari), vergul bilan: "111,222"
_owner_ids_raw = os.getenv("OWNER_IDS", "123456789")
OWNER_IDS = [int(x.strip()) for x in _owner_ids_raw.split(",") if x.strip()]

# Aloqa uchun admin username (mijoz "Admin bilan aloqa" bosganda ko'rsatiladigan)
ADMIN_CONTACT_USERNAME = os.getenv("ADMIN_CONTACT_USERNAME", "your_username")

# Master bot ma'lumotlar bazasi
MASTER_DB_PATH = os.getenv("MASTER_DB_PATH", "master.db")

# Har bir child-bot uchun alohida SQLite fayl shu papkada saqlanadi
CHILD_DB_DIR = os.getenv("CHILD_DB_DIR", "child_dbs")

# Standart tariflar (birinchi marta ishga tushganda DB'ga yoziladi, keyin admin panel orqali o'zgartiriladi)
DEFAULT_TARIFFS = {
    "trial_days": 15,        # sinov muddati (kun)
    "monthly_price": 50000,  # oylik narx, so'm
    "yearly_price": 500000,  # yillik narx, so'm
}

# Sahifalash
PAGE_SIZE = 10

# Render uchun (VPS'da ishlatilganda WEBHOOK_BASE_URL bo'sh qoldiriladi, polling ishlaydi)
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://rghefgsfdhgfhghghg.onrender.com")  # https://xxx.onrender.com yoki bo'sh
USE_WEBHOOK = bool(WEBHOOK_BASE_URL)
