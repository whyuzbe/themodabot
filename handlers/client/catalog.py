from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from db.repos import Repos
from locales.texts import tt

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
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    text = await tt(repos, lang, "channel_not_ready")
    await call.answer(text, show_alert=True)


@router.callback_query(F.data.startswith("cat_switch:"))
async def cb_switch_catalog(call: CallbackQuery, repos: Repos):
    """Обработчик переключения между мужским/женским каталогом и возврата «в свой»"""
    # ИСПРАВЛЕНИЕ: раньше здесь пытались точечно редактировать сообщение через
    # call.message.edit_text(...) — но Telegram не позволяет менять текст у
    # сообщения с фото (баннером) методом edit_text, для этого нужен отдельный
    # edit_caption. Ошибка тихо проглатывалась в except, из-за чего при
    # переключении каталога баннер пропадал и не возвращался. Теперь просто
    # удаляем старое сообщение и заново отправляем каталог через
    # show_catalog_entry — ту же функцию, что и при первом входе, она уже
    # корректно обрабатывает и баннер, и текст без картинки.
    from handlers.client.start import show_catalog_entry

    user = await repos.users.get(call.from_user.id)
    if not user:
        await call.answer("Ошибка: пользователь не найден", show_alert=True)
        return

    target = call.data.split(":")[1]
    override_gender = None if target == "home" else target

    try:
        await call.message.delete()
    except Exception:
        pass

    await show_catalog_entry(call.message, user, repos, override_gender=override_gender)
    await call.answer()
