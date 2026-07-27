from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from db.repos import Repos

# Объявляем router, чтобы main и __init__.py его видели
router = Router()


async def _category_urls(repos: Repos, gender: str) -> dict:
    """Вспомогательная функция для получения ссылок/состояний категорий"""
    try:
        if hasattr(repos, "categories"):
            return await repos.categories.get_urls(gender)
    except Exception:
        pass
    return {}


@router.callback_query(F.data.startswith("cat:"))
async def cb_category_select(call: CallbackQuery, repos: Repos):
    """Обработчик выбора категории в каталоге"""
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    cat_id = call.data.split(":")[1]

    # Здеь выводится список товаров или подкатегорий
    await call.answer()
