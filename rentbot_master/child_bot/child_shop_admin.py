"""
CHILD BOT — ADMIN PANELI (kategoriya, mahsulot, buyurtmalar).
Bu bo'lim ham 1-daraja (owner), ham 2-daraja (do'kon admin) uchun BIR XIL —
ikkalasi ham kategoriya/mahsulot qo'shadi va buyurtmalarni boshqaradi.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from . import child_db as db
from .child_states import (
    CAT_ADD_NAME, CAT_RENAME,
    PROD_CATEGORY, PROD_NAME, PROD_UNIT, PROD_BUY_PRICE, PROD_SELL_PRICE, PROD_PHOTO,
)

PAGE_SIZE = 10


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


# ==================== ADMIN PANEL ====================

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏷 Katalog qo'shish", callback_data="ad_add_category")],
        [InlineKeyboardButton("✏️ Katalogni tahrirlash", callback_data="ad_edit_categories:0")],
        [InlineKeyboardButton("➕ Mahsulot qo'shish", callback_data="ad_add_product")],
        [InlineKeyboardButton("📦 Mahsulotlar ro'yxati", callback_data="ad_products_list:0")],
        [InlineKeyboardButton("🧾 Buyurtmalar", callback_data="ad_orders:0")],
    ]
    await update.message.reply_text(
        "🛠 Admin panel:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ad_back_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🏷 Katalog qo'shish", callback_data="ad_add_category")],
        [InlineKeyboardButton("✏️ Katalogni tahrirlash", callback_data="ad_edit_categories:0")],
        [InlineKeyboardButton("➕ Mahsulot qo'shish", callback_data="ad_add_product")],
        [InlineKeyboardButton("📦 Mahsulotlar ro'yxati", callback_data="ad_products_list:0")],
        [InlineKeyboardButton("🧾 Buyurtmalar", callback_data="ad_orders:0")],
    ]
    await query.message.reply_text("🛠 Admin panel:", reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== KATALOG (KATEGORIYA) ====================

async def ad_add_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_any_admin(update.effective_user.id):
        return ConversationHandler.END
    await query.message.reply_text("Yangi katalog nomini kiriting:")
    return CAT_ADD_NAME


async def ad_add_category_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    await db.add_category(name)
    await update.message.reply_text(f"✅ \"{name}\" katalogi qo'shildi.")
    return ConversationHandler.END


async def ad_edit_categories_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = await db.get_categories()
    if not categories:
        await query.message.reply_text("Bu kategoriya bo'sh.")
        return
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"ad_cat_detail:{cid}")]
        for cid, name in categories
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="ad_back_panel")])
    await query.message.reply_text("📝 Katalogni tahrirlash:", reply_markup=InlineKeyboardMarkup(keyboard))


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
    query = update.callback_query
    await query.answer()
    if not await db.is_any_admin(update.effective_user.id):
        return ConversationHandler.END

    categories = await db.get_categories()
    if not categories:
        await query.message.reply_text("⚠️ Avval kamida 1 ta katalog qo'shing.")
        return ConversationHandler.END

    context.user_data["new_product"] = {}
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"pick_pcat:{cid}")]
        for cid, name in categories
    ]
    await query.message.reply_text("Kategoriya tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
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
    return ConversationHandler.END


async def ad_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


# ==================== MAHSULOTLAR RO'YXATI (admin) ====================

async def ad_products_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])

    products = await db.get_all_products_admin(offset, PAGE_SIZE)
    total = await db.count_all_products()

    if not products:
        await query.message.reply_text("Hozircha mahsulot yo'q.")
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
    keyboard.append([InlineKeyboardButton("⬅️ Admin panel", callback_data="ad_back_panel")])

    await query.message.reply_text(f"📦 Mahsulotlar ({total} ta):", reply_markup=InlineKeyboardMarkup(keyboard))


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

async def ad_orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])

    orders = await db.get_orders_admin(offset, PAGE_SIZE)
    total = await db.count_orders_admin()

    if not orders:
        await query.message.reply_text("Hozircha buyurtmalar yo'q.")
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
    keyboard.append([InlineKeyboardButton("⬅️ Admin panel", callback_data="ad_back_panel")])

    await query.message.reply_text(f"🧾 Buyurtmalar ({total} ta):", reply_markup=InlineKeyboardMarkup(keyboard))


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

    text = (
        f"🧾 <b>Buyurtma #{order_id}</b>\n\n"
        f"👤 {customer_name}\n"
        f"📞 {customer_phone}\n"
        f"📍 Masofa: {distance_km if distance_km is not None else '—'} km\n\n"
        f"{items_text}\n\n"
        f"Mahsulotlar: {fmt_money(items_total)}\n"
        f"Yetkazib berish: {fmt_money(delivery_price)}\n"
        f"<b>Jami: {fmt_money(grand_total)}</b>\n"
        f"Holat: {status}"
    )

    keyboard = []
    if lat and lon:
        keyboard.append([InlineKeyboardButton("📍 Lokatsiyani ko'rish", callback_data=f"ad_order_loc:{order_id}")])
    if status == "new":
        keyboard.append([
            InlineKeyboardButton("👍 Qabul qilish", callback_data=f"ad_order_accept:{order_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"ad_order_reject:{order_id}"),
        ])
    elif status == "accepted":
        keyboard.append([InlineKeyboardButton("✅ Yetkazildi", callback_data=f"ad_order_delivered:{order_id}")])

    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)


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


# ==================== RO'YXATDAN O'TKAZISH ====================

def register_child_shop_admin_handlers(app):
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(ad_back_panel, pattern="^ad_back_panel$"))

    add_cat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_add_category_start, pattern="^ad_add_category$")],
        states={CAT_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_add_category_save)]},
        fallbacks=[CommandHandler("cancel", ad_cancel)],
    )
    app.add_handler(add_cat_conv)

    app.add_handler(CallbackQueryHandler(ad_edit_categories_list, pattern="^ad_edit_categories:"))
    app.add_handler(CallbackQueryHandler(ad_cat_detail, pattern="^ad_cat_detail:"))

    rename_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_cat_rename_start, pattern="^ad_cat_rename:")],
        states={CAT_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_cat_rename_apply)]},
        fallbacks=[CommandHandler("cancel", ad_cancel)],
    )
    app.add_handler(rename_conv)
    app.add_handler(CallbackQueryHandler(ad_cat_delete, pattern="^ad_cat_delete:"))

    add_product_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_add_product_start, pattern="^ad_add_product$")],
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

    app.add_handler(CallbackQueryHandler(ad_products_list, pattern="^ad_products_list:"))
    app.add_handler(CallbackQueryHandler(ad_product_detail, pattern="^ad_product_detail:"))
    app.add_handler(CallbackQueryHandler(ad_toggle_product, pattern="^ad_toggle_product:"))
    app.add_handler(CallbackQueryHandler(ad_delete_product, pattern="^ad_delete_product:"))

    app.add_handler(CallbackQueryHandler(ad_orders_list, pattern="^ad_orders:"))
    app.add_handler(CallbackQueryHandler(ad_order_detail, pattern="^ad_order_detail:"))
    app.add_handler(CallbackQueryHandler(ad_order_location, pattern="^ad_order_loc:"))
    app.add_handler(CallbackQueryHandler(ad_order_accept, pattern="^ad_order_accept:"))
    app.add_handler(CallbackQueryHandler(ad_order_reject, pattern="^ad_order_reject:"))
    app.add_handler(CallbackQueryHandler(ad_order_delivered, pattern="^ad_order_delivered:"))
