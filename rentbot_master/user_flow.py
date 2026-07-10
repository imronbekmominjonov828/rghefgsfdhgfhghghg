"""
MIJOZ OQIMI:

1. /start -> "Do'kon arendaga olish" matni + tariflar (sinov, oylik, yillik)
   Asosiy menyu PASTKI (Reply) klaviatura sifatida ko'rinadi:
   🏬 Do'kon arendaga olish va narxi
   ⚙️ Bot ma'lumotlarini to'ldirish
   💳 Arenda to'lovi
   📞 Admin bilan aloqa
   👑 Admin panel (faqat ownerlarga)

2. "⚙️ Bot ma'lumotlarini to'ldirish" -> FORMA (bir ketma-ketlikda so'raladi):
   - Do'kon nomi
   - Bot tokeni
   - Bot admin ID
   - Bot username
3. Forma to'lgach status "review" bo'ladi - ADMIN TASDIQLAMAGUNCHA sinov BERILMAYDI.
   Admin "✅ Tasdiqlash / ❌ Rad etish" tugmasi orqali (bu inline, chunki ID asosli) ko'rib chiqadi.
4. Tasdiqlansa -> sinov muddati beriladi, child-bot ishga tushadi.
5. "💳 Arenda to'lovi" -> tarif tanlash (inline, ID asosli emas lekin tanlov - inline qoldirildi
   chunki keyingi bosqich chek surasiga bog'liq) -> KARTA RAQAMI -> chek yuborish -> admin tasdiqlaydi.
"""
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
)
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

import master_db as mdb
import child_bot_manager as cbm
from config import OWNER_IDS, ADMIN_CONTACT_USERNAME
from states import (
    CONTACT_MESSAGE, PAYMENT_PHOTO,
    SETUP_SHOP_NAME, SETUP_TOKEN, SETUP_ADMIN_ID, SETUP_BOT_USERNAME,
)

BTN_PRICING = "🏬 Do'kon arendaga olish va narxi"
BTN_SETUP = "⚙️ Bot ma'lumotlarini to'ldirish"
BTN_PAYMENT = "💳 Arenda to'lovi"
BTN_CONTACT = "📞 Admin bilan aloqa"
BTN_ADMIN_PANEL = "👑 Admin panel"


def fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


async def notify_owners(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode="HTML"):
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_message(
                chat_id=owner_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception:
            pass


def main_menu_keyboard(is_owner: bool = False):
    rows = [
        [BTN_PRICING],
        [BTN_SETUP],
        [BTN_PAYMENT],
        [BTN_CONTACT],
    ]
    if is_owner:
        rows.append([BTN_ADMIN_PANEL])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def _intro_text():
    trial_days, monthly_price, yearly_price = await mdb.get_tariffs()
    return (
        "🏬 <b>Do'kon arendaga olish</b>\n\n"
        f"{trial_days}-kun bepul\n"
        f"Oylik to'lov {fmt_money(monthly_price)}\n"
        f"Yillik to'lov -20%. {fmt_money(yearly_price)}\n\n"
        "Boshlash uchun \"⚙️ Bot ma'lumotlarini to'ldirish\" tugmasini bosing.\n"
        "Savolingiz bo'lsa \"📞 Admin bilan aloqa\" orqali yozing."
    )


# ==================== /start ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await mdb.create_or_update_client(user.id, user.username or "", user.full_name or "")

    text = await _intro_text()
    is_owner = user.id in OWNER_IDS
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard(is_owner))


async def back_to_menu_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply-keyboard orqali 'orqaga' kabi harakatlar uchun (matn tugmasi sifatida)."""
    text = await _intro_text()
    is_owner = update.effective_user.id in OWNER_IDS
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard(is_owner))


async def open_admin_panel_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'👑 Admin panel' tugmasi bosilganda (faqat ownerlar uchun, reply-keyboard tugmasi)."""
    if update.effective_user.id not in OWNER_IDS:
        return  # oddiy foydalanuvchilar bu matnni yuborsa ham e'tiborsiz qoldiriladi
    from master_admin import admin_panel_inline
    await admin_panel_inline(update.message)


async def show_pricing_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'🏬 Do'kon arendaga olish va narxi' tugmasi - tariflar haqida batafsil ma'lumot."""
    trial_days, monthly_price, yearly_price = await mdb.get_tariffs()
    text = (
        "🏬 <b>Do'kon arendaga olish va narxi</b>\n\n"
        f"🎁 {trial_days} kun bepul sinov muddati\n"
        f"📅 Oylik to'lov: {fmt_money(monthly_price)}\n"
        f"📆 Yillik to'lov: {fmt_money(yearly_price)} (-20% chegirma)\n\n"
        "Botingizni ishga tushirish uchun \"⚙️ Bot ma'lumotlarini to'ldirish\" "
        "tugmasini bosing va so'ralgan ma'lumotlarni kiriting."
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ==================== BOT MA'LUMOTLARINI TO'LDIRISH (FORMA) ====================

async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    client = await mdb.get_client(user.id)

    if client and client[8] in ("active", "review"):
        status_text = "faol" if client[8] == "active" else "ko'rib chiqilmoqda"
        await update.message.reply_text(
            f"✅ Sizda allaqachon bot mavjud (holati: {status_text}). "
            f"Yangi bot qo'shish uchun admin bilan bog'laning."
        )
        return ConversationHandler.END

    context.user_data["setup_form"] = {}
    await update.message.reply_text(
        "⚙️ Bot ma'lumotlarini to'ldiramiz.\n\n"
        "1) Do'kon (bot) nomini yuboring (masalan: Online Do'kon):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SETUP_SHOP_NAME


async def setup_shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup_form"]["shop_name"] = update.message.text.strip()
    await update.message.reply_text(
        "2) Botingiz TOKEN'ini yuboring.\n"
        "(Token @BotFather orqali /newbot bilan olinadi)\n\n"
        "⚠️ Tokenni hech kimga oshkor qilmang, faqat shu yerga yuboring."
    )
    return SETUP_TOKEN


async def setup_token_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    if ":" not in token or len(token) < 20:
        await update.message.reply_text(
            "⚠️ Bu token to'g'ri ko'rinmaydi. Iltimos, @BotFather'dan olingan to'liq tokenni yuboring."
        )
        return SETUP_TOKEN

    context.user_data["setup_form"]["bot_token"] = token
    await update.message.reply_text(
        "3) Botingizning ADMIN ID raqamini yuboring.\n"
        "(Bu sizning yoki ishongan odamingizning Telegram ID raqami — botni shu odam boshqaradi.\n"
        "ID'ni @userinfobot orqali bilib olish mumkin)"
    )
    return SETUP_ADMIN_ID


async def setup_admin_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ Iltimos, faqat raqam (Telegram ID) yuboring.")
        return SETUP_ADMIN_ID

    context.user_data["setup_form"]["bot_admin_id"] = int(text)
    await update.message.reply_text("4) Botingizning username'ini yuboring (masalan: @MeningDokonimBot):")
    return SETUP_BOT_USERNAME


async def setup_bot_username_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = update.message.text.strip().lstrip("@")
    user = update.effective_user
    form = context.user_data.pop("setup_form")
    form["bot_username"] = bot_username

    await mdb.set_client_bot_info(
        user_id=user.id,
        bot_token=form["bot_token"],
        bot_username=bot_username,
        shop_owner_id=form["bot_admin_id"],
        shop_name=form["shop_name"],
    )
    # Status "review" qilib belgilaymiz - admin tasdiqlamaguncha sinov BERILMAYDI
    await mdb.set_client_status(user.id, "review")

    is_owner = user.id in OWNER_IDS
    await update.message.reply_text(
        f"✅ Ma'lumotlaringiz qabul qilindi!\n\n"
        f"🏪 Do'kon nomi: {form['shop_name']}\n"
        f"🤖 Bot username: @{bot_username}\n\n"
        f"Admin ma'lumotlarni tekshirib chiqadi. Tasdiqlangandan so'ng botingiz "
        f"sinov muddati bilan ishga tushadi. Iltimos kuting.",
        reply_markup=main_menu_keyboard(is_owner),
    )

    client = await mdb.get_client(user.id)
    client_id = client[0]
    tariffs = await mdb.get_tariffs()
    trial_days = tariffs[0]

    # Adminga (siz) tasdiqlash/rad etish tugmasi bilan so'rovnoma yuboriladi (bu inline -
    # chunki client_id ga bog'liq, ID-asosli tanlov)
    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash (sinov beriladi)", callback_data=f"setup_review_ok:{client_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"setup_review_no:{client_id}"),
    ]]
    notify_text = (
        f"🆕 <b>Yangi bot so'rovnomasi (tasdiqlash kerak)</b>\n\n"
        f"👤 Ism: {user.full_name}\n"
        f"🔗 Username: @{user.username or '-'}\n"
        f"🆔 Telegram ID: {user.id}\n\n"
        f"🏪 Do'kon nomi: {form['shop_name']}\n"
        f"🤖 Bot username: @{bot_username}\n"
        f"👤 Bot admin ID: {form['bot_admin_id']}\n"
        f"🔑 Token: <code>{form['bot_token']}</code>\n\n"
        f"Tasdiqlasangiz, {trial_days} kunlik sinov muddati beriladi va bot ishga tushadi."
    )
    await notify_owners(context, notify_text, reply_markup=InlineKeyboardMarkup(keyboard))

    return ConversationHandler.END


async def setup_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("setup_form", None)
    is_owner = update.effective_user.id in OWNER_IDS
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_keyboard(is_owner))
    return ConversationHandler.END


# ==================== ARENDA TO'LOVI ====================
# Eslatma: tarif tanlash va to'lov bosqichlari INLINE qoldirildi - chunki bu yerda
# ketma-ket bog'liq amallar (tarif tanlash -> chek yuborish) bo'lib, ID-asosli emas,
# lekin alohida xabar ichida ko'rsatish ancha qulay va aniq.

async def rent_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    client = await mdb.get_client(user.id)

    if not client or not client[4]:  # bot_token yo'q
        await update.message.reply_text(
            "⚠️ Avval \"⚙️ Bot ma'lumotlarini to'ldirish\" orqali botingizni ro'yxatdan o'tkazing."
        )
        return

    tariffs = await mdb.get_tariffs()
    trial_days, monthly_price, yearly_price = tariffs

    keyboard = [
        [InlineKeyboardButton(f"📅 Oylik — {fmt_money(monthly_price)}", callback_data="pay_plan:monthly")],
        [InlineKeyboardButton(f"📆 Yillik — {fmt_money(yearly_price)} (-20%)", callback_data="pay_plan:yearly")],
    ]
    await update.message.reply_text("Qaysi tarifni tanlaysiz?", reply_markup=InlineKeyboardMarkup(keyboard))


async def pay_plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split(":")[1]
    tariffs = await mdb.get_tariffs()
    _trial_days, monthly_price, yearly_price = tariffs
    amount = monthly_price if plan == "monthly" else yearly_price

    card_number = await mdb.get_card_number()

    context.user_data["pending_plan"] = plan
    context.user_data["pending_amount"] = amount

    card_text = (
        f"\n💳 Karta raqami: <code>{card_number}</code>\n"
        if card_number else
        "\n⚠️ Karta raqami hali kiritilmagan, admin bilan bog'laning.\n"
    )

    await query.message.reply_text(
        f"💳 To'lov: {fmt_money(amount)}\n{card_text}\n"
        f"To'lovni amalga oshirgandan so'ng, to'lov chekini (screenshot) shu yerga yuboring.\n"
        f"Admin chekni ko'rib chiqib tasdiqlaydi.",
        parse_mode="HTML",
    )
    await query.message.reply_text("📸 To'lov chekini (rasm) yuboring:")
    return PAYMENT_PHOTO


async def payment_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, faqat rasm (screenshot) yuboring.")
        return PAYMENT_PHOTO

    user = update.effective_user
    plan = context.user_data.pop("pending_plan")
    amount = context.user_data.pop("pending_amount")
    photo_file_id = update.message.photo[-1].file_id

    client = await mdb.get_client(user.id)
    client_id = client[0]
    payment_id = await mdb.create_payment(client_id, plan, amount, photo_file_id)

    is_owner = user.id in OWNER_IDS
    await update.message.reply_text(
        "✅ Chekingiz qabul qilindi. Admin tekshirib, tez orada javob beradi.",
        reply_markup=main_menu_keyboard(is_owner),
    )

    plan_text = "Oylik" if plan == "monthly" else "Yillik"
    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_pay:{payment_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_pay:{payment_id}"),
    ]]
    caption = (
        f"💳 <b>Yangi to'lov</b>\n\n"
        f"👤 {user.full_name} (@{user.username or '-'})\n"
        f"🆔 {user.id}\n"
        f"📦 Tarif: {plan_text}\n"
        f"💰 Summa: {fmt_money(amount)}"
    )
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_photo(
                chat_id=owner_id, photo=photo_file_id, caption=caption,
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception:
            pass

    return ConversationHandler.END


async def payment_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_plan", None)
    context.user_data.pop("pending_amount", None)
    is_owner = update.effective_user.id in OWNER_IDS
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_keyboard(is_owner))
    return ConversationHandler.END


# ==================== ADMIN BILAN ALOQA ====================

async def contact_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 Admin bilan bog'lanish uchun: xabaringizni yozing, "
        f"xabaringiz adminga yetkaziladi.\n\nAdmin: @{ADMIN_CONTACT_USERNAME}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text("✍️ Xabaringizni yozing:")
    return CONTACT_MESSAGE


async def contact_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    await mdb.save_contact_message(user.id, user.username or "", user.full_name or "", text)

    is_owner = user.id in OWNER_IDS
    await update.message.reply_text(
        "✅ Xabaringiz adminga yetkazildi.", reply_markup=main_menu_keyboard(is_owner)
    )

    notify_text = (
        f"✉️ <b>Yangi xabar</b>\n\n"
        f"👤 {user.full_name} (@{user.username or '-'})\n"
        f"🆔 {user.id}\n\n"
        f"💬 {text}"
    )
    await notify_owners(context, notify_text)
    return ConversationHandler.END


async def contact_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_owner = update.effective_user.id in OWNER_IDS
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_keyboard(is_owner))
    return ConversationHandler.END


# ==================== RO'YXATDAN O'TKAZISH ====================

def register_user_flow_handlers(app):
    app.add_handler(CommandHandler("start", start))

    # --- Asosiy menyu (Reply Keyboard) tugmalari ---
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_PRICING}$"), show_pricing_msg))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_ADMIN_PANEL}$"), open_admin_panel_msg))

    setup_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_SETUP}$"), setup_start)],
        states={
            SETUP_SHOP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_shop_name)],
            SETUP_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_token_received)],
            SETUP_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_admin_id_received)],
            SETUP_BOT_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_bot_username_received)],
        },
        fallbacks=[CommandHandler("cancel", setup_cancel)],
    )
    app.add_handler(setup_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_PAYMENT}$"), rent_payment_start))

    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pay_plan_selected, pattern="^pay_plan:")],
        states={
            PAYMENT_PHOTO: [
                MessageHandler(filters.PHOTO, payment_photo_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_photo_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", payment_cancel)],
    )
    app.add_handler(payment_conv)

    contact_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_CONTACT}$"), contact_admin_start)],
        states={CONTACT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_message_received)]},
        fallbacks=[CommandHandler("cancel", contact_cancel)],
    )
    app.add_handler(contact_conv)
