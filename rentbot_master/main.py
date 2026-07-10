"""
MASTER BOT — asosiy ishga tushiruvchi fayl.
"""
import asyncio
import logging
import httpx

from telegram.ext import ApplicationBuilder

from config import MASTER_BOT_TOKEN, PORT, WEBHOOK_BASE_URL, USE_WEBHOOK
from master_db import init_master_db
from user_flow import register_user_flow_handlers
from master_admin import register_admin_panel_handlers
import child_bot_manager as cbm
from scheduler import run_scheduler_loop

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def keep_alive_ping():
    """
    Render serverini hadep o'chib qolmasligi uchun har 10 daqiqada uyg'otib turuvchi funksiya.
    """
    if USE_WEBHOOK and WEBHOOK_BASE_URL:
        url = WEBHOOK_BASE_URL.rstrip('/')
        await asyncio.sleep(30)  # Server to'liq yuklanishini kutamiz
        
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    # Render o'z portimizga kelayotgan so'rovni ko'rishi uchun asosiy URL'ga ping beramiz
                    response = await client.get(url, timeout=10)
                    logger.info(f"⏰ Anti-Sleep ping muvaffaqiyatli: Status {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Anti-Sleep pingda xatolik: {e}")
            
            await asyncio.sleep(600)  # Har 10 daqiqada


async def post_init(application):
    await init_master_db()
    logger.info("Master DB tayyor.")

    # Server qayta ko'tarilganda child-botlarni ham qayta ishga tushirish
    asyncio.create_task(cbm.restart_all_active_bots())

    # Fon vazifasi (muddati tugaganlarni tekshirish)
    asyncio.create_task(run_scheduler_loop(application.bot))

    # O'chib qolmaslik tizimi
    asyncio.create_task(keep_alive_ping())


def main():
    if MASTER_BOT_TOKEN == "vghvhj":
        raise SystemExit(
            "❗ MASTER_BOT_TOKEN o'rnatilmagan. config.py yoki Environment Variable orqali bering."
        )

    app = ApplicationBuilder().token(MASTER_BOT_TOKEN).post_init(post_init).build()

    register_user_flow_handlers(app)
    register_admin_panel_handlers(app)

    if USE_WEBHOOK:
        logger.info(f"Master bot WEBHOOK rejimida {PORT}-portda ishga tushdi: {WEBHOOK_BASE_URL}")
        
        # run_webhook funksiyasi ichkarida avtomatik ravishda Tornado/Aiohttp serverini 
        # port orqali ochadi va tashqi so'rovlarni tinglaydi.
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,  # Render beradigan ichki PORT (odatda 10000)
            url_path="webhook",
            webhook_url=f"{WEBHOOK_BASE_URL}/webhook",
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("Master bot POLLING rejimida ishga tushdi (lokal test).")
        app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        main()
    finally:
        loop.close()
