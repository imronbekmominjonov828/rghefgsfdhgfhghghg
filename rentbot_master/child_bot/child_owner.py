"""
CHILD BOT — OWNER (1-daraja admin, botni sotib olgan kishi) funksiyalari.

Faqat owner:
- Boshqa "do'kon admin"larni (2-daraja) qo'sha oladi / o'chira oladi
- Yetkazib berish narxini, do'kon lokatsiyasini, karta raqamini, qo'llanma matnini sozlaydi
- Admin bilan aloqa uchun ko'rsatiladigan username'ni belgilaydi

2-daraja admin ham qolgan hamma narsaga (kategoriya, mahsulot, buyurtma) ega bo'lgani uchun
ular umumiy child_shop_admin.py da boshqariladi.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from . import child_db as db
from .child_states import (
    ADD_ADMIN_ID, SET_DELIVERY_PRICE, SET_CARD_NUMBER, SET_GUIDE_TEXT,
    SET_ADMIN_CONTACT, SET_SHOP_LOCATION,
)


def fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await db.is_owner(user_id):
            if update.message:
                await update.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
            return
        return await func(update, context)
    return wrapper


# ==================== OWNER PANEL ====================

@owner_only
async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 Do'kon admin qo'shish", callback_data="own_add_admin")],
        [InlineKeyboardButton("👥 Adminlar ro'yxati", callback_data="own_admins_list")],
        [InlineKeyboardButton("🚚 Yetkazib berish narxi", callback_data="own_set_delivery")],
        [InlineKeyboardButton("📍 Do'kon lokatsiyasi", callback_data="own_set_location")],
        [InlineKeyboardButton("💳 Karta raqami", callback_data="own_set_card")],
        [InlineKeyboardButton("📖 Qo'llanma matni", callback_data="own_set_guide")],
        [InlineKeyboardButton("📞 Aloqa uchun username", callback_data="own_set_contact")],
    ]
    await update.message.reply_text(
        "👑 Bot egasi paneli",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ==================== DO'KON ADMIN QO'SHISH ====================

async def own_add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_owner(update.effective_user.id):
        await query.message.reply_text("Bu bo'lim faqat bot egasi uchun.")
        return ConversationHandler.END
    await query.message.reply_text(
        "Yangi do'kon adminining Telegram ID raqamini yuboring.\n"
        "(U kishi @userinfobot orqali o'z ID'sini bilib olishi mumkin)"
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
    await update.message.reply_text(
        f"✅ Yangi do'kon admin qo'shildi (ID: {new_admin_id}).\n"
        f"U kishi botga /admin buyrug'ini yuborib boshqaruv panelidan foydalanishi mumkin."
    )

    try:
        await context.bot.send_message(
            chat_id=new_admin_id,
            text="✅ Sizni ushbu do'kon botida admin etib tayinlashdi!\n"
                 "Boshqaruv paneliga kirish uchun /admin buyrug'ini yuboring.",
        )
    except Exception:
        pass

    return ConversationHandler.END


async def own_admins_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admins = await db.get_all_admins()
    if not admins:
        await query.message.reply_text("Hozircha adminlar yo'q.")
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

    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)


async def own_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_user_id = int(query.data.split(":")[1])
    await db.remove_admin(admin_user_id)
    await query.message.reply_text("🗑 Admin o'chirildi.")


# ==================== YETKAZIB BERISH NARXI ====================

async def own_set_delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    settings = await db.get_settings()
    current = settings[0] if settings else 0
    await query.message.reply_text(
        f"Joriy yetkazib berish narxi: {fmt_money(current)}\n\n"
        f"Yangi narxni so'mda yuboring (faqat raqam, masalan: 15000):"
    )
    return SET_DELIVERY_PRICE


async def own_set_delivery_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam yuboring.")
        return SET_DELIVERY_PRICE
    await db.update_settings(delivery_price=int(text))
    await update.message.reply_text(f"✅ Yetkazib berish narxi {fmt_money(int(text))} qilib o'rnatildi.")
    return ConversationHandler.END


# ==================== DO'KON LOKATSIYASI ====================

async def own_set_location_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    query = update.callback_query
    await query.answer()
    location_btn = KeyboardButton("📍 Do'kon lokatsiyasini yuborish", request_location=True)
    await query.message.reply_text(
        "Do'koningiz joylashgan manzilni (lokatsiyani) yuboring. "
        "Bu mijozlardan masofani hisoblash uchun ishlatiladi:",
        reply_markup=ReplyKeyboardMarkup([[location_btn]], resize_keyboard=True),
    )
    return SET_SHOP_LOCATION


async def own_set_location_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import ReplyKeyboardRemove
    if not update.message.location:
        await update.message.reply_text("⚠️ Iltimos, lokatsiya tugmasini bosing.")
        return SET_SHOP_LOCATION
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    await db.update_settings(shop_location_lat=lat, shop_location_lon=lon)
    await update.message.reply_text("✅ Do'kon lokatsiyasi saqlandi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ==================== KARTA RAQAMI ====================

async def own_set_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    settings = await db.get_settings()
    current = settings[3] if settings and settings[3] else "— hali kiritilmagan"
    await query.message.reply_text(
        f"Joriy karta raqami: {current}\n\nYangi karta raqamini yuboring (masalan: 8600 1234 5678 9012):"
    )
    return SET_CARD_NUMBER


async def own_set_card_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card = update.message.text.strip()
    await db.update_settings(card_number=card)
    await update.message.reply_text(f"✅ Karta raqami saqlandi: {card}")
    return ConversationHandler.END


# ==================== QO'LLANMA MATNI ====================

async def own_set_guide_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Yangi qo'llanma matnini yuboring (foydalanuvchilarga ko'rinadi):")
    return SET_GUIDE_TEXT


async def own_set_guide_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await db.update_settings(guide_text=text)
    await update.message.reply_text("✅ Qo'llanma matni saqlandi.")
    return ConversationHandler.END


# ==================== ALOQA USERNAME ====================

async def own_set_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Admin bilan aloqa uchun ko'rsatiladigan username'ni yuboring (@ siz):")
    return SET_ADMIN_CONTACT


async def own_set_contact_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().lstrip("@")
    await db.update_settings(admin_contact_username=username)
    await update.message.reply_text(f"✅ Aloqa username saqlandi: @{username}")
    return ConversationHandler.END


async def own_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


# ==================== RO'YXATDAN O'TKAZISH ====================

def register_child_owner_handlers(app):
    app.add_handler(CommandHandler("owner", owner_panel))

    add_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(own_add_admin_start, pattern="^own_add_admin$")],
        states={ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_add_admin_id)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(add_admin_conv)

    app.add_handler(CallbackQueryHandler(own_admins_list, pattern="^own_admins_list$"))
    app.add_handler(CallbackQueryHandler(own_remove_admin, pattern="^own_remove_admin:"))

    delivery_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(own_set_delivery_start, pattern="^own_set_delivery$")],
        states={SET_DELIVERY_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_delivery_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(delivery_conv)

    location_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(own_set_location_start, pattern="^own_set_location$")],
        states={SET_SHOP_LOCATION: [MessageHandler(filters.LOCATION, own_set_location_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(location_conv)

    card_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(own_set_card_start, pattern="^own_set_card$")],
        states={SET_CARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_card_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(card_conv)

    guide_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(own_set_guide_start, pattern="^own_set_guide$")],
        states={SET_GUIDE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_guide_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(guide_conv)

    contact_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(own_set_contact_start, pattern="^own_set_contact$")],
        states={SET_ADMIN_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, own_set_contact_apply)]},
        fallbacks=[CommandHandler("cancel", own_cancel)],
    )
    app.add_handler(contact_conv)
