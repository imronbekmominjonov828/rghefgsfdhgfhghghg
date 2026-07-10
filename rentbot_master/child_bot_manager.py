"""
CHILD BOT MANAGER — har bir mijozning o'z tokeni bilan alohida botini
bitta Python process ichida asyncio task sifatida ishga tushiradi/to'xtatadi.

Muhim: bitta child-bot xato qilsa (noto'g'ri token, internet uzilishi va h.k.),
bu Master botga yoki boshqa child-botlarga ta'sir qilmasligi kerak — shuning
uchun har biri alohida asyncio.Task va try/except bilan o'raladi.
"""
import asyncio
import logging
import os

from telegram.ext import Application

from config import CHILD_DB_DIR
import master_db as mdb

logger = logging.getLogger(__name__)

# Hozir ishlayotgan child-botlar: {client_id: {"app": Application, "task": asyncio.Task}}
running_bots: dict[int, dict] = {}

os.makedirs(CHILD_DB_DIR, exist_ok=True)


def get_child_db_path(client_id: int) -> str:
    return os.path.join(CHILD_DB_DIR, f"shop_{client_id}.db")


async def _run_child_bot(client_id: int, bot_token: str, shop_owner_id: int):
    """Bitta child-bot uchun to'liq lifecycle: build -> init -> polling -> (to'xtatilguncha kutish)."""
    from telegram.error import Forbidden, InvalidToken
    from child_bot.child_db import init_child_db, set_db_path, add_owner
    from child_bot.child_admin import register_child_admin_handlers
    from child_bot.child_user import register_child_user_handlers

    db_path = get_child_db_path(client_id)
    set_db_path(db_path)

    app = Application.builder().token(bot_token).build()

    register_child_admin_handlers(app)
    register_child_user_handlers(app)

    try:
        await init_child_db(db_path)
        # Botni sotib olgan kishi avtomatik 1-daraja (owner) sifatida qo'shiladi
        await add_owner(shop_owner_id, full_name="", username="")

        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])
        logger.info(f"[child:{client_id}] Bot ishga tushdi.")

        stop_event = running_bots[client_id]["stop_event"]
        await stop_event.wait()

    except (Forbidden, InvalidToken) as e:
        # Token noto'g'ri, yoki mijoz botni o'chirib/bloklab tashlagan
        logger.warning(f"[child:{client_id}] Token yaroqsiz/bot bloklangan: {e}")
        await mdb.suspend_client(client_id)
    except Exception as e:
        logger.error(f"[child:{client_id}] XATO: {e}")
    finally:
        try:
            await app.updater.stop()
        except Exception:
            pass
        try:
            await app.stop()
        except Exception:
            pass
        try:
            await app.shutdown()
        except Exception:
            pass
        running_bots.pop(client_id, None)
        logger.info(f"[child:{client_id}] Bot to'xtatildi.")


async def start_child_bot(client_id: int, bot_token: str, shop_owner_id: int) -> bool:
    """Yangi child-bot ishga tushiradi. Agar allaqachon ishlayotgan bo'lsa, avval to'xtatadi."""
    if client_id in running_bots:
        await stop_child_bot(client_id)

    stop_event = asyncio.Event()
    running_bots[client_id] = {"stop_event": stop_event, "task": None}

    task = asyncio.create_task(_run_child_bot(client_id, bot_token, shop_owner_id))
    running_bots[client_id]["task"] = task
    return True


async def stop_child_bot(client_id: int):
    """Child-botni to'xtatadi (masalan muddat tugaganda)."""
    entry = running_bots.pop(client_id, None)
    if not entry:
        return
    entry["stop_event"].set()
    task = entry.get("task")
    if task:
        try:
            await asyncio.wait_for(task, timeout=10)
        except (asyncio.TimeoutError, Exception):
            task.cancel()


async def restart_all_active_bots():
    """Server qayta ishga tushganda barcha aktiv mijozlarning botlarini qayta ko'taradi."""
    clients = await mdb.get_active_clients_with_tokens()
    for client_id, user_id, bot_token, bot_username, shop_owner_id in clients:
        try:
            await start_child_bot(client_id, bot_token, shop_owner_id)
            logger.info(f"[child:{client_id}] (@{bot_username}) qayta ishga tushirildi.")
        except Exception as e:
            logger.error(f"[child:{client_id}] qayta ishga tushirishda xato: {e}")


def is_bot_running(client_id: int) -> bool:
    return client_id in running_bots


def get_running_count() -> int:
    return len(running_bots)
