from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from db.repos import Repos
from keyboards.client_kb import kb_categories

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

    # Здесь выводится список товаров или подкатегорий
    await call.answer()


@router.callback_query(F.data.startswith("cat_switch:"))
async def cb_switch_catalog(call: CallbackQuery, repos: Repos):
    """ИСПРАВЛЕНИЕ: Обработчик переключения между мужским/женским каталогом и возврата «в свой»"""
    user = await repos.users.get(call.from_user.id)
    if not user:
        await call.answer("Ошибка: пользователь не найден", show_alert=True)
        return

    lang = user.get("language", "ru")
    user_gender = user.get("gender", "male")
    
    target = call.data.split(":")[1]
    
    # Определяем, какой каталог показывать
    if target == "home":
        # Возвращаем в родной каталог пользователя
        show_other = False
        active_gender = user_gender
    else:
        # Переходим в противоположный каталог
        show_other = True
        active_gender = target

    urls = await _category_urls(repos, active_gender)
    keyboard = await kb_categories(repos, lang, user_gender, urls, show_other=show_other)

    text = "🛍 Выберите интересующую вас категорию:"
    
    try:
        await call.message.edit_text(text=text, reply_markup=keyboard)
    except Exception:
        pass
    
    await call.answer()
