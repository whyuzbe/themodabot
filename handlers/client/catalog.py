from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from db.repos import Repos
from translate import tr
from keyboards.client_kb import kb_categories
from config import CATEGORIES
from utils import with_warehouse_button
from filters import ButtonText

router = Router()


async def _category_urls(repos: Repos, gender: str) -> dict[str, str | None]:
    """Для каждой категории этого пола — прямая ссылка на её канал (если настроен)."""
    urls = {}
    for key in CATEGORIES[gender]:
        channel = await repos.brands.get_channel(gender, key)
        urls[key] = channel["invite_url"] if channel else None
    return urls


async def _show_categories(target_message, repos: Repos, own_gender: str, display_gender: str, lang: str, edit: bool):
    show_other = display_gender != own_gender
    text = await repos.texts.get(f"text_opening_{lang}")
    urls = await _category_urls(repos, display_gender)
    kb = await kb_categories(repos, lang, own_gender, urls, show_other)
    kb = await with_warehouse_button(kb, repos, display_gender, lang)
    if edit:
        await target_message.edit_text(text, reply_markup=kb)
    else:
        await target_message.answer(text, reply_markup=kb)


@router.message(ButtonText("btn_catalog"))
async def msg_catalog(message: Message, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    if not user:
        return
    lang = user.get("language", "ru")
    gender = user.get("gender", "male")
    await _show_categories(message, repos, gender, gender, lang, edit=False)


# ── Назад к категориям / переключение на каталог другого пола ─────────
# Категория = сразу прямая ссылка на канал (клиент сам видит топики в Telegram,
# списка разделов внутри бота больше нет). Этот хендлер только переключает,
# чей каталог категорий показываем — свой или противоположного пола.

@router.callback_query(F.data.startswith("cat_back:"))
async def cb_category_back(call: CallbackQuery, repos: Repos):
    display_gender = call.data.split(":")[1]
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    own_gender = user.get("gender", "male") if user else "male"
    await _show_categories(call.message, repos, own_gender, display_gender, lang, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("cat_no_channel:"))
async def cb_category_no_channel(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    msg = await tr(repos, "❌ Канал для этой категории не настроен. Обратитесь к менеджеру.", lang)
    await call.answer(msg, show_alert=True)