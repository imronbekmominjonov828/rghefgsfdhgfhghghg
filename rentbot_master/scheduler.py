"""
SCHEDULER — fon vazifasi: muddati tugagan mijozlarning botlarini avtomatik to'xtatadi
va ularga eslatma yuboradi. Har N daqiqada bir marta ishlaydi.
"""
import asyncio
import logging

import master_db as mdb
import child_bot_manager as cbm

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60 * 60  # har 1 soatda tekshiradi


async def _check_expired_clients(master_bot):
    expired = await mdb.get_expired_active_clients()
    for client_id, user_id, bot_username in expired:
        await cbm.stop_child_bot(client_id)
        await mdb.suspend_client(client_id)
        logger.info(f"[scheduler] Muddati tugadi, to'xtatildi: client_id={client_id} (@{bot_username})")
        try:
            await master_bot.send_message(
                chat_id=user_id,
                text=(
                    f"⏳ @{bot_username} botingizning arenda muddati tugadi va vaqtincha to'xtatildi.\n\n"
                    f"Davom ettirish uchun \"💳 Arenda to'lovi\" orqali to'lov qiling."
                ),
            )
        except Exception:
            pass


async def _check_soon_expiring(master_bot):
    soon = await mdb.get_soon_expiring_clients(within_hours=24)
    for client_id, user_id, bot_username, expires_at in soon:
        try:
            await master_bot.send_message(
                chat_id=user_id,
                text=(
                    f"⏰ Eslatma: @{bot_username} botingizning arenda muddati "
                    f"{expires_at[:16]} da tugaydi.\n\n"
                    f"Muddatni uzaytirish uchun \"💳 Arenda to'lovi\" orqali to'lov qiling."
                ),
            )
        except Exception:
            pass


async def run_scheduler_loop(master_bot):
    """Master botning Application post_init'idan asyncio.create_task() bilan chaqiriladi."""
    while True:
        try:
            await _check_expired_clients(master_bot)
            await _check_soon_expiring(master_bot)
        except Exception as e:
            logger.error(f"[scheduler] xato: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
