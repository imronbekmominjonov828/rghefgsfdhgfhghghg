"""
MASTER DB — Master botning o'z ma'lumotlar bazasi.

Jadvallar:
- tariffs: tarif narxlari (admin panel orqali o'zgartiriladi, bitta qator bo'ladi)
- clients: mijozlar (do'kon arendaga olganlar) — token, ID, holat, muddat
- payments: to'lov so'rovlari (screenshot, tasdiqlash/rad etish holati)
- messages: "Admin bilan aloqa" orqali kelgan xabarlar
"""
import aiosqlite
from datetime import datetime, timedelta
from config import MASTER_DB_PATH, DEFAULT_TARIFFS


async def init_master_db():
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tariffs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                trial_days INTEGER NOT NULL,
                monthly_price INTEGER NOT NULL,
                yearly_price INTEGER NOT NULL,
                card_number TEXT
            )
        """)
        # Tariflar uchun standart qator (faqat 1 marta yoziladi)
        await db.execute(
            """INSERT OR IGNORE INTO tariffs (id, trial_days, monthly_price, yearly_price)
               VALUES (1, ?, ?, ?)""",
            (DEFAULT_TARIFFS["trial_days"], DEFAULT_TARIFFS["monthly_price"], DEFAULT_TARIFFS["yearly_price"]),
        )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                bot_token TEXT,
                bot_username TEXT,
                shop_owner_id INTEGER,
                shop_name TEXT,
                plan TEXT DEFAULT 'trial',
                status TEXT DEFAULT 'pending',
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                plan TEXT,
                amount INTEGER,
                photo_file_id TEXT,
                status TEXT DEFAULT 'waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Eski bazalarda card_number ustuni bo'lmasligi mumkin - xavfsiz migratsiya
        try:
            await db.execute("ALTER TABLE tariffs ADD COLUMN card_number TEXT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE clients ADD COLUMN shop_name TEXT")
        except Exception:
            pass

        await db.commit()


# ==================== TARIFLAR ====================

async def get_tariffs():
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT trial_days, monthly_price, yearly_price FROM tariffs WHERE id = 1"
        )
        return await cursor.fetchone()


async def get_card_number():
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute("SELECT card_number FROM tariffs WHERE id = 1")
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_card_number(card_number: str):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("UPDATE tariffs SET card_number = ? WHERE id = 1", (card_number,))
        await db.commit()


async def update_tariffs(trial_days=None, monthly_price=None, yearly_price=None):
    current = await get_tariffs()
    trial_days = trial_days if trial_days is not None else current[0]
    monthly_price = monthly_price if monthly_price is not None else current[1]
    yearly_price = yearly_price if yearly_price is not None else current[2]
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute(
            "UPDATE tariffs SET trial_days = ?, monthly_price = ?, yearly_price = ? WHERE id = 1",
            (trial_days, monthly_price, yearly_price),
        )
        await db.commit()


# ==================== MIJOZLAR (CLIENTS) ====================

async def get_client(user_id: int):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, username, full_name, bot_token, bot_username,
                      shop_owner_id, plan, status, expires_at, created_at, shop_name
               FROM clients WHERE user_id = ?""",
            (user_id,),
        )
        return await cursor.fetchone()


async def get_client_by_id(client_id: int):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, username, full_name, bot_token, bot_username,
                      shop_owner_id, plan, status, expires_at, created_at, shop_name
               FROM clients WHERE id = ?""",
            (client_id,),
        )
        return await cursor.fetchone()


async def create_or_update_client(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute(
            """INSERT INTO clients (user_id, username, full_name)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET username = ?, full_name = ?""",
            (user_id, username, full_name, username, full_name),
        )
        await db.commit()


async def set_client_bot_info(user_id: int, bot_token: str, bot_username: str, shop_owner_id: int, shop_name: str = None):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute(
            """UPDATE clients SET bot_token = ?, bot_username = ?, shop_owner_id = ?, shop_name = ?
               WHERE user_id = ?""",
            (bot_token, bot_username, shop_owner_id, shop_name, user_id),
        )
        await db.commit()


async def set_client_status(user_id: int, status: str):
    """user_id orqali statusni o'zgartiradi (forma to'lgandan keyin 'review' qilish uchun)."""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("UPDATE clients SET status = ? WHERE user_id = ?", (status, user_id))
        await db.commit()


async def approve_client(client_id: int, plan: str, days: int):
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute(
            """UPDATE clients SET status = 'active', plan = ?, expires_at = ? WHERE id = ?""",
            (plan, expires_at, client_id),
        )
        await db.commit()
    return expires_at


async def extend_client(client_id: int, plan: str, days: int):
    """Mavjud muddatga qo'shimcha kun qo'shadi (agar muddat tugamagan bo'lsa) yoki yangidan boshlaydi."""
    client = await get_client_by_id(client_id)
    now = datetime.utcnow()
    current_expiry = None
    if client and client[9]:
        try:
            current_expiry = datetime.fromisoformat(client[9])
        except ValueError:
            current_expiry = None

    base = current_expiry if (current_expiry and current_expiry > now) else now
    new_expiry = (base + timedelta(days=days)).isoformat()

    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute(
            "UPDATE clients SET status = 'active', plan = ?, expires_at = ? WHERE id = ?",
            (plan, new_expiry, client_id),
        )
        await db.commit()
    return new_expiry


async def set_client_expiry(client_id: int, new_expires_at: str):
    """Admin muddatni to'g'ridan-to'g'ri (kun qo'shmasdan) belgilaydi - masalan muddatni qisqartirish uchun."""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("UPDATE clients SET expires_at = ? WHERE id = ?", (new_expires_at, client_id))
        await db.commit()


async def adjust_client_expiry_days(client_id: int, delta_days: int):
    """Mavjud muddatga +N yoki -N kun qo'shadi/ayiradi. Natija o'tmishda bo'lsa ham ruxsat (darhol tugatish uchun)."""
    client = await get_client_by_id(client_id)
    if not client or not client[9]:
        return None
    try:
        current_expiry = datetime.fromisoformat(client[9])
    except ValueError:
        return None
    new_expiry = (current_expiry + timedelta(days=delta_days)).isoformat()
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("UPDATE clients SET expires_at = ? WHERE id = ?", (new_expiry, client_id))
        await db.commit()
    return new_expiry


async def reject_client(client_id: int):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("UPDATE clients SET status = 'rejected' WHERE id = ?", (client_id,))
        await db.commit()


async def suspend_client(client_id: int):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("UPDATE clients SET status = 'suspended' WHERE id = ?", (client_id,))
        await db.commit()


async def get_all_clients(offset: int = 0, limit: int = 10, status: str = None):
    query = """SELECT id, user_id, full_name, bot_username, plan, status, expires_at
               FROM clients"""
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()


async def count_all_clients(status: str = None) -> int:
    query = "SELECT COUNT(*) FROM clients"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_active_clients_with_tokens():
    """Bot manager ishga tushirishi kerak bo'lgan barcha aktiv mijozlar."""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, bot_token, bot_username, shop_owner_id FROM clients
               WHERE status = 'active' AND bot_token IS NOT NULL"""
        )
        return await cursor.fetchall()


async def get_expired_active_clients():
    """Muddati o'tgan, lekin hali 'active' deb belgilangan mijozlar."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, bot_username FROM clients
               WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at < ?""",
            (now,),
        )
        return await cursor.fetchall()


async def get_soon_expiring_clients(within_hours: int = 24):
    """Yaqin kunda (masalan 24 soat ichida) muddati tugaydigan mijozlar — eslatma yuborish uchun."""
    now = datetime.utcnow()
    soon = (now + timedelta(hours=within_hours)).isoformat()
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, bot_username, expires_at FROM clients
               WHERE status = 'active' AND expires_at IS NOT NULL
                     AND expires_at < ? AND expires_at > ?""",
            (soon, now.isoformat()),
        )
        return await cursor.fetchall()


# ==================== TO'LOVLAR ====================

async def create_payment(client_id: int, plan: str, amount: int, photo_file_id: str) -> int:
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO payments (client_id, plan, amount, photo_file_id)
               VALUES (?, ?, ?, ?)""",
            (client_id, plan, amount, photo_file_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_payment(payment_id: int):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, client_id, plan, amount, photo_file_id, status, created_at
               FROM payments WHERE id = ?""",
            (payment_id,),
        )
        return await cursor.fetchone()


async def update_payment_status(payment_id: int, status: str):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
        await db.commit()


async def get_pending_payments(offset: int = 0, limit: int = 10):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT p.id, p.client_id, p.plan, p.amount, c.full_name, c.username
               FROM payments p
               JOIN clients c ON p.client_id = c.id
               WHERE p.status = 'waiting'
               ORDER BY p.id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        return await cursor.fetchall()


async def count_pending_payments() -> int:
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM payments WHERE status = 'waiting'")
        row = await cursor.fetchone()
        return row[0] if row else 0


# ==================== ALOQA XABARLARI ====================

async def save_contact_message(user_id: int, username: str, full_name: str, text: str):
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        await db.execute(
            """INSERT INTO contact_messages (user_id, username, full_name, text)
               VALUES (?, ?, ?, ?)""",
            (user_id, username, full_name, text),
        )
        await db.commit()
