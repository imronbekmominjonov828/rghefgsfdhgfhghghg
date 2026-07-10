"""
CHILD BOT — BIRLASHTIRILGAN ADMIN PANEL.

Bitta "Admin panel" — ham 1-daraja (owner, botni sotib olgan kishi),
ham 2-daraja (owner qo'shgan do'kon admin) shu yerga kiradi.

Hammaga ochiq bo'limlar (1 va 2-daraja):
- Katalog (kategoriya) qo'shish/tahrirlash
- Mahsulot qo'shish/ro'yxat
- Buyurtmalar

Faqat OWNER (1-daraja) ko'radigan bo'limlar:
- Do'kon admin qo'shish/o'chirish
- Yetkazib berish narxi (km/so'm)
- Do'kon lokatsiyasi
- Karta raqami
- Qo'llanma matni
- Aloqa uchun username

Admin panelga kirish: oddiy foydalanuvchi /start qilganda, agar u admin bo'lsa,
asosiy menyuda "🛠 Admin panel" tugmasi qo'shiladi (faqat adminlarga ko'rinadi,
komanda orqali emas).
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from . import child_db as db
from .child_states import (
    ADD_ADMIN_ID,
    CAT_ADD_NAME, CAT_RENAME,
    PROD_CATEGORY, PROD_NAME, PROD_UNIT, PROD_BUY_PRICE, PROD_SELL_PRICE, PROD_PHOTO,
    SET_DELIVERY_PRICE_PER_KM, SET_CARD_NUMBER, SET_GUIDE_TEXT,
    SET_ADMIN_CONTACT, SET_SHOP_LOCATION,
)
from .child_user import BTN_ADMIN_PANEL

PAGE_SIZE = 10

BTN_ADD_CATEGORY = "🏷 Katalog qo'shish"
BTN_EDIT_CATEGORIES = "✏️ Katalogni tahrirlash"
BTN_ADD_PRODUCT = "➕ Mahsulot qo'shish"
BTN_PRODUCTS_LIST = "📦 Mahsulotlar ro'yxati"
BTN_ORDERS = "🧾 Buyurtmalar"
BTN_ADD_SHOP_ADMIN = "👤 Do'kon admin qo'shish"
BTN_ADMINS_LIST = "👥 Adminlar ro'yxati"
BTN_SET_DELIVERY = "🚚 Yetkazib berish narxi (km/so'm)"
BTN_SET_LOCATION = "📍 Do'kon lokatsiyasi"
BTN_SET_CARD = "💳 Karta raqami"
BTN_SET_GUIDE = "📖 Qo'llanma matni"
BTN_SET_CONTACT = "📞 Aloqa uchun username"
BTN_BACK_MAIN = "⬅️ Asosiy menyu"


def fmt_money(amount) -> str:
    return f"{amount:,.0f}".replace(",", " ") + " so'm"


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await db.is_any_admin(user_id):
            if update.message:
                await update.message.reply_text("Sizda admin huquqi yo'q.")
            return
        return await func(update, context)
    return wrapper


def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await db.is_owner(user_id):
            if update.message:
                await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
            return
        return await func(update, context)
    return wrapper


def _admin_panel_keyboard(is_owner: bool):
    rows = [
        [BTN_ADD_CATEGORY, BTN_EDIT_CATEGORIES],
        [BTN_ADD_PRODUCT, BTN_PRODUCTS_LIST],
        [BTN_ORDERS],
    ]
    if is_owner:
        rows.append([BTN_ADD_SHOP_ADMIN, BTN_ADMINS_LIST])
        rows.append([BTN_SET_DELIVERY])
        rows.append([BTN_SET_LOCATION, BTN_SET_CARD])
        rows.append([BTN_SET_GUIDE, BTN_SET_CONTACT])
    rows.append([BTN_BACK_MAIN])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


# ==================== ADMIN PANEL (asosiy kirish nuqtasi) ====================

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin komandasi orqali (eskidan qolgan, ixtiyoriy) yoki to'g'ridan-to'g'ri chaqirilishi mumkin."""
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text("🛠 Admin panel:", reply_markup=_admin_panel_keyboard(is_owner))


async def open_admin_panel_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asosiy menyudagi '🛠 Admin panel' tugmasi bosilganda chaqiriladi (reply-keyboard tugmasi)."""
    user_id = update.effective_user.id
    if not await db.is_any_admin(user_id):
        await update.message.reply_text("Sizda admin huquqi yo'q.")
        return
    is_owner = await db.is_owner(user_id)
    await update.message.reply_text("🛠 Admin panel:", reply_markup=_admin_panel_keyboard(is_owner))


async def ad_back_panel_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel ichida '⬅️ Asosiy menyu' bosilganda - mijoz asosiy menyusiga qaytaradi."""
    from .child_user import main_menu_keyboard
    await update.message.reply_text(
        "Asosiy menyu:", reply_markup=await main_menu_keyboard(update.effective_user.id)
    )


# ==================== KATALOG (KATEGORIYA) ====================

async def ad_add_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_any_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "Yangi katalog nomini kiriting:", reply_markup=ReplyKeyboardRemove()
    )
    return CAT_ADD_NAME


async def ad_add_category_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    await db.add_category(name)
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text(
        f"✅ \"{name}\" katalogi qo'shildi.", reply_markup=_admin_panel_keyboard(is_owner)
    )
    return ConversationHandler.END


async def ad_edit_categories_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = await db.get_categories()
    if not categories:
        await update.message.reply_text("Bu kategoriya bo'sh.")
        return
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"ad_cat_detail:{cid}")]
        for cid, name in categories
    ]
    await update.message.reply_text("📝 Katalogni tahrirlash:", reply_markup=InlineKeyboardMarkup(keyboard))


async def ad_cat_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_id = int(query.data.split(":")[1])
    category = await db.get_category(category_id)
    if not category:
        await query.message.reply_text("Topilmadi.")
        return
    count = await db.count_products_in_category(category_id)
    keyboard = [
        [InlineKeyboardButton("✏️ Nomini o'zgartirish", callback_data=f"ad_cat_rename:{category_id}")],
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"ad_cat_delete:{category_id}")],
    ]
    await query.message.reply_text(
        f"🏷 {category[1]}\n📦 Mahsulotlar soni: {count}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ad_cat_rename_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_id = int(query.data.split(":")[1])
    context.user_data["rename_cat_id"] = category_id
    await query.message.reply_text("Yangi nomni kiriting:")
    return CAT_RENAME


async def ad_cat_rename_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    category_id = context.user_data.pop("rename_cat_id")
    await db.rename_category(category_id, new_name)
    await update.message.reply_text(f"✅ Yangi nom: {new_name}")
    return ConversationHandler.END


async def ad_cat_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_id = int(query.data.split(":")[1])
    await db.delete_category(category_id)
    await query.edit_message_text("🗑 Katalog (va undagi mahsulotlar) o'chirildi.")


# ==================== MAHSULOT QO'SHISH ====================

async def ad_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_any_admin(update.effective_user.id):
        return ConversationHandler.END

    categories = await db.get_categories()
    if not categories:
        await update.message.reply_text("⚠️ Avval kamida 1 ta katalog qo'shing.")
        return ConversationHandler.END

    context.user_data["new_product"] = {}
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"pick_pcat:{cid}")]
        for cid, name in categories
    ]
    await update.message.reply_text(
        "Kategoriya tanlang:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PROD_CATEGORY


async def ad_product_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_id = int(query.data.split(":")[1])
    context.user_data["new_product"]["category_id"] = category_id
    await query.message.reply_text("Mahsulot nomini kiriting:")
    return PROD_NAME


async def ad_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["name"] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("Dona", callback_data="pick_unit:dona"),
                 InlineKeyboardButton("Kg", callback_data="pick_unit:kg")]]
    await update.message.reply_text(
        f"\"{context.user_data['new_product']['name']}\" uchun birlik turini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return PROD_UNIT


async def ad_product_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    unit = query.data.split(":")[1]
    context.user_data["new_product"]["unit"] = unit
    await query.message.reply_text("Olish narxini kiriting (so'mda):")
    return PROD_BUY_PRICE


async def ad_product_buy_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam yuboring.")
        return PROD_BUY_PRICE
    context.user_data["new_product"]["buy_price"] = int(text)
    await update.message.reply_text("Sotish narxini kiriting (so'mda):")
    return PROD_SELL_PRICE


async def ad_product_sell_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam yuboring.")
        return PROD_SELL_PRICE
    context.user_data["new_product"]["sell_price"] = int(text)
    await update.message.reply_text("Mahsulot rasmini yuboring (rasm sifatida):")
    return PROD_PHOTO


async def ad_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ Iltimos, rasm yuboring.")
        return PROD_PHOTO

    data = context.user_data.pop("new_product")
    file_id = update.message.photo[-1].file_id
    user_id = update.effective_user.id

    product_id = await db.add_product(
        category_id=data["category_id"], name=data["name"], unit=data["unit"],
        buy_price=data["buy_price"], sell_price=data["sell_price"],
        photo_file_id=file_id, created_by=user_id,
    )

    category = await db.get_category(data["category_id"])
    cat_name = category[1] if category else "?"

    await update.message.reply_photo(
        photo=file_id,
        caption=f"✅ {data['name']} ({data['unit']}) mahsuloti {cat_name} ga qo'shildi.",
    )
    is_owner = await db.is_owner(user_id)
    await update.message.reply_text("🛠 Admin panel:", reply_markup=_admin_panel_keyboard(is_owner))
    return ConversationHandler.END


async def ad_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=_admin_panel_keyboard(is_owner))
    return ConversationHandler.END


# ==================== MAHSULOTLAR RO'YXATI (admin) ====================

async def ad_products_list_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'📦 Mahsulotlar ro'yxati' matn tugmasi - 0-sahifadan boshlaydi."""
    await _show_products_list(update.message, 0)


async def ad_products_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sahifalash (⬅️/➡️) inline tugmalari orqali chaqiriladi."""
    query = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])
    await _show_products_list(query.message, offset, edit=False)


async def _show_products_list(message, offset, edit=False):
    products = await db.get_all_products_admin(offset, PAGE_SIZE)
    total = await db.count_all_products()

    if not products:
        await message.reply_text("Hozircha mahsulot yo'q.")
        return

    keyboard = []
    for pid, name, price, is_active, cat_name in products:
        status = "🟢" if is_active else "🔴"
        keyboard.append([
            InlineKeyboardButton(f"{status} {name} — {fmt_money(price)}", callback_data=f"ad_product_detail:{pid}")
        ])
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"ad_products_list:{max(0, offset-PAGE_SIZE)}"))
    if offset + PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"ad_products_list:{offset+PAGE_SIZE}"))
    if nav_row:
        keyboard.append(nav_row)

    await message.reply_text(f"📦 Mahsulotlar ({total} ta):", reply_markup=InlineKeyboardMarkup(keyboard))


async def ad_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    product = await db.get_product(product_id)
    if not product:
        await query.message.reply_text("Topilmadi.")
        return
    _id, category_id, name, unit, buy_price, sell_price, photo_file_id, is_active, created_by = product

    caption = (
        f"🛒 {name}\n"
        f"📏 Birlik: {unit}\n"
        f"💵 Olish narxi: {fmt_money(buy_price)}\n"
        f"💰 Sotish narxi: {fmt_money(sell_price)}\n"
        f"Holati: {'Faol ✅' if is_active else 'O‘chirilgan 🚫'}"
    )
    keyboard = [
        [InlineKeyboardButton(
            "🚫 Yashirish" if is_active else "✅ Faollashtirish",
            callback_data=f"ad_toggle_product:{product_id}",
        )],
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"ad_delete_product:{product_id}")],
    ]
    if photo_file_id:
        await query.message.reply_photo(photo=photo_file_id, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard))


async def ad_toggle_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    await db.toggle_product_active(product_id)
    await query.message.reply_text("✅ Holat o'zgartirildi.")


async def ad_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    await db.delete_product(product_id)
    await query.edit_message_text("🗑 Mahsulot o'chirildi.")


# ==================== BUYURTMALAR (admin) ====================

async def ad_orders_list_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'🧾 Buyurtmalar' matn tugmasi - 0-sahifadan boshlaydi."""
    await _show_orders_list(update.message, 0)


async def ad_orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sahifalash (⬅️/➡️) inline tugmalari orqali chaqiriladi."""
    query = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])
    await _show_orders_list(query.message, offset)


async def _show_orders_list(message, offset):
    orders = await db.get_orders_admin(offset, PAGE_SIZE)
    total = await db.count_orders_admin()

    if not orders:
        await message.reply_text("Hozircha buyurtmalar yo'q.")
        return

    status_emoji = {"new": "🆕", "accepted": "👍", "delivered": "✅", "rejected": "❌"}
    keyboard = []
    for order_id, customer_name, grand_total, status, created_at in orders:
        emoji = status_emoji.get(status, "🆕")
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} #{order_id} {customer_name} — {fmt_money(grand_total)}",
                callback_data=f"ad_order_detail:{order_id}",
            )
        ])
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"ad_orders:{max(0, offset-PAGE_SIZE)}"))
    if offset + PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"ad_orders:{offset+PAGE_SIZE}"))
    if nav_row:
        keyboard.append(nav_row)

    await message.reply_text(f"🧾 Buyurtmalar ({total} ta):", reply_markup=InlineKeyboardMarkup(keyboard))


async def ad_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await query.message.reply_text("Topilmadi.")
        return
    (_id, user_id, customer_name, customer_phone, lat, lon, distance_km,
     items_total, delivery_price, grand_total, status, created_at) = order
    items = await db.get_order_items(order_id)

    items_text = "\n".join(
        f"  • {name} ({unit}) x{qty} — {fmt_money(price*qty)}" for name, unit, price, qty in items
    )

    location_line = ""
    if lat and lon:
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
        location_line = f"📍 Lokatsiya: {maps_link}\n"
        if distance_km is not None:
            location_line += f"🧭 Masofa: {distance_km} km\n"

    text = (
        f"🧾 <b>Buyurtma #{order_id}</b>\n\n"
        f"👤 Ism: {customer_name}\n"
        f"📞 Telefon: {customer_phone}\n"
        f"{location_line}\n"
        f"{items_text}\n\n"
        f"Mahsulotlar: {fmt_money(items_total)}\n"
        f"Yetkazib berish: {fmt_money(delivery_price)}\n"
        f"<b>Jami: {fmt_money(grand_total)}</b>\n"
        f"Holat: {status}"
    )

    keyboard = []
    if status == "new":
        keyboard.append([
            InlineKeyboardButton("👍 Qabul qilish", callback_data=f"ad_order_accept:{order_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"ad_order_reject:{order_id}"),
        ])
    elif status == "accepted":
        keyboard.append([InlineKeyboardButton("✅ Yetkazildi", callback_data=f"ad_order_delivered:{order_id}")])

    await query.message.reply_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        disable_web_page_preview=True,
    )


async def ad_order_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order = await db.get_order(order_id)
    if order and order[4] and order[5]:
        await query.message.reply_location(latitude=order[4], longitude=order[5])
    else:
        await query.message.reply_text("Lokatsiya mavjud emas.")


async def ad_order_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    await db.update_order_status(order_id, "accepted")
    await query.message.reply_text("👍 Buyurtma qabul qilindi.")

    order = await db.get_order(order_id)
    if order:
        try:
            await context.bot.send_message(
                chat_id=order[1],
                text=f"👍 Buyurtmangiz #{order_id} qabul qilindi! Tez orada yetkaziladi.",
            )
        except Exception:
            pass


async def ad_order_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    await db.update_order_status(order_id, "rejected")
    await query.message.reply_text("❌ Buyurtma rad etildi.")

    order = await db.get_order(order_id)
    if order:
        try:
            await context.bot.send_message(
                chat_id=order[1],
                text=f"❌ Afsuski, buyurtmangiz #{order_id} rad etildi. Admin bilan bog'laning.",
            )
        except Exception:
            pass


async def ad_order_delivered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    await db.update_order_status(order_id, "delivered")
    await query.message.reply_text("✅ Buyurtma \"yetkazildi\" deb belgilandi.")

    order = await db.get_order(order_id)
    if order:
        try:
            await context.bot.send_message(
                chat_id=order[1],
                text=f"✅ Buyurtmangiz #{order_id} yetkazildi. Xaridingiz uchun rahmat!",
            )
        except Exception:
            pass


# ==================== OWNER-ONLY: DO'KON ADMIN BOSHQARUVI ====================

async def own_add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_owner(update.effective_user.id):
        await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Yangi do'kon adminining Telegram ID raqamini yuboring.\n"
        "(U kishi @userinfobot orqali o'z ID'sini bilib olishi mumkin)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADD_ADMIN_ID


async def own_add_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ Iltimos, faqat raqam (Telegram ID) yuboring.")
        return ADD_ADMIN_ID

    new_admin_id = int(text)
    owner_id = update.effective_user.id

    if await db.is_any_admin(new_admin_id):
        await update.message.reply_text("⚠️ Bu foydalanuvchi allaqachon admin.")
        return ConversationHandler.END

    await db.add_shop_admin(new_admin_id, full_name="", username="", added_by=owner_id)
    is_owner = await db.is_owner(owner_id)
    await update.message.reply_text(
        f"✅ Yangi do'kon admin qo'shildi (ID: {new_admin_id}).\n"
        f"U kishi botga /start yuborib, \"🛠 Admin panel\" tugmasi orqali boshqaruvdan foydalanishi mumkin.",
        reply_markup=_admin_panel_keyboard(is_owner),
    )

    try:
        await context.bot.send_message(
            chat_id=new_admin_id,
            text="✅ Sizni ushbu do'kon botida admin etib tayinlashdi!\n"
                 "/start yuboring, asosiy menyuda \"🛠 Admin panel\" tugmasi ko'rinadi.",
        )
    except Exception:
        pass

    return ConversationHandler.END


async def own_admins_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = await db.get_all_admins()
    if not admins:
        await update.message.reply_text("Hozircha adminlar yo'q.")
        return

    keyboard = []
    text = "👥 Adminlar:\n\n"
    for user_id, full_name, username, level in admins:
        level_text = "👑 Egasi" if level == 1 else "👤 Do'kon admin"
        text += f"{level_text} — {full_name or user_id} (@{username or '-'})\n"
        if level == 2:
            keyboard.append([
                InlineKeyboardButton(f"🗑 O'chirish: {full_name or user_id}", callback_data=f"own_remove_admin:{user_id}")
            ])

    if keyboard:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text)


async def own_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_user_id = int(query.data.split(":")[1])
    await db.remove_admin(admin_user_id)
    await query.message.reply_text("🗑 Admin o'chirildi.")


# ==================== OWNER-ONLY: YETKAZIB BERISH NARXI (km/so'm) ====================

async def own_set_delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_owner(update.effective_user.id):
        await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
        return ConversationHandler.END
    settings = await db.get_settings()
    current = settings[0] if settings else 0
    await update.message.reply_text(
        f"Joriy yetkazib berish narxi: {fmt_money(current)} / km\n\n"
        f"Yangi narxni 1 km uchun so'mda yuboring (faqat raqam, masalan: 2000):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_DELIVERY_PRICE_PER_KM


async def own_set_delivery_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam yuboring.")
        return SET_DELIVERY_PRICE_PER_KM
    await db.update_settings(delivery_price_per_km=int(text))
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text(
        f"✅ Yetkazib berish narxi {fmt_money(int(text))} / km qilib o'rnatildi.",
        reply_markup=_admin_panel_keyboard(is_owner),
    )
    return ConversationHandler.END


# ==================== OWNER-ONLY: DO'KON LOKATSIYASI ====================

async def own_set_location_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import KeyboardButton
    if not await db.is_owner(update.effective_user.id):
        await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
        return ConversationHandler.END
    location_btn = KeyboardButton("📍 Do'kon lokatsiyasini yuborish", request_location=True)
    await update.message.reply_text(
        "Do'koningiz joylashgan manzilni (lokatsiyani) yuboring. "
        "Bu mijozlardan masofani hisoblash uchun ishlatiladi:",
        reply_markup=ReplyKeyboardMarkup([[location_btn]], resize_keyboard=True),
    )
    return SET_SHOP_LOCATION


async def own_set_location_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        await update.message.reply_text("⚠️ Iltimos, lokatsiya tugmasini bosing.")
        return SET_SHOP_LOCATION
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    await db.update_settings(shop_location_lat=lat, shop_location_lon=lon)
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text(
        "✅ Do'kon lokatsiyasi saqlandi.", reply_markup=_admin_panel_keyboard(is_owner)
    )
    return ConversationHandler.END


# ==================== OWNER-ONLY: KARTA RAQAMI ====================

async def own_set_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_owner(update.effective_user.id):
        await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
        return ConversationHandler.END
    settings = await db.get_settings()
    current = settings[3] if settings and settings[3] else "— hali kiritilmagan"
    await update.message.reply_text(
        f"Joriy karta raqami: {current}\n\nYangi karta raqamini yuboring (masalan: 8600 1234 5678 9012):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_CARD_NUMBER


async def own_set_card_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card = update.message.text.strip()
    await db.update_settings(card_number=card)
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text(
        f"✅ Karta raqami saqlandi: {card}", reply_markup=_admin_panel_keyboard(is_owner)
    )
    return ConversationHandler.END


# ==================== OWNER-ONLY: QO'LLANMA MATNI ====================

async def own_set_guide_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_owner(update.effective_user.id):
        await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Yangi qo'llanma matnini yuboring (foydalanuvchilarga ko'rinadi):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_GUIDE_TEXT


async def own_set_guide_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await db.update_settings(guide_text=text)
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text(
        "✅ Qo'llanma matni saqlandi.", reply_markup=_admin_panel_keyboard(is_owner)
    )
    return ConversationHandler.END


# ==================== OWNER-ONLY: ALOQA USERNAME ====================

async def own_set_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_owner(update.effective_user.id):
        await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Admin bilan aloqa uchun ko'rsatiladigan username'ni yuboring (@ siz):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_ADMIN_CONTACT


async def own_set_contact_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().lstrip("@")
    await db.update_settings(admin_contact_username=username)
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text(
        f"✅ Aloqa username saqlandi: @{username}", reply_markup=_admin_panel_keyboard(is_owner)
    )
    return ConversationHandler.END


async def own_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    is_owner = await db.is_owner(update.effective_user.id)
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=_admin_panel_keyboard(is_owner))
    return ConversationHandler.END


# ==================== RO'YXATDAN O'TKAZISH ====================

def register_child_admin_handlers(app):
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_ADMIN_PANEL}$"), open_admin_panel_msg))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_BACK_MAIN}$"), ad_back_panel_msg))

    # --- Katalog ---
    add_cat_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_ADD_CATEGORY}$"), ad_add_category_start)],
        states={CAT_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_add_category_save)]},
        fallbacks=[CommandHandler("cancel", ad_cancel)],
    )
    app.add_handler(add_cat_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_EDIT_CATEGORIES}$"), ad_edit_categories_list))
    app.add_handler(CallbackQueryHandler(ad_cat_detail, pattern="^ad_cat_detail:"))

    rename_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_cat_rename_start, pattern="^ad_cat_rename:")],
        states={CAT_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_cat_rename_apply)]},
        fallbacks=[CommandHandler("cancel", ad_cancel)],
    )
    app.add_handler(rename_conv)
    app.add_handler(CallbackQueryHandler(ad_cat_delete, pattern="^ad_cat_delete:"))

    # --- Mahsulot ---
    add_product_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_ADD_PRODUCT}$"), ad_add_product_start)],
        states={
            PROD_CATEGORY: [CallbackQueryHandler(ad_product_category, pattern="^pick_pcat:")],
            PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_product_name)],
            PROD_UNIT: [CallbackQueryHandler(ad_product_unit, pattern="^pick_unit:")],
            PROD_BUY_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_product_buy_price)],
            PROD_SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_product_sell_price)],
            PROD_PHOTO: [MessageHandler(filters.PHOTO, ad_product_photo)],
        },
        fallbacks=[CommandHandler("cancel", ad_cancel)],
    )
    app.add_handler(add_product_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_PRODUCTS_LIST}$"), ad_products_list_msg))
    app.add_handler(CallbackQueryHandler(ad_products_list, pattern="^ad_products_list:"))
    app.add_handler(CallbackQueryHandler(ad_product_detail, pattern="^ad_product_detail:"))
    app.add_handler(CallbackQueryHandler(ad_toggle_product, pattern="^ad_toggle_product:"))
    app.add_handler(CallbackQueryHandler(ad_delete_product, pattern="^ad_delete_product:"))

    # --- Buyurtmalar ---
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_ORDERS}$"), ad_orders_list_msg))
    app.add_handler(CallbackQueryHandler(ad_orders_list, pattern="^ad_orders:"))
    app.add_handler(CallbackQueryHandler(ad_order_detail, pattern="^ad_order_detail:"))
    app.add_handler(CallbackQueryHandler(ad_order_location, pattern="^ad_order_loc:"))
    app.add_handler(CallbackQueryHandler(ad_order_accept, pattern="^ad_order_accept:"))
    app.add_handler(CallbackQueryHandler(ad_order_reject, pattern="^ad_order_reject:"))
    app.add_handler(CallbackQueryHandler(ad_order_delivered, pattern="^ad_order_delivered:"))

    # --- Owner-only: do'kon admin ---
    add_admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_ADD_SHOP_ADMIN}$"), own_add_admin_start)],
        states={ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_add_admin_id)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(add_admin_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_ADMINS_LIST}$"), own_admins_list))
    app.add_handler(CallbackQueryHandler(own_remove_admin, pattern="^own_remove_admin:"))

    # --- Owner-only: yetkazib berish narxi ---
    delivery_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_SET_DELIVERY}$"), own_set_delivery_start)],
        states={SET_DELIVERY_PRICE_PER_KM: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_delivery_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(delivery_conv)

    # --- Owner-only: lokatsiya ---
    location_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_SET_LOCATION}$"), own_set_location_start)],
        states={SET_SHOP_LOCATION: [MessageHandler(filters.LOCATION, own_set_location_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(location_conv)

    # --- Owner-only: karta ---
    card_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_SET_CARD}$"), own_set_card_start)],
        states={SET_CARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_card_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(card_conv)

    # --- Owner-only: qo'llanma ---
    guide_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_SET_GUIDE}$"), own_set_guide_start)],
        states={SET_GUIDE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_guide_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(guide_conv)

    # --- Owner-only: aloqa username ---
    contact_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_SET_CONTACT}$"), own_set_contact_start)],
        states={SET_ADMIN_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_contact_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(contact_conv)
