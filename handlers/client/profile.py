from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.repos import Repos
from locales.texts import t, tt
from keyboards.client_kb import (
    kb_profile, kb_gender, kb_language_profile, kb_share_phone, kb_remove,
)
from utils import client_menu_kb
from filters import ButtonText

router = Router()


class ProfileStates(StatesGroup):
    changing_phone = State()


async def _gender_label(repos, lang, gender):
    return await tt(repos, lang, "male") if gender == "male" else await tt(repos, lang, "female")


def _lang_label(lang):
    # Названия языков — собственные имена, не переводятся (см. keyboards/client_kb.py)
    key = f"lang_{lang}" if lang in ("ru", "en", "uk", "es") else "lang_ru"
    return t(lang, key)


async def _send_profile(repos, obj, lang, user, edit=False):
    header = await tt(repos, lang, "profile_header")
    phone_label = await tt(repos, lang, "label_phone")
    gender_label = await tt(repos, lang, "label_gender")
    language_label = await tt(repos, lang, "label_language")
    gender_value = await _gender_label(repos, lang, user.get("gender", "male"))

    text = (
        f"{header}\n\n"
        f"📱 {phone_label}: <code>{user.get('phone') or '—'}</code>\n"
        f"⚧ {gender_label}: {gender_value}\n"
        f"🌐 {language_label}: {_lang_label(lang)}"
    )
    kb = await kb_profile(repos, lang)
    if edit and hasattr(obj, "message"):
        await obj.message.edit_text(text, reply_markup=kb)
    else:
        msg = obj.message if hasattr(obj, "message") else obj
        await msg.answer(text, reply_markup=kb)


@router.message(ButtonText("btn_profile"))
async def msg_profile(message: Message, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    if not user:
        return
    await _send_profile(repos, message, user.get("language", "ru"), user)


@router.callback_query(F.data == "profile:change_gender")
async def cb_change_gender(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    text = await tt(repos, lang, "choose_new_gender")
    kb = await kb_gender(repos, lang, back_cb="go:profile")
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("gender:"))
async def cb_set_gender(call: CallbackQuery, state: FSMContext, repos: Repos):
    current = await state.get_state()
    if current is not None and "RegStates" in str(current):
        await call.answer()
        return

    user = await repos.users.get(call.from_user.id)
    if not user:
        await call.answer()
        return

    lang = user.get("language", "ru")
    gender = call.data.split(":")[1]
    await repos.users.update(call.from_user.id, gender=gender)
    user["gender"] = gender

    changed_text = await tt(repos, lang, "gender_changed")
    await call.answer(changed_text, show_alert=True)
    await _send_profile(repos, call, lang, user, edit=True)


@router.callback_query(F.data == "profile:change_language")
async def cb_change_language(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    text = await tt(repos, lang, "choose_new_language")
    await call.message.edit_text(text, reply_markup=kb_language_profile(lang))
    await call.answer()


@router.callback_query(F.data.startswith("profile_lang:"))
async def cb_set_language(call: CallbackQuery, repos: Repos):
    new_lang = call.data.split(":")[1]
    await repos.users.update(call.from_user.id, language=new_lang)
    changed_text = await tt(repos, new_lang, "language_changed")
    await call.answer(changed_text, show_alert=True)
    await call.message.delete()
    main_menu_text = await tt(repos, new_lang, "main_menu")
    await call.message.answer(main_menu_text, reply_markup=await client_menu_kb(repos, call.from_user.id, new_lang))


@router.callback_query(F.data == "profile:change_phone")
async def cb_change_phone(call: CallbackQuery, state: FSMContext, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    await state.set_state(ProfileStates.changing_phone)
    await state.update_data(lang=lang)
    ask_text = await tt(repos, lang, "ask_new_phone")
    await call.message.edit_text(ask_text)
    await call.message.answer(ask_text, reply_markup=await kb_share_phone(repos, lang))
    await call.answer()


@router.message(ProfileStates.changing_phone, F.contact)
async def msg_new_phone(message: Message, state: FSMContext, repos: Repos):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await repos.users.update(message.from_user.id, phone=message.contact.phone_number)
    await state.clear()

    user = await repos.users.get(message.from_user.id)
    phone_changed_text = await tt(repos, lang, "phone_changed")
    main_menu_text = await tt(repos, lang, "main_menu")
    await message.answer(phone_changed_text, reply_markup=kb_remove())
    await message.answer(main_menu_text, reply_markup=await client_menu_kb(repos, message.from_user.id, lang))
    await _send_profile(repos, message, lang, user)


@router.message(ProfileStates.changing_phone)
async def msg_new_phone_invalid(message: Message, state: FSMContext, repos: Repos):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await message.answer(await tt(repos, lang, "invalid_phone"))


@router.callback_query(F.data == "go:profile")
async def cb_go_profile(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    if not user:
        await call.answer()
        return
    await _send_profile(repos, call, user.get("language", "ru"), user, edit=True)
    await call.answer()