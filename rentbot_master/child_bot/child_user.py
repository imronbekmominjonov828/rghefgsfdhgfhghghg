"""
CHILD BOT — MIJOZ (oddiy foydalanuvchi) qismi.

Asosiy menyu — PASTKI (Reply) klaviatura, doimiy ko'rinadi:
  🛍 Katalog        🛒 Korzinka
  📦 Buyurtmalarim  🔍 Qidirish
  💰 Keshbek        👥 Do'stlarni taklif qilish
  🏆 TOP 10         🚚 Yetkazib berish narxi
  📖 Qo'llanma      📞 Admin bilan aloqa
  🛠 Admin panel (faqat adminlarga)

Ichki ro'yxatlar (kategoriya, mahsulot, savat tarkibi) — INLINE, chunki bular
ID-asosli dinamik ro'yxatlar.

Lokatsiya va telefon so'rash — Telegram API cheklovi sababli faqat pastki
(Reply) tugma orqali so'raladi, bu allaqachon shunday edi.
"""
import math
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
)
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from . import child_db as db
from .child_states import (
    ASK_NAME, ASK_PHONE, ORDER_LOCATION, CONTACT_MESSAGE, SEARCH_QUERY,
    DELIVERY_CALC_LOCATION,
)

PAGE_SIZE = 10
REFERRAL_CASHBACK = 1500

BTN_KATALOG = "🛍 Katalog"
BTN_KORZINKA = "🛒 Korzinka"
BTN_ORDERS = "📦 Buyurtmalarim"
BTN_SEARCH = "🔍 Qidirish"
BTN_KESHBEK = "💰 Keshbek"
BTN_INVITE = "👥 Do'stlarni taklif qilish"
BTN_TOP10 = "🏆 TOP 10"
BTN_DELIVERY = "🚚 Yetkazib berish narxi"
BTN_GUIDE = "📖 Qo'llanma"
BTN_CONTACT = "📞 Admin bilan aloqa"
BTN_ADMIN_PANEL = "🛠 Admin panel"
BTN_CANCEL = "⬅️ Bekor qilish"


def fmt_money(amount) -> str:
    return f"{amount:,.0f}".replace(",", " ") + " so'm"


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def main_menu_keyboard(user_id: int):
    """Asosiy menyu - pastki (Reply) klaviatura. Admin bo'lsa qo'shimcha tugma ko'rinadi."""
    rows = [
        [BTN_KATALOG, BTN_KORZINKA],
        [BTN_ORDERS, BTN_SEARCH],
        [BTN_KESHBEK, BTN_INVITE],
        [BTN_TOP10, BTN_DELIVERY],
        [BTN_GUIDE, BTN_CONTACT],
    ]
    if await db.is_any_admin(user_id):
        rows.append([BTN_ADMIN_PANEL])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def _send_main_menu(message, user_id, text="Asosiy menu:"):
    await message.reply_text(text, reply_markup=await main_menu_keyboard(user_id))


# ==================== /start ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None

    if context.args:
        arg = context.args[0]
        if arg.startswith("ref"):
            try:
                referred_by = int(arg.replace("ref", ""))
            except ValueError:
                referred_by = None
            if referred_by == user.id:
                referred_by = None

    existing = await db.get_customer(user.id)
    is_new = existing is None

    await db.upsert_customer(user.id, user.full_name or "", user.username or "", referred_by if is_new else None)

    if is_new:
        await update.message.reply_text("Ismingizni kiriting:")
        return ASK_NAME

    await _send_main_menu(update.message, user.id, f"Xush kelibsiz, {user.full_name}!")
    return ConversationHandler.END


async def ask_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["onboard_name"] = name
    await update.message.reply_text("📞 Telefon raqamingizni yuboring:")
    return ASK_PHONE


async def ask_phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone = update.message.contact.phone_number if update.message.contact else update.message.text.strip()
    await db.set_customer_phone(user.id, phone)

    customer = await db.get_customer(user.id)
    referred_by = customer[4] if customer else None

    if referred_by:
        await db.add_cashback(referred_by, REFERRAL_CASHBACK, "referral")
        try:
            await context.bot.send_message(
                chat_id=referred_by,
                text=f"🎉 Sizning havolangiz orqali yangi do'st qo'shildi! "
                     f"+{fmt_money(REFERRAL_CASHBACK)} keshbek hisobingizga qo'shildi.",
            )
        except Exception:
            pass

    name = context.user_data.pop("onboard_name", user.full_name)
    await _send_main_menu(update.message, user.id, f"Xush kelibsiz, {name}!")
    return ConversationHandler.END


# ==================== KATALOG ====================

async def menu_katalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = await db.get_categories()
    if not categories:
        await update.message.reply_text("Hozircha katalog mavjud emas.")
        return
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"cat_open:{cid}:0")]
        for cid, name in categories
    ]
    await update.message.reply_text("🛍 Katalog:", reply_markup=InlineKeyboardMarkup(keyboard))


async def cat_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category_id, offset = query.data.split(":")
    category_id, offset = int(category_id), int(offset)

    products = await db.get_products_by_category(category_id, offset, PAGE_SIZE, active_only=True)
    total = await db.count_products_by_category(category_id, active_only=True)

    if not products:
        await query.message.reply_text("Bu katalogda hozircha mahsulot yo'q.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{name} — {fmt_money(price)}/{unit}", callback_data=f"prod_view:{pid}")]
        for pid, name, unit, price, _photo in products
    ]
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"cat_open:{category_id}:{max(0, offset-PAGE_SIZE)}"))
    if offset + PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"cat_open:{category_id}:{offset+PAGE_SIZE}"))
    if nav_row:
        keyboard.append(nav_row)

    await query.message.reply_text(f"📦 Mahsulotlar ({total} ta):", reply_markup=InlineKeyboardMarkup(keyboard))


async def prod_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    product = await db.get_product(product_id)
    if not product or not product[7]:
        await query.message.reply_text("Mahsulot mavjud emas.")
        return
    _id, category_id, name, unit, buy_price, sell_price, photo_file_id, is_active, created_by = product

    caption = f"🛒 <b>{name}</b>\n💰 {fmt_money(sell_price)} / {unit}"
    keyboard = [[InlineKeyboardButton("➕ Savatga qo'shish", callback_data=f"cart_add:{product_id}")]]

    if photo_file_id:
        await query.message.reply_photo(
            photo=photo_file_id, caption=caption, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.message.reply_text(caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def cart_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Savatga qo'shildi ✅")
    product_id = int(query.data.split(":")[1])
    await db.add_to_cart(update.effective_user.id, product_id, quantity=1)


# ==================== KORZINKA (SAVAT) ====================

async def menu_korzinka(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_cart(update.message, update.effective_user.id)


async def show_cart(message, user_id):
    cart_rows = await db.get_cart(user_id)
    if not cart_rows:
        await message.reply_text("🛒 Savatingiz bo'sh.")
        return

    text = ""
    total = 0
    for _cid, _pid, name, unit, price, qty in cart_rows:
        line_total = price * qty
        total += line_total
        qty_str = f"{qty:g}"
        text += f"- {name} ({qty_str} {unit} × {fmt_money(price)} = {fmt_money(line_total)})\n"
    text += f"\n💰 Jami mahsulot: {fmt_money(total)}\n\nBuyurtma berish yoki boshqa amalni tanlang:"

    keyboard = [
        [InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout_start")],
        [InlineKeyboardButton("🗑 Savatni tozalash", callback_data="cart_clear")],
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def cart_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.clear_cart(update.effective_user.id)
    await query.message.reply_text("🗑 Savat tozalandi.")


# ==================== BUYURTMA BERISH ====================
# Eslatma: lokatsiya va telefon so'rash Telegram API cheklovi sababli faqat
# pastki (Reply) tugma orqali so'raladi — inline tugma orqali bu ikkisini
# so'rash texnik jihatdan mumkin emas.

async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    cart_rows = await db.get_cart(user_id)
    if not cart_rows:
        await query.message.reply_text("🛒 Savatingiz bo'sh.")
        return ConversationHandler.END

    # Agar foydalanuvchi avval "Yetkazib berish narxi" tugmasi orqali lokatsiyasini
    # yuborgan va narx hisoblangan bo'lsa - qayta so'ramaymiz, keshdan foydalanamiz.
    if "order_location" in context.user_data and "cached_delivery_price" in context.user_data:
        customer = await db.get_customer(user_id)
        if customer and customer[3]:
            return await _finalize_order(update, context, customer[3])
        contact_btn = KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)
        await query.message.reply_text(
            "📞 Telefon raqamingizni yuboring:",
            reply_markup=ReplyKeyboardMarkup([[contact_btn], [BTN_CANCEL]], resize_keyboard=True),
        )
        return ASK_PHONE

    location_btn = KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)
    await query.message.reply_text(
        "Buyurtmani yakunlash uchun lokatsiyangizni yuboring:",
        reply_markup=ReplyKeyboardMarkup([[location_btn], [BTN_CANCEL]], resize_keyboard=True),
    )
    return ORDER_LOCATION


async def checkout_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        await update.message.reply_text("⚠️ Iltimos, \"📍 Lokatsiyani yuborish\" tugmasini bosing.")
        return ORDER_LOCATION

    lat = update.message.location.latitude
    lon = update.message.location.longitude

    settings = await db.get_settings()
    price_per_km = settings[0] if settings else 0
    shop_lat, shop_lon = (settings[1], settings[2]) if settings else (None, None)

    distance_km = None
    delivery_price = 0
    if shop_lat is not None and shop_lon is not None:
        distance_km = round(haversine_km(shop_lat, shop_lon, lat, lon), 1)
        delivery_price = round(distance_km * price_per_km)

    context.user_data["order_location"] = (lat, lon, distance_km)
    context.user_data["cached_delivery_price"] = delivery_price

    await update.message.reply_location(latitude=lat, longitude=lon)
    distance_text = f"{distance_km} km" if distance_km is not None else "—"
    await update.message.reply_text(
        f"🧭 Masofa: {distance_text}\n"
        f"🚚 Yetkazib berish narxi: {fmt_money(delivery_price)}",
        reply_markup=ReplyKeyboardRemove(),
    )

    customer = await db.get_customer(update.effective_user.id)
    if customer and customer[3]:  # telefon allaqachon bor
        return await _finalize_order(update, context, customer[3])

    contact_btn = KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)
    await update.message.reply_text(
        "📞 Telefon raqamingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup([[contact_btn], [BTN_CANCEL]], resize_keyboard=True),
    )
    return ASK_PHONE


async def checkout_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number if update.message.contact else update.message.text.strip()
    await db.set_customer_phone(update.effective_user.id, phone)
    return await _finalize_order(update, context, phone)


async def _finalize_order(update, context, phone):
    user = update.effective_user
    cart_rows = await db.get_cart(user.id)
    if not cart_rows:
        await update.message.reply_text("🛒 Savat bo'sh qoldi.", reply_markup=ReplyKeyboardRemove())
        await _send_main_menu(update.message, user.id)
        return ConversationHandler.END

    items_total = sum(price * qty for _c, _p, _n, _u, price, qty in cart_rows)
    delivery_price = context.user_data.pop("cached_delivery_price", 0)

    lat, lon, distance_km = context.user_data.pop("order_location", (None, None, None))
    customer = await db.get_customer(user.id)
    customer_name = customer[1] if customer else user.full_name

    order_id = await db.create_order(
        user_id=user.id, customer_name=customer_name, customer_phone=phone,
        lat=lat, lon=lon, distance_km=distance_km,
        items_total=items_total, delivery_price=delivery_price, cart_rows=cart_rows,
    )

    cashback_amount = int(items_total * 0.01)
    if cashback_amount > 0:
        await db.add_cashback(user.id, cashback_amount, "purchase")

    await db.clear_cart(user.id)

    grand_total = items_total + delivery_price
    await update.message.reply_text(
        f"✅ Buyurtmangiz qabul qilindi! (#{order_id})\n"
        f"💰 Jami: {fmt_money(grand_total)}\n\n"
        f"Tez orada admin siz bilan bog'lanadi.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await _send_main_menu(update.message, user.id)

    admins = await db.get_all_admins()
    items_text = "\n".join(f"  • {name} x{qty:g}" for _c, _p, name, unit, price, qty in cart_rows)

    location_line = ""
    if lat is not None and lon is not None:
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
        location_line = f"📍 Lokatsiya: {maps_link}\n"
        if distance_km is not None:
            location_line += f"🧭 Masofa: {distance_km} km\n"

    notify_text = (
        f"🆕 <b>Yangi buyurtma #{order_id}</b>\n\n"
        f"👤 Ism: {customer_name}\n"
        f"📞 Telefon: {phone}\n"
        f"{location_line}\n"
        f"{items_text}\n\n"
        f"Mahsulotlar: {fmt_money(items_total)}\n"
        f"Yetkazib berish: {fmt_money(delivery_price)}\n"
        f"<b>Jami: {fmt_money(grand_total)}</b>"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 Qabul qilish", callback_data=f"ad_order_accept:{order_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"ad_order_reject:{order_id}"),
    ]])
    for user_id, _name, _username, _level in admins:
        try:
            await context.bot.send_message(
                chat_id=user_id, text=notify_text, parse_mode="HTML", reply_markup=keyboard
            )
        except Exception:
            pass

    return ConversationHandler.END


async def checkout_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("order_location", None)
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    await _send_main_menu(update.message, update.effective_user.id)
    return ConversationHandler.END


# ==================== BUYURTMALARIM ====================

async def menu_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders = await db.get_user_orders(user_id, 0, PAGE_SIZE)
    if not orders:
        await update.message.reply_text("📭 Siz hali hech qanday yetkazilgan buyurtma olmadingiz.")
        return
    status_emoji = {"new": "🆕", "accepted": "👍", "delivered": "✅", "rejected": "❌"}
    text = "📦 Buyurtmalaringiz:\n\n"
    for order_id, grand_total, status, created_at in orders:
        emoji = status_emoji.get(status, "🆕")
        text += f"{emoji} #{order_id} — {fmt_money(grand_total)} — {created_at[:16]}\n"
    await update.message.reply_text(text)


# ==================== QIDIRISH ====================

async def menu_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Qidiruvni boshlash uchun mahsulot nomini kiriting:")
    return SEARCH_QUERY


async def search_query_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    results = await db.search_products(text, 0, PAGE_SIZE)
    total = await db.count_search_products(text)

    if not results:
        await update.message.reply_text(f"\"{text}\" bo'yicha hech narsa topilmadi.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(f"{name} — {fmt_money(price)}", callback_data=f"prod_view:{pid}")]
        for pid, name, price in results
    ]
    await update.message.reply_text(
        f"🔍 \"{text}\" bo'yicha natijalar ({total} ta):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


# ==================== KESHBEK / REFERAL / TOP10 / YETKAZISH / QO'LLANMA / ALOQA ====================

async def menu_keshbek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    referral_total, purchase_total = await db.get_cashback_breakdown(user_id)
    ref_count = await db.count_referrals(user_id)
    total = referral_total + purchase_total

    await update.message.reply_text(
        f"💰 Sizning keshbek balansingiz:\n\n"
        f"🤝 Do'stlar orqali: {fmt_money(referral_total)} ({ref_count} do'st)\n"
        f"🛒 Xaridlar orqali: {fmt_money(purchase_total)}\n"
        f"💳 Jami: {fmt_money(total)}"
    )


async def menu_invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = context.bot.username
    ref_count = await db.count_referrals(user_id)
    referral_total, _ = await db.get_cashback_breakdown(user_id)

    link = f"https://t.me/{bot_username}?start=ref{user_id}"
    await update.message.reply_text(
        f"👥 Do'stlaringizni taklif qilish uchun quyidagi havolani ulashing:\n{link}\n\n"
        f"📊 Siz hozircha {ref_count} do'st taklif qilgansiz.\n"
        f"💰 Shu do'stlaringiz uchun keshbek: {fmt_money(referral_total)}.\n\n"
        f"✅ Har bir do'st obuna bo'lsa, sizga {fmt_money(REFERRAL_CASHBACK)} keshbek beriladi!"
    )


async def menu_top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = await db.get_top_referrers(10)
    if not top:
        await update.message.reply_text("🏆 TOP 10 ro'yxati hali bo'sh.")
        return
    text = "🏆 TOP 10 foydalanuvchilar:\n\n"
    for i, (user_id, full_name, ref_count, cb) in enumerate(top, start=1):
        text += f"{i}. {full_name or user_id} — {ref_count} do'st — 💰 {fmt_money(cb)} keshbek\n"
    await update.message.reply_text(text)


async def menu_delivery_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'Yetkazib berish narxi' tugmasi - lokatsiya so'raydi, km*narx hisoblaydi va keshlaydi."""
    settings = await db.get_settings()
    price_per_km = settings[0] if settings else 0
    shop_lat, shop_lon = (settings[1], settings[2]) if settings else (None, None)

    if not shop_lat or not shop_lon:
        await update.message.reply_text(
            "⚠️ Do'kon lokatsiyasi hali sozlanmagan, narxni hisoblab bo'lmaydi. "
            "Admin bilan bog'laning."
        )
        return ConversationHandler.END

    location_btn = KeyboardButton("📍 Mening lokatsiyam", request_location=True)
    await update.message.reply_text(
        f"🚚 Yetkazib berish narxi: {fmt_money(price_per_km)} / km\n\n"
        f"Aniq narxni bilish uchun lokatsiyangizni yuboring:",
        reply_markup=ReplyKeyboardMarkup([[location_btn], [BTN_CANCEL]], resize_keyboard=True),
    )
    return DELIVERY_CALC_LOCATION


async def delivery_calc_location_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        await update.message.reply_text("⚠️ Iltimos, \"📍 Mening lokatsiyam\" tugmasini bosing.")
        return DELIVERY_CALC_LOCATION

    lat = update.message.location.latitude
    lon = update.message.location.longitude

    settings = await db.get_settings()
    price_per_km = settings[0] if settings else 0
    shop_lat, shop_lon = (settings[1], settings[2]) if settings else (None, None)

    distance_km = round(haversine_km(shop_lat, shop_lon, lat, lon), 1)
    delivery_price = round(distance_km * price_per_km)

    context.user_data["order_location"] = (lat, lon, distance_km)
    context.user_data["cached_delivery_price"] = delivery_price

    await update.message.reply_text(
        f"🧭 Masofa: {distance_km} km\n"
        f"🚚 Yetkazib berish narxi: {fmt_money(delivery_price)}\n\n"
        f"Bu narx savatingizga buyurtma berishda avtomatik qo'llaniladi.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await _send_main_menu(update.message, update.effective_user.id)
    return ConversationHandler.END


async def delivery_calc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    await _send_main_menu(update.message, update.effective_user.id)
    return ConversationHandler.END


async def menu_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = await db.get_settings()
    guide = settings[4] if settings and settings[4] else None
    text = f"📖 {guide}" if guide else "📖 Qo'llanma hali mavjud emas."
    await update.message.reply_text(text)


# ==================== ADMIN BILAN ALOQA ====================

async def menu_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = await db.get_settings()
    username = settings[5] if settings and settings[5] else None
    text = "📞 Admin bilan bog'lanish uchun xabaringizni yozing."
    if username:
        text += f"\nAdmin: @{username}"
    await update.message.reply_text(text)
    await update.message.reply_text("✍️ Xabaringizni yuboring:")
    return CONTACT_MESSAGE


async def contact_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    admins = await db.get_all_admins()
    notify_text = f"✉️ Yangi xabar\n👤 {user.full_name} (@{user.username or '-'})\n🆔 {user.id}\n\n💬 {text}"
    for user_id, _name, _username, _level in admins:
        try:
            await context.bot.send_message(chat_id=user_id, text=notify_text)
        except Exception:
            pass
    await _send_main_menu(update.message, user.id, "✅ Xabaringiz adminga yetkazildi.")
    return ConversationHandler.END


async def contact_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_main_menu(update.message, update.effective_user.id, "❌ Bekor qilindi.")
    return ConversationHandler.END


# ==================== RO'YXATDAN O'TKAZISH ====================

def register_child_user_handlers(app):
    onboarding_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name_received)],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, ask_phone_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone_received),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(onboarding_conv)

    # --- Asosiy menyu (Reply Keyboard) tugmalari ---
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_KATALOG}$"), menu_katalog))
    app.add_handler(CallbackQueryHandler(cat_open, pattern="^cat_open:"))
    app.add_handler(CallbackQueryHandler(prod_view, pattern="^prod_view:"))
    app.add_handler(CallbackQueryHandler(cart_add, pattern="^cart_add:"))

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_KORZINKA}$"), menu_korzinka))
    app.add_handler(CallbackQueryHandler(cart_clear, pattern="^cart_clear$"))

    checkout_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(checkout_start, pattern="^checkout_start$")],
        states={
            ORDER_LOCATION: [
                MessageHandler(filters.LOCATION, checkout_location),
                MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), checkout_cancel),
            ],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, checkout_phone),
                MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), checkout_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_phone),
            ],
        },
        fallbacks=[CommandHandler("cancel", checkout_cancel)],
    )
    app.add_handler(checkout_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_ORDERS}$"), menu_my_orders))

    search_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_SEARCH}$"), menu_search_start)],
        states={SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query_received)]},
        fallbacks=[CommandHandler("cancel", checkout_cancel)],
    )
    app.add_handler(search_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_KESHBEK}$"), menu_keshbek))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_INVITE}$"), menu_invite_friends))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_TOP10}$"), menu_top10))

    delivery_calc_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_DELIVERY}$"), menu_delivery_price)],
        states={
            DELIVERY_CALC_LOCATION: [
                MessageHandler(filters.LOCATION, delivery_calc_location_received),
                MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), delivery_calc_cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel", delivery_calc_cancel)],
    )
    app.add_handler(delivery_calc_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_GUIDE}$"), menu_guide))

    contact_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_CONTACT}$"), menu_contact_admin)],
        states={CONTACT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_message_received)]},
        fallbacks=[CommandHandler("cancel", contact_cancel)],
    )
    app.add_handler(contact_conv)
