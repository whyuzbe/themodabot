from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.repos import Repos
from locales.texts import t, tt
from keyboards.client_kb import kb_language, kb_gender, kb_categories
from utils import client_menu_kb, with_warehouse_button
from translate import tr

router = Router()


class RegStates(StatesGroup):
    choosing_language = State()
    choosing_gender = State()


async def show_catalog_entry(message: Message, user: dict | None, repos: Repos, override_gender: str | None = None):
    """Открыть опенинг с категориями (после регистрации / по кнопке Каталог / переключение полов)."""
    from handlers.client.catalog import _category_urls

    user = user or {}
    lang = user.get("language", "ru")
    gender = override_gender or user.get("gender", "male")
    
    opening_text = await repos.texts.get(f"text_opening_{lang}")
    if not opening_text:
        opening_text = await tt(repos, lang, "btn_catalog")
        
    banner_file_id = await repos.settings.get("settings_banner_file_id")
    if not banner_file_id:
        banner_file_id = await repos.settings.get("banner_file_id")

    show_other = override_gender is not None and override_gender != user.get("gender", "male")
    urls = await _category_urls(repos, gender)
    
    # Получаем клавиатуру и принудительно заменяем тексты на кнопках прямо здесь (гарантия от старого кэша)
    kb = await kb_categories(repos, lang, gender, urls, show_other=show_other)
    
    icon_map = {
        "clothing": "👕 Одежда",
        "shoes": "👟 Обувь",
        "accessories": "💍 Аксессуары",
        "bags": "👜 Сумки"
    }
    
    for row in kb.inline_keyboard:
        for btn in row:
            for key, val in icon_map.items():
                if key in btn.callback_data:
                    btn.text = val

    kb = await with_warehouse_button(kb, repos, gender, lang)

    try:
        if banner_file_id:
            await message.answer_photo(banner_file_id, caption=opening_text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(opening_text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        clean_text = opening_text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        await message.answer(clean_text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    await state.clear()

    user = await repos.users.get(message.from_user.id)

    if user and user.get("is_blocked"):
        lang = user.get("language", "ru")
        await message.answer(await tt(repos, lang, "blocked"))
        return

    args = message.text.split()
    payload = args[1] if len(args) > 1 else ""

    if payload.startswith("ref_"):
        ref_code = payload[len("ref_"):]
        partner = await repos.staff.get_by_ref_code(ref_code)
        if partner:
            await repos.partners.register_referral(partner["login"], message.from_user.id)

    if user and user.get("gender"):
        lang = user.get("language", "ru")
        if payload.startswith(("cart_", "wish_", "interest_")):
            from handlers.client.cart import handle_deeplink
            await handle_deeplink(message, payload, repos)
            return
        main_menu_text = await tt(repos, lang, "main_menu")
        await message.answer(main_menu_text, reply_markup=await client_menu_kb(repos, message.from_user.id, lang))
        await show_catalog_entry(message, user, repos)
        return

    welcome_parts = []
    for code in ("ru", "en", "uk", "es"):
        part = await repos.texts.get(f"text_welcome_{code}")
        if part:
            welcome_parts.append(part)
            
    if welcome_parts:
        welcome_text = "\n\n".join(welcome_parts)
    else:
        welcome_text = "Welcome / Добро пожаловать / Вітаємо / Bienvenidos"

    await state.update_data(pending_payload=payload)
    await state.set_state(RegStates.choosing_language)
    await message.answer(welcome_text, reply_markup=kb_language(), parse_mode="HTML")


@router.callback_query(RegStates.choosing_language, F.data.startswith("lang:"))
async def cb_choose_language(call: CallbackQuery, state: FSMContext, repos: Repos):
    lang = call.data.split(":")[1]
    await state.update_data(language=lang)
    await repos.users.create(call.from_user.id, call.from_user.username, lang)

    choose_gender_text = await tt(repos, lang, "choose_gender")
    await call.message.edit_text(choose_gender_text, reply_markup=await kb_gender(repos, lang), parse_mode="HTML")
    await state.set_state(RegStates.choosing_gender)
    await call.answer()


@router.callback_query(RegStates.choosing_gender, F.data.startswith("gender:"))
async def cb_choose_gender(call: CallbackQuery, state: FSMContext, repos: Repos):
    data = await state.get_data()
    lang = data.get("language", "ru")
    payload = data.get("pending_payload", "")
    gender = call.data.split(":")[1]

    await repos.users.update(call.from_user.id, gender=gender)
    await state.clear()

    registered_ok_text = await tt(repos, lang, "registered_ok")
    main_menu_text = await tt(repos, lang, "main_menu")
    await call.message.edit_text(registered_ok_text, parse_mode="HTML")
    await call.message.answer(main_menu_text, reply_markup=await client_menu_kb(repos, call.from_user.id, lang))

    if payload.startswith(("cart_", "wish_", "interest_")):
        from handlers.client.cart import handle_deeplink
        await handle_deeplink(call.message, payload, repos, user_tg_id=call.from_user.id)
        await call.answer()
        return

    user = await repos.users.get(call.from_user.id)
    await show_catalog_entry(call.message, user, repos)
    await call.answer()


@router.callback_query(F.data == "go:main")
async def cb_go_main(call: CallbackQuery, state: FSMContext, repos: Repos):
    await state.clear()
    user = await repos.users.get(call.from_user.id)
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_catalog_entry(call.message, user, repos)
    await call.answer()


@router.callback_query(F.data.startswith("cat_back:"))
async def cb_cat_back(call: CallbackQuery, repos: Repos):
    target_gender = call.data.split(":")[1]
    user = await repos.users.get(call.from_user.id)
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_catalog_entry(call.message, user, repos, override_gender=target_gender)
    await call.answer()


@router.message(Command("dell_num"))
async def cmd_dell_num(message: Message, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    if not user:
        await message.answer(await tr(repos, "ℹ️ У вас ещё нет аккаунта в боте.", lang))
        return

    text = await tr(
        repos,
        "⚠️ Вы уверены, что хотите удалить свой аккаунт?\n\n"
        "Будут стёрты: ваш профиль, корзина, сохранённые товары и сохранённые размеры.\n"
        "Это действие нельзя отменить.",
        lang,
    )
    yes_btn = await tr(repos, "✅ Да, удалить", lang)
    no_btn = await tr(repos, "❌ Отмена", lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=yes_btn, callback_data="dell_num:confirm"),
        InlineKeyboardButton(text=no_btn, callback_data="dell_num:cancel"),
    ]])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "dell_num:cancel")
async def cb_dell_num_cancel(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    await call.message.edit_text(await tr(repos, "Отменено. Аккаунт не удалён.", lang))
    await call.answer()


@router.callback_query(F.data == "dell_num:confirm")
async def cb_dell_num_confirm(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    deleted = await repos.users.delete_account(call.from_user.id)

    if deleted:
        msg = await tr(
            repos,
            "✅ Ваш аккаунт удалён. Чтобы начать заново, отправьте /start.",
            lang,
        )
        await call.message.edit_text(msg)
        try:
            await call.message.answer("👋", reply_markup=ReplyKeyboardRemove())
        except Exception:
            pass
    else:
        await call.message.edit_text(await tr(repos, "❌ Не удалось удалить аккаунт.", lang))
    await call.answer()
