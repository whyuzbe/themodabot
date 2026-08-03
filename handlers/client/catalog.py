from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from db.repos import Repos
from keyboards.client_kb import kb_categories

# Объявляем router, чтобы main и __init__.py его видели
router = Router()


async def _category_urls(repos: Repos, gender: str) -> dict:
    """
    Возвращает {category: invite_url} для конкретного пола,
    используя реальные данные из BrandsRepo (таблица gender_channels).
    Категории без настроенного канала просто не попадают в словарь —
    для них kb_categories покажет кнопку с callback_data="cat_no_channel:...".
    """
    urls: dict[str, str] = {}
    try:
        channels = await repos.brands.list_channels()
        for ch in channels:
            if ch.get("gender") == gender and ch.get("invite_url"):
                urls[ch["category"]] = ch["invite_url"]
    except Exception:
        pass
    return urls


@router.callback_query(F.data.startswith("cat_no_channel:"))
async def cb_category_no_channel(call: CallbackQuery, repos: Repos):
    """
    Категория есть в CATEGORIES, но для неё ещё не настроен канал
    (invite_url) в таблице gender_channels — сообщаем пользователю,
    вместо того чтобы кнопка молча "проглатывала" нажатие.
    """
    await call.answer(
        "🚧 Этот раздел пока не готов, загляните позже!",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("cat_switch:"))
async def cb_switch_catalog(call: CallbackQuery, repos: Repos):
    """Обработчик переключения между мужским/женским каталогом и возврата «в свой»"""
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
