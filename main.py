import asyncio
import logging
import datetime
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis

# Конфигурация
from config import BOT_TOKEN, REDIS_URL, DATABASE_URL, DB_DRIVER
from db.pool import DB
from db.repos import Repos
from handlers.staff.auth import ensure_bootstrap_manager

# Импортируем главный роутер со всеми подключенными хэндлерами
from handlers import router as main_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cart_expiration_checker(bot: Bot, repos: Repos):
    """Фоновая задача: раз в минуту очищает товары из корзины, которые пролежали > 45 минут"""
    while True:
        try:
            await asyncio.sleep(60)
            expired_items = await repos.cart.clear_expired(minutes="45")
            # или minutes="45 minutes", в зависимости от того, как написан твой SQL-запрос внутри функции clear_expired

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
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Ошибка в фоновой проверке корзины: {e}")


async def deficit_reminder_checker(bot: Bot, repos: Repos):
    """
    Раз в день (около 20:00 по времени сервера) напоминает всем сотрудникам
    склада проверить дефицитные товары, если такие есть — по аналогии с идеей
    из cart_expiration_checker, но раз в сутки, а не каждую минуту.
    Отправляет всем складским аккаунтам с привязанным tg_id (не только тем,
    у кого сейчас активна сессия), чтобы напоминание точно дошло, даже если
    сотрудник в этот момент не залогинен в панель.
    """
    reminded_date = None
    while True:
        try:
            await asyncio.sleep(600)  # проверяем раз в 10 минут, шлём — раз в день
            now = datetime.datetime.now()
            if now.hour == 20 and reminded_date != now.date():
                items = await repos.posts.deficit_summary()
                if items:
                    warehouse_staff = await repos.staff.list_by_role("warehouse")
                    text = (
                        f"🚨 <b>Напоминание: {len(items)} дефицитных позиций</b>\n\n"
                        "Загляните в «🚨 Дефицит» в панели склада и закажите то, чего не хватает."
                    )
                    for wh in warehouse_staff:
                        if wh.get("tg_id"):
                            try:
                                await bot.send_message(wh["tg_id"], text)
                            except Exception:
                                pass
                reminded_date = now.date()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Ошибка в напоминании о дефиците: {e}")


async def main():
    # ВРЕМЕННАЯ ДИАГНОСТИКА: показываем в логах длину токена и первые/последние
    # символы, чтобы понять, действительно ли процесс видит тот токен, что в Railway.
    # Полный токен в лог не пишем из соображений безопасности.
    if BOT_TOKEN:
        logger.info(
            f"🔍 DEBUG BOT_TOKEN: len={len(BOT_TOKEN)} "
            f"start={BOT_TOKEN[:12]!r} end={BOT_TOKEN[-6:]!r}"
        )
    else:
        logger.info("🔍 DEBUG BOT_TOKEN: пусто/None")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключение к базе данных и Redis
    db = DB(driver=DB_DRIVER, dsn_or_path=DATABASE_URL)
    await db.connect()
    # ИСПРАВЛЕНИЕ: init_schema() (создание таблиц + все ALTER TABLE миграции
    # в _migrate()) раньше нигде не вызывался при старте бота. На текущей базе
    # это не проявлялось, т.к. схема уже была создана вручную ранее, но при
    # деплое на чистую БД бот бы не создал ни одной таблицы, а будущие
    # миграции (новые колонки) никогда бы не применялись автоматически.
    # _migrate() написан безопасно для повторных вызовов, поэтому вызывать
    # его при каждом старте — нормально.
    await db.init_schema()

    redis = Redis.from_url(REDIS_URL) if REDIS_URL else None
    repos = Repos(db, redis=redis)

    # ИСПРАВЛЕНИЕ: создаём стартовый аккаунт manager/<пароль из .env>,
    # если в staff_accounts ещё нет ни одного менеджера.
    # Без этого вызова аккаунт из BOOTSTRAP_MANAGER_LOGIN/PASSWORD
    # никогда не появляется в базе.
    await ensure_bootstrap_manager(repos)

    # Прокидываем зависимости в контекст диспетчера
    dp["repos"] = repos
    dp["redis"] = redis

    # Подключаем роутеры
    dp.include_router(main_router)

    # Запускаем фоновую очистку просроченных броней
    checker_task = asyncio.create_task(cart_expiration_checker(bot, repos))
    # Запускаем фоновое ежедневное напоминание складу о дефиците
    deficit_task = asyncio.create_task(deficit_reminder_checker(bot, repos))

    try:
        logger.info("🚀 Бот успешно запущен!")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        checker_task.cancel()
        deficit_task.cancel()
        await db.close()
        if redis:
            await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
