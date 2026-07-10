"""
CHILD BOT DATABASE — har bir mijozning o'z botiga tegishli SQLite fayl.
set_db_path() orqali har bir child-bot o'ziga tegishli faylga ulanadi.

Jadvallar:
- shop_admins: 2 darajali adminlar (1=bot egasi/owner, 2=do'kon admin)
- categories: kategoriyalar (katalog)
- products: mahsulotlar (kategoriya, birlik turi, olish/sotish narxi, rasm)
- settings: do'kon sozlamalari (yetkazib berish narxi - qat'iy summa, karta va h.k.)
- cart_items: savat
- orders: buyurtmalar (lokatsiya, masofa, telefon, status)
- order_items: buyurtma tarkibi
- referrals: kim kimni taklif qilgani
- cashback_log: keshbek tarixi (referal yoki xarid orqali)
"""
import aiosqlite
from datetime import datetime

_DB_PATH = "child_default.db"


def set_db_path(path: str):
    global _DB_PATH
    _DB_PATH = path


def get_db_path() -> str:
    return _DB_PATH


async def init_child_db(path: str = None):
    db_path = path or _DB_PATH
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # 1-daraja = owner (botni sotib olgan), 2-daraja = do'kon admin (owner qo'shgan)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                username TEXT,
                level INTEGER NOT NULL DEFAULT 2,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                name TEXT NOT NULL,
                unit TEXT DEFAULT 'dona',
                buy_price INTEGER DEFAULT 0,
                sell_price INTEGER NOT NULL,
                photo_file_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                delivery_price_per_km INTEGER DEFAULT 0,
                shop_location_lat REAL,
                shop_location_lon REAL,
                card_number TEXT,
                guide_text TEXT,
                admin_contact_username TEXT
            )
        """)
        # Eski bazalarda delivery_price_per_km ustuni bo'lmasligi mumkin - xavfsiz migratsiya
        try:
            await db.execute("ALTER TABLE settings ADD COLUMN delivery_price_per_km INTEGER DEFAULT 0")
        except Exception:
            pass
        await db.execute(
            "INSERT OR IGNORE INTO settings (id, delivery_price_per_km) VALUES (1, 0)"
        )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity REAL DEFAULT 1,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                customer_name TEXT,
                customer_phone TEXT,
                location_lat REAL,
                location_lon REAL,
                distance_km REAL,
                items_total INTEGER NOT NULL,
                delivery_price INTEGER DEFAULT 0,
                grand_total INTEGER NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                unit TEXT,
                price INTEGER NOT NULL,
                quantity REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
            )
        """)

        # Foydalanuvchilar (mijozlar) profili - ism, telefon, referal
        await db.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                phone TEXT,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cashback_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


# ==================== SHOP ADMINS (2 daraja) ====================

async def get_admin(user_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, full_name, username, level, added_by FROM shop_admins WHERE user_id = ?",
            (user_id,),
        )
        return await cursor.fetchone()


async def is_owner(user_id: int) -> bool:
    admin = await get_admin(user_id)
    return bool(admin and admin[4] == 1)


async def is_any_admin(user_id: int) -> bool:
    admin = await get_admin(user_id)
    return admin is not None


async def add_owner(user_id: int, full_name: str, username: str):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """INSERT INTO shop_admins (user_id, full_name, username, level, added_by)
               VALUES (?, ?, ?, 1, NULL)
               ON CONFLICT(user_id) DO UPDATE SET level = 1""",
            (user_id, full_name, username),
        )
        await db.commit()


async def add_shop_admin(user_id: int, full_name: str, username: str, added_by: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """INSERT INTO shop_admins (user_id, full_name, username, level, added_by)
               VALUES (?, ?, ?, 2, ?)
               ON CONFLICT(user_id) DO UPDATE SET full_name = ?, username = ?""",
            (user_id, full_name, username, added_by, full_name, username),
        )
        await db.commit()


async def remove_admin(user_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM shop_admins WHERE user_id = ? AND level = 2", (user_id,))
        await db.commit()


async def get_all_admins():
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, full_name, username, level FROM shop_admins ORDER BY level, id"
        )
        return await cursor.fetchall()


# ==================== KATEGORIYALAR ====================

async def add_category(name: str) -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,)
        )
        await db.commit()
        return cursor.lastrowid


async def get_categories():
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM categories ORDER BY name")
        return await cursor.fetchall()


async def get_category(category_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM categories WHERE id = ?", (category_id,))
        return await cursor.fetchone()


async def rename_category(category_id: int, new_name: str):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, category_id))
        await db.commit()


async def delete_category(category_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE category_id = ?", (category_id,))
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()


async def count_products_in_category(category_id: int) -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM products WHERE category_id = ?", (category_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# ==================== MAHSULOTLAR ====================

async def add_product(category_id, name, unit, buy_price, sell_price, photo_file_id, created_by) -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO products (category_id, name, unit, buy_price, sell_price, photo_file_id, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (category_id, name, unit, buy_price, sell_price, photo_file_id, created_by),
        )
        await db.commit()
        return cursor.lastrowid


async def get_product(product_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, category_id, name, unit, buy_price, sell_price, photo_file_id, is_active, created_by
               FROM products WHERE id = ?""",
            (product_id,),
        )
        return await cursor.fetchone()


async def get_products_by_category(category_id: int, offset=0, limit=10, active_only=True):
    query = "SELECT id, name, unit, sell_price, photo_file_id FROM products WHERE category_id = ?"
    params = [category_id]
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()


async def count_products_by_category(category_id: int, active_only=True) -> int:
    query = "SELECT COUNT(*) FROM products WHERE category_id = ?"
    params = [category_id]
    if active_only:
        query += " AND is_active = 1"
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_all_products_admin(offset=0, limit=10):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT p.id, p.name, p.sell_price, p.is_active, c.name
               FROM products p LEFT JOIN categories c ON p.category_id = c.id
               ORDER BY p.id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        return await cursor.fetchall()


async def count_all_products() -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM products")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_product(product_id, **fields):
    allowed = {"name", "unit", "buy_price", "sell_price", "photo_file_id", "category_id"}
    set_clause = ", ".join(f"{k} = ?" for k in fields if k in allowed)
    values = [v for k, v in fields.items() if k in allowed]
    if not set_clause:
        return
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(f"UPDATE products SET {set_clause} WHERE id = ?", (*values, product_id))
        await db.commit()


async def toggle_product_active(product_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("UPDATE products SET is_active = 1 - is_active WHERE id = ?", (product_id,))
        await db.commit()


async def delete_product(product_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()


async def search_products(query: str, offset=0, limit=10):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, name, sell_price FROM products
               WHERE is_active = 1 AND name LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?""",
            (f"%{query}%", limit, offset),
        )
        return await cursor.fetchall()


async def count_search_products(query: str) -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM products WHERE is_active = 1 AND name LIKE ?", (f"%{query}%",)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# ==================== SOZLAMALAR ====================

async def get_settings():
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT delivery_price_per_km, shop_location_lat, shop_location_lon,
                      card_number, guide_text, admin_contact_username
               FROM settings WHERE id = 1"""
        )
        return await cursor.fetchone()


async def update_settings(**fields):
    allowed = {
        "delivery_price_per_km", "shop_location_lat", "shop_location_lon",
        "card_number", "guide_text", "admin_contact_username",
    }
    set_clause = ", ".join(f"{k} = ?" for k in fields if k in allowed)
    values = [v for k, v in fields.items() if k in allowed]
    if not set_clause:
        return
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(f"UPDATE settings SET {set_clause} WHERE id = 1", values)
        await db.commit()


# ==================== MIJOZLAR (customers) ====================

async def upsert_customer(user_id, full_name, username, referred_by=None):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM customers WHERE user_id = ?", (user_id,))
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                "UPDATE customers SET full_name = ?, username = ? WHERE user_id = ?",
                (full_name, username, user_id),
            )
        else:
            await db.execute(
                """INSERT INTO customers (user_id, full_name, username, referred_by)
                   VALUES (?, ?, ?, ?)""",
                (user_id, full_name, username, referred_by),
            )
        await db.commit()


async def get_customer(user_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, full_name, username, phone, referred_by FROM customers WHERE user_id = ?",
            (user_id,),
        )
        return await cursor.fetchone()


async def set_customer_phone(user_id: int, phone: str):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("UPDATE customers SET phone = ? WHERE user_id = ?", (phone, user_id))
        await db.commit()


async def count_referrals(user_id: int) -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM customers WHERE referred_by = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# ==================== SAVAT ====================

async def add_to_cart(user_id: int, product_id: int, quantity: float = 1):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE cart_items SET quantity = quantity + ? WHERE id = ?", (quantity, row[0])
            )
        else:
            await db.execute(
                "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user_id, product_id, quantity),
            )
        await db.commit()


async def get_cart(user_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT ci.id, p.id, p.name, p.unit, p.sell_price, ci.quantity
               FROM cart_items ci JOIN products p ON ci.product_id = p.id
               WHERE ci.user_id = ? ORDER BY ci.id""",
            (user_id,),
        )
        return await cursor.fetchall()


async def clear_cart(user_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()


async def remove_cart_item(cart_item_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM cart_items WHERE id = ?", (cart_item_id,))
        await db.commit()


# ==================== BUYURTMALAR ====================

async def create_order(user_id, customer_name, customer_phone, lat, lon, distance_km,
                        items_total, delivery_price, cart_rows):
    grand_total = items_total + delivery_price
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO orders (user_id, customer_name, customer_phone, location_lat, location_lon,
                                    distance_km, items_total, delivery_price, grand_total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, customer_name, customer_phone, lat, lon, distance_km,
             items_total, delivery_price, grand_total),
        )
        order_id = cursor.lastrowid
        for _cid, _pid, name, unit, price, qty in cart_rows:
            await db.execute(
                """INSERT INTO order_items (order_id, product_name, unit, price, quantity)
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, name, unit, price, qty),
            )
        await db.commit()
        return order_id


async def get_order(order_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, customer_name, customer_phone, location_lat, location_lon,
                      distance_km, items_total, delivery_price, grand_total, status, created_at
               FROM orders WHERE id = ?""",
            (order_id,),
        )
        return await cursor.fetchone()


async def get_order_items(order_id: int):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT product_name, unit, price, quantity FROM order_items WHERE order_id = ?",
            (order_id,),
        )
        return await cursor.fetchall()


async def get_orders_admin(offset=0, limit=10, status=None):
    query = "SELECT id, customer_name, grand_total, status, created_at FROM orders"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()


async def count_orders_admin(status=None) -> int:
    query = "SELECT COUNT(*) FROM orders"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_user_orders(user_id: int, offset=0, limit=10):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, grand_total, status, created_at FROM orders
               WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        )
        return await cursor.fetchall()


async def count_user_orders(user_id: int) -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_order_status(order_id: int, status: str):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()


# ==================== KESHBEK / REFERAL ====================

async def add_cashback(user_id: int, amount: int, reason: str):
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT INTO cashback_log (user_id, amount, reason) VALUES (?, ?, ?)",
            (user_id, amount, reason),
        )
        await db.commit()


async def get_cashback_balance(user_id: int) -> int:
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM cashback_log WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_cashback_breakdown(user_id: int):
    """(referal orqali jami, xaridlar orqali jami) qaytaradi."""
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT COALESCE(SUM(amount), 0) FROM cashback_log
               WHERE user_id = ? AND reason = 'referral'""",
            (user_id,),
        )
        referral_total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COALESCE(SUM(amount), 0) FROM cashback_log
               WHERE user_id = ? AND reason = 'purchase'""",
            (user_id,),
        )
        purchase_total = (await cursor.fetchone())[0]
        return referral_total, purchase_total


async def get_top_referrers(limit: int = 10):
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """SELECT c.user_id, c.full_name, COUNT(r.user_id) as ref_count,
                      COALESCE((SELECT SUM(amount) FROM cashback_log cl
                                WHERE cl.user_id = c.user_id AND cl.reason = 'referral'), 0) as cb
               FROM customers c
               LEFT JOIN customers r ON r.referred_by = c.user_id
               GROUP BY c.user_id
               ORDER BY ref_count DESC, cb DESC
               LIMIT ?""",
            (limit,),
        )
        return await cursor.fetchall()
