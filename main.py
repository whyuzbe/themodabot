import asyncio
import logging
from aiogram import Bot, Dispatcher
from redis.asyncio import Redis

# Переменные окружения
from config import BOT_TOKEN, REDIS_URL, DATABASE_URL, DB_DRIVER
from db.pool import DB
from db.repos import Repos

# Импортируем модуль handlers
import handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cart_expiration_checker(bot: Bot, repos: Repos):
    """Фоновая задача: раз в минуту очищает товары из корзины, которые пролежали > 45 минут"""
    while True:
        try:
            await asyncio.sleep(60)
            expired_items = await repos.cart.clear_expired(minutes=45)

            if expired_items:
                logger.info(f"⏳ Снята бронь с {len(expired_items)} товаров в корзинах.")
                for item in expired_items:
                    user_id = item["user_tg_id"]
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                "⏳ <b>Время брони истекло</b>\n\n"
                                "Товар из вашей корзины вернулся в общий каталог, так как время ожидания (45 мин) завершилось.\n\n"
                                "💡 <i>Вы всегда можете повторно добавить его из каталога или Избранного!</i>"
                            ),
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Ошибка в фоновой проверке корзины: {e}")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Подключение к базе данных и Redis
    db = DB(driver=DB_DRIVER, dsn_or_path=DATABASE_URL)
    await db.connect()

    redis = Redis.from_url(REDIS_URL) if REDIS_URL else None
    repos = Repos(db, redis=redis)

    # Прокидываем зависимости в контекст диспетчера
    dp["repos"] = repos
    dp["redis"] = redis

    # Подключаем роутеры из модуля handlers, если в __init__.py есть функция setup/router или список
    if hasattr(handlers, "router"):
        dp.include_router(handlers.router)
    elif hasattr(handlers, "setup_routers"):
        handlers.setup_routers(dp)

    # Запускаем фоновую очистку просроченных броней
    checker_task = asyncio.create_task(cart_expiration_checker(bot, repos))

    try:
        logger.info("🚀 Бот успешно запущен!")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        checker_task.cancel()
        await db.close()
        if redis:
            await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
