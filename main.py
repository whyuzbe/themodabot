import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent
from redis.asyncio import Redis

from config import config
from db.pool import DB
from db.repos import Repos
from middlewares import RepoMiddleware

from handlers.staff import auth as staff_auth
from handlers.staff import manager as staff_manager
from handlers.staff import admin as staff_admin
from handlers.staff import warehouse as staff_warehouse
from handlers.staff import partner as staff_partner
from handlers.client import start as client_start
from handlers.client import catalog as client_catalog
from handlers.client import cart as client_cart
from handlers.client import profile as client_profile
from handlers.client import support as client_support

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


async def main():
    db = DB(config.DB_DRIVER, config.db_dsn_or_path)
    await db.connect()
    await db.init_schema()

    repos = Repos(db)
    await staff_auth.ensure_bootstrap_manager(repos)

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Подключаем RedisStorage для устойчивости к высоким нагрузкам
    redis = Redis.from_url(config.REDIS_URL)
    dp = Dispatcher(storage=RedisStorage(redis=redis))

    repo_mw = RepoMiddleware(repos)
    dp.message.outer_middleware(repo_mw)
    dp.callback_query.outer_middleware(repo_mw)

    @dp.errors()
    async def errors_handler(event: ErrorEvent):
        exc = event.exception
        # Безвредная ошибка: пользователь нажал кнопку, ведущую на тот же текст/клавиатуру.
        if isinstance(exc, TelegramBadRequest) and "message is not modified" in str(exc):
            return True
        logger.exception("Необработанная ошибка в хендлере", exc_info=exc)
        return True

    # Порядок важен: стафф-роутеры первыми (свои команды /admin /manager /warehouse),
    # затем клиентские.
    dp.include_router(staff_auth.router)
    dp.include_router(staff_manager.router)
    dp.include_router(staff_admin.router)
    dp.include_router(staff_warehouse.router)
    dp.include_router(staff_partner.router)

    dp.include_router(client_start.router)
    dp.include_router(client_profile.router)
    dp.include_router(client_catalog.router)
    dp.include_router(client_cart.router)
    dp.include_router(client_support.router)

    logger.info("Бот запущен ✅")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())