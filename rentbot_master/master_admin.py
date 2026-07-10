"""
MASTER BOT ADMIN PANELI. Faqat config.py dagi OWNER_IDS dagi foydalanuvchilar kira oladi.

Imkoniyatlar:
- To'lovlarni tasdiqlash / rad etish
- Bot so'rovnomalarini tekshirib, child-botni ishga tushirish
- Mijozlar ro'yxati, statusi, muddati
- Tariflarni o'zgartirish
- Mijozni to'xtatish (suspend) / qayta yoqish
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

import master_db as mdb
import child_bot_manager as cbm
from config import OWNER_IDS, PAGE_SIZE
from states import TARIFF_TRIAL, TARIFF_MONTHLY, TARIFF_YEARLY, CARD_NUMBER


def fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in OWNER_IDS:
            if update.message:
                await update.message.reply_text("Sizda bu buyruqdan foydalanish huquqi yo'q.")
            return
        return await func(update, context)
    return wrapper


# ==================== ASOSIY MENU ====================

@owner_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_count = await mdb.count_pending_payments()
    keyboard = [
        [InlineKeyboardButton(f"💳 To'lovlar ({pending_count})", callback_data="ap_payments:0")],
        [InlineKeyboardButton("👥 Mijozlar ro'yxati", callback_data="ap_clients:0")],
        [InlineKeyboardButton("⚙️ Tariflarni sozlash", callback_data="ap_tariffs")],
        [InlineKeyboardButton("🤖 Ishlayotgan botlar", callback_data="ap_running")],
    ]
    await update.message.reply_text(
        "👑 Bosh admin paneli",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_panel_inline(message):
    """user_flow.py dagi '👑 Admin panel' inline tugmasi bosilganda chaqiriladi."""
    pending_count = await mdb.count_pending_payments()
    keyboard = [
        [InlineKeyboardButton(f"💳 To'lovlar ({pending_count})", callback_data="ap_payments:0")],
        [InlineKeyboardButton("👥 Mijozlar ro'yxati", callback_data="ap_clients:0")],
        [InlineKeyboardButton("⚙️ Tariflarni sozlash", callback_data="ap_tariffs")],
        [InlineKeyboardButton("🤖 Ishlayotgan botlar", callback_data="ap_running")],
    ]
    await message.reply_text(
        "👑 Bosh admin paneli",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ==================== TO'LOVLARNI TASDIQLASH ====================

async def ap_payments_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])

    payments = await mdb.get_pending_payments(offset, PAGE_SIZE)
    total = await mdb.count_pending_payments()

    if not payments:
        await query.message.reply_text("Hozircha kutilayotgan to'lovlar yo'q.")
        return

    keyboard = []
    for pay_id, client_id, plan, amount, full_name, username in payments:
        plan_text = "Oylik" if plan == "monthly" else "Yillik"
        keyboard.append([
            InlineKeyboardButton(
                f"{full_name} — {plan_text} — {fmt_money(amount)}",
                callback_data=f"ap_pay_detail:{pay_id}",
            )
        ])
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"ap_payments:{max(0, offset-PAGE_SIZE)}"))
    if offset + PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"ap_payments:{offset+PAGE_SIZE}"))
    if nav_row:
        keyboard.append(nav_row)

    await query.message.reply_text(
        f"💳 Kutilayotgan to'lovlar ({total} ta):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ap_payment_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payment_id = int(query.data.split(":")[1])
    payment = await mdb.get_payment(payment_id)
    if not payment:
        await query.message.reply_text("To'lov topilmadi.")
        return
    _id, client_id, plan, amount, photo_file_id, status, created_at = payment
    plan_text = "Oylik" if plan == "monthly" else "Yillik"

    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_pay:{payment_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_pay:{payment_id}"),
    ]]
    caption = f"💳 Tarif: {plan_text}\n💰 Summa: {fmt_money(amount)}\nHolat: {status}"
    if photo_file_id:
        await query.message.reply_photo(photo=photo_file_id, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard))


async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payment_id = int(query.data.split(":")[1])
    payment = await mdb.get_payment(payment_id)
    if not payment:
        await query.message.reply_text("To'lov topilmadi.")
        return
    _id, client_id, plan, amount, photo_file_id, status, created_at = payment

    if status != "waiting":
        await query.message.reply_text("Bu to'lov allaqachon ko'rib chiqilgan.")
        return

    days = 30 if plan == "monthly" else 365
    new_expiry = await mdb.extend_client(client_id, plan, days)
    await mdb.update_payment_status(payment_id, "approved")

    client = await mdb.get_client_by_id(client_id)
    client_user_id = client[1]

    await query.message.reply_text(f"✅ To'lov tasdiqlandi. Yangi muddat: {new_expiry[:10]}")

    try:
        await context.bot.send_message(
            chat_id=client_user_id,
            text=(
                f"✅ To'lovingiz tasdiqlandi!\n"
                f"Tarifingiz muddati: {new_expiry[:10]} gacha.\n\n"
                f"Agar hali bot ma'lumotlarini to'ldirmagan bo'lsangiz, "
                f"\"⚙️ Bot ma'lumotlarini to'ldirish\" tugmasini bosing."
            ),
        )
    except Exception:
        pass

    # Agar bu mijozning boti allaqachon tasdiqlangan va token mavjud bo'lsa,
    # lekin biror sababga ko'ra ishlamayotgan bo'lsa — qayta ishga tushiramiz.
    if client[4] and client[8] == "active" and not cbm.is_bot_running(client_id):
        await cbm.start_child_bot(client_id, client[4], client[6])


async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payment_id = int(query.data.split(":")[1])
    payment = await mdb.get_payment(payment_id)
    if not payment:
        await query.message.reply_text("To'lov topilmadi.")
        return
    _id, client_id, plan, amount, photo_file_id, status, created_at = payment

    await mdb.update_payment_status(payment_id, "rejected")
    await query.message.reply_text("❌ To'lov rad etildi.")

    client = await mdb.get_client_by_id(client_id)
    try:
        await context.bot.send_message(
            chat_id=client[1],
            text="❌ Afsuski, to'lovingiz tasdiqlanmadi. Iltimos, admin bilan bog'laning.",
        )
    except Exception:
        pass


# ==================== BOT SO'ROVNOMASINI TEKSHIRISH ====================

async def setup_review_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    client = await mdb.get_client_by_id(client_id)
    if not client:
        await query.message.reply_text("Mijoz topilmadi.")
        return
    _id, user_id, username, full_name, bot_token, bot_username, shop_owner_id, plan, status, expires_at, created_at, shop_name = client

    # Agar hali 'active' bo'lmagan bo'lsa (masalan to'lov hali tasdiqlanmagan bo'lsa ham),
    # sinov muddati sifatida tasdiqlaymiz.
    if status != "active":
        tariffs = await mdb.get_tariffs()
        trial_days = tariffs[0]
        await mdb.approve_client(client_id, "trial", trial_days)

    ok = await cbm.start_child_bot(client_id, bot_token, shop_owner_id)
    if ok:
        await query.message.reply_text(f"✅ @{bot_username} boti ishga tushirildi!")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Tabriklaymiz! @{bot_username} botingiz ishga tushdi va sinov muddati boshlandi.\n\n"
                     f"Endi botingizga kirib, /owner buyrug'i orqali do'kon profilingizni sozlang, "
                     f"/admin orqali kategoriya va mahsulot qo'shing.",
            )
        except Exception:
            pass
    else:
        await query.message.reply_text("⚠️ Botni ishga tushirishda xatolik yuz berdi.")


async def setup_review_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    client = await mdb.get_client_by_id(client_id)
    if not client:
        return
    await mdb.reject_client(client_id)
    await query.message.reply_text("❌ So'rovnoma rad etildi.")
    try:
        await context.bot.send_message(
            chat_id=client[1],
            text="❌ Afsuski, bot ma'lumotlaringiz tasdiqlanmadi. Admin bilan bog'laning.",
        )
    except Exception:
        pass


# ==================== MIJOZLAR RO'YXATI ====================

async def ap_clients_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])

    clients = await mdb.get_all_clients(offset, PAGE_SIZE)
    total = await mdb.count_all_clients()

    if not clients:
        await query.message.reply_text("Hozircha mijozlar yo'q.")
        return

    status_emoji = {"pending": "⚪", "review": "🟡", "active": "🟢", "suspended": "🔴", "rejected": "⚫"}
    keyboard = []
    for cid, user_id, full_name, bot_username, plan, status, expires_at in clients:
        emoji = status_emoji.get(status, "⚪")
        label = f"{emoji} {full_name or user_id}"
        if bot_username:
            label += f" (@{bot_username})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"ap_client_detail:{cid}")])

    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"ap_clients:{max(0, offset-PAGE_SIZE)}"))
    if offset + PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"ap_clients:{offset+PAGE_SIZE}"))
    if nav_row:
        keyboard.append(nav_row)

    await query.message.reply_text(
        f"👥 Mijozlar ({total} ta):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ap_client_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    client = await mdb.get_client_by_id(client_id)
    if not client:
        await query.message.reply_text("Mijoz topilmadi.")
        return
    _id, user_id, username, full_name, bot_token, bot_username, shop_owner_id, plan, status, expires_at, created_at, shop_name = client

    is_running = cbm.is_bot_running(client_id)
    text = (
        f"👤 <b>{full_name}</b>\n"
        f"🔗 @{username or '-'}\n"
        f"🆔 {user_id}\n"
        f"🏪 Do'kon: {shop_name or '—'}\n"
        f"🤖 Bot: @{bot_username or '— hali kiritilmagan'}\n"
        f"📦 Tarif: {plan}\n"
        f"📌 Holat: {status}\n"
        f"⏳ Muddat: {expires_at[:10] if expires_at else '—'}\n"
        f"▶️ Bot hozir: {'ishlayapti ✅' if is_running else 'to‘xtagan 🔴'}"
    )

    keyboard = []
    if bot_token:
        if is_running:
            keyboard.append([InlineKeyboardButton("🚫 Botni to'xtatish", callback_data=f"ap_stop_bot:{client_id}")])
        else:
            keyboard.append([InlineKeyboardButton("▶️ Botni ishga tushirish", callback_data=f"ap_start_bot:{client_id}")])
    keyboard.append([
        InlineKeyboardButton("➕7 kun", callback_data=f"ap_extend_days:{client_id}:7"),
        InlineKeyboardButton("➕30 kun", callback_data=f"ap_extend_days:{client_id}:30"),
        InlineKeyboardButton("➕365 kun", callback_data=f"ap_extend_days:{client_id}:365"),
    ])
    keyboard.append([
        InlineKeyboardButton("➖7 kun", callback_data=f"ap_extend_days:{client_id}:-7"),
        InlineKeyboardButton("➖30 kun", callback_data=f"ap_extend_days:{client_id}:-30"),
    ])
    keyboard.append([InlineKeyboardButton("⏹ Hozir tugatish (muddatdan oldin)", callback_data=f"ap_terminate_now:{client_id}")])
    keyboard.append([InlineKeyboardButton("⛔️ Suspend qilish", callback_data=f"ap_suspend:{client_id}")])

    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def ap_start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    client = await mdb.get_client_by_id(client_id)
    if not client or not client[4]:
        await query.message.reply_text("Token topilmadi.")
        return
    await cbm.start_child_bot(client_id, client[4], client[6])
    await query.message.reply_text("✅ Bot ishga tushirildi.")


async def ap_stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    await cbm.stop_child_bot(client_id)
    await query.message.reply_text("🚫 Bot to'xtatildi.")


async def ap_extend_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin muddatga +N yoki -N kun qo'shadi/ayiradi (manfiy son = ayirish)."""
    query = update.callback_query
    await query.answer()
    _, client_id, delta = query.data.split(":")
    client_id, delta = int(client_id), int(delta)

    client = await mdb.get_client_by_id(client_id)
    if not client:
        await query.message.reply_text("Mijoz topilmadi.")
        return

    if client[9]:  # expires_at mavjud
        new_expiry = await mdb.adjust_client_expiry_days(client_id, delta)
    else:
        # Hali muddat berilmagan (masalan to'g'ridan-to'g'ri admin sinov bermay turib kun qo'shmoqchi) -
        # bugundan boshlab hisoblaymiz
        plan = "monthly" if delta > 0 else "trial"
        new_expiry = await mdb.extend_client(client_id, plan, max(delta, 0))

    if not new_expiry:
        await query.message.reply_text("⚠️ Muddatni o'zgartirib bo'lmadi.")
        return

    sign = "+" if delta > 0 else ""
    await query.message.reply_text(
        f"✅ Muddat o'zgartirildi ({sign}{delta} kun). Yangi muddat: {new_expiry[:10]} gacha."
    )

    # Agar yangi muddat hali kelajakda bo'lsa va bot to'xtagan bo'lsa - qayta ishga tushiramiz
    from datetime import datetime
    try:
        still_active = datetime.fromisoformat(new_expiry) > datetime.utcnow()
    except ValueError:
        still_active = True

    if still_active and client[4] and not cbm.is_bot_running(client_id):
        await cbm.start_child_bot(client_id, client[4], client[6])
    elif not still_active and cbm.is_bot_running(client_id):
        # Kun ayirish natijasida muddat o'tib ketgan bo'lsa - botni darhol to'xtatamiz
        await cbm.stop_child_bot(client_id)
        await mdb.suspend_client(client_id)
        await query.message.reply_text("⏹ Yangi muddat allaqachon o'tib ketgan, bot to'xtatildi.")


async def ap_terminate_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin to'lov/sinov muddatini VAQTIDAN OLDIN tugatadi - bot darhol to'xtatiladi."""
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    keyboard = [[
        InlineKeyboardButton("✅ Ha, hozir tugatilsin", callback_data=f"ap_terminate_yes:{client_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="ap_terminate_no"),
    ]]
    await query.message.reply_text(
        "Haqiqatan ham bu mijozning muddatini VAQTIDAN OLDIN tugatib, botini darhol "
        "to'xtatmoqchimisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ap_terminate_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])

    from datetime import datetime
    await mdb.set_client_expiry(client_id, datetime.utcnow().isoformat())
    await mdb.suspend_client(client_id)
    await cbm.stop_child_bot(client_id)

    await query.edit_message_text("⏹ Muddat vaqtidan oldin tugatildi, bot to'xtatildi.")

    client = await mdb.get_client_by_id(client_id)
    if client:
        try:
            await context.bot.send_message(
                chat_id=client[1],
                text="⏹ Arenda muddatingiz admin tomonidan vaqtidan oldin tugatildi va botingiz to'xtatildi.",
            )
        except Exception:
            pass


async def ap_terminate_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Bekor qilindi.")


async def ap_suspend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    await mdb.suspend_client(client_id)
    await cbm.stop_child_bot(client_id)
    await query.message.reply_text("⛔️ Mijoz suspend qilindi, boti to'xtatildi.")


# ==================== ISHLAYOTGAN BOTLAR ====================

async def ap_running_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = cbm.get_running_count()
    await query.message.reply_text(f"🤖 Hozir {count} ta child-bot ishlayapti.")


# ==================== TARIFLAR ====================

async def ap_tariffs_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    trial_days, monthly_price, yearly_price = await mdb.get_tariffs()
    card_number = await mdb.get_card_number()
    keyboard = [
        [InlineKeyboardButton("✏️ Tariflarni o'zgartirish", callback_data="ap_tariffs_edit")],
        [InlineKeyboardButton("💳 Karta raqamini o'zgartirish", callback_data="ap_card_edit")],
    ]
    await query.message.reply_text(
        f"⚙️ Joriy tariflar:\n\n"
        f"Sinov muddati: {trial_days} kun\n"
        f"Oylik: {fmt_money(monthly_price)}\n"
        f"Yillik: {fmt_money(yearly_price)}\n"
        f"💳 Karta: {card_number or '— hali kiritilmagan'}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ap_card_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Yangi karta raqamini yuboring (masalan: 8600 1234 5678 9012):")
    return CARD_NUMBER


async def ap_card_edit_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card = update.message.text.strip()
    await mdb.set_card_number(card)
    await update.message.reply_text(f"✅ Karta raqami saqlandi: {card}")
    return ConversationHandler.END


async def ap_tariffs_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Yangi sinov muddatini kunlarda yuboring (masalan: 15):")
    return TARIFF_TRIAL


async def ap_tariff_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam yuboring.")
        return TARIFF_TRIAL
    context.user_data["new_trial_days"] = int(text)
    await update.message.reply_text("Yangi oylik narxni so'mda yuboring (masalan: 50000):")
    return TARIFF_MONTHLY


async def ap_tariff_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam yuboring.")
        return TARIFF_MONTHLY
    context.user_data["new_monthly_price"] = int(text)
    await update.message.reply_text("Yangi yillik narxni so'mda yuboring (masalan: 500000):")
    return TARIFF_YEARLY


async def ap_tariff_yearly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam yuboring.")
        return TARIFF_YEARLY

    trial_days = context.user_data.pop("new_trial_days")
    monthly_price = context.user_data.pop("new_monthly_price")
    yearly_price = int(text)

    await mdb.update_tariffs(trial_days, monthly_price, yearly_price)
    await update.message.reply_text(
        f"✅ Tariflar yangilandi!\n\n"
        f"Sinov: {trial_days} kun\nOylik: {fmt_money(monthly_price)}\nYillik: {fmt_money(yearly_price)}"
    )
    return ConversationHandler.END


async def ap_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


# ==================== RO'YXATDAN O'TKAZISH ====================

def register_admin_panel_handlers(app):
    app.add_handler(CommandHandler("adminpanel", admin_panel))

    app.add_handler(CallbackQueryHandler(ap_payments_list, pattern="^ap_payments:"))
    app.add_handler(CallbackQueryHandler(ap_payment_detail, pattern="^ap_pay_detail:"))
    app.add_handler(CallbackQueryHandler(approve_payment, pattern="^approve_pay:"))
    app.add_handler(CallbackQueryHandler(reject_payment, pattern="^reject_pay:"))

    app.add_handler(CallbackQueryHandler(setup_review_approve, pattern="^setup_review_ok:"))
    app.add_handler(CallbackQueryHandler(setup_review_reject, pattern="^setup_review_no:"))

    app.add_handler(CallbackQueryHandler(ap_clients_list, pattern="^ap_clients:"))
    app.add_handler(CallbackQueryHandler(ap_client_detail, pattern="^ap_client_detail:"))
    app.add_handler(CallbackQueryHandler(ap_start_bot, pattern="^ap_start_bot:"))
    app.add_handler(CallbackQueryHandler(ap_stop_bot, pattern="^ap_stop_bot:"))
    app.add_handler(CallbackQueryHandler(ap_extend_days, pattern="^ap_extend_days:"))
    app.add_handler(CallbackQueryHandler(ap_terminate_now, pattern="^ap_terminate_now:"))
    app.add_handler(CallbackQueryHandler(ap_terminate_yes, pattern="^ap_terminate_yes:"))
    app.add_handler(CallbackQueryHandler(ap_terminate_no, pattern="^ap_terminate_no$"))
    app.add_handler(CallbackQueryHandler(ap_suspend, pattern="^ap_suspend:"))

    app.add_handler(CallbackQueryHandler(ap_running_bots, pattern="^ap_running$"))

    app.add_handler(CallbackQueryHandler(ap_tariffs_show, pattern="^ap_tariffs$"))

    card_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ap_card_edit_start, pattern="^ap_card_edit$")],
        states={CARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_card_edit_apply)]},
        fallbacks=[CommandHandler("cancel", ap_cancel)],
    )
    app.add_handler(card_conv)

    tariff_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ap_tariffs_edit_start, pattern="^ap_tariffs_edit$")],
        states={
            TARIFF_TRIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_tariff_trial)],
            TARIFF_MONTHLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_tariff_monthly)],
            TARIFF_YEARLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_tariff_yearly)],
        },
        fallbacks=[CommandHandler("cancel", ap_cancel)],
    )
    app.add_handler(tariff_conv)
