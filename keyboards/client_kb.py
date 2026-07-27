from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from locales.texts import t, tt
from config import CATEGORIES


def kb_language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang:uk"),
         InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang:es")],
    ])


async def kb_gender(repos, lang: str, back_cb: str | None = None) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=await tt(repos, lang, "male"), callback_data="gender:male"),
        InlineKeyboardButton(text=await tt(repos, lang, "female"), callback_data="gender:female"),
    ]]
    if back_cb:
        rows.append([InlineKeyboardButton(text=await tt(repos, lang, "btn_back"), callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def kb_share_phone(repos, lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=await tt(repos, lang, "share_contact_btn"), request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def kb_remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


async def kb_main_menu(repos, lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=await tt(repos, lang, "btn_catalog"))],
            [KeyboardButton(text=await tt(repos, lang, "btn_cart")), KeyboardButton(text=await tt(repos, lang, "btn_wishlist"))],
            [KeyboardButton(text=await tt(repos, lang, "btn_my_order")), KeyboardButton(text=await tt(repos, lang, "btn_order_history"))],
            [KeyboardButton(text=await tt(repos, lang, "btn_support")), KeyboardButton(text=await tt(repos, lang, "btn_profile"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


async def kb_categories(repos, lang: str, gender: str, urls: dict[str, str | None], show_other: bool = False) -> InlineKeyboardMarkup:
    # Если show_other == True, значит мы смотрим противоположный каталог
    current_gender = ("female" if gender == "male" else "male") if show_other else gender

    cats = CATEGORIES
    if isinstance(cats, dict):
        category_keys = cats.get(current_gender, [])
    else:
        category_keys = cats

    # Иконки строго привязаны к отображаемому полу (current_gender)
    male_names = {
        "Одежда": "🧥 Мужская одежда",
        "Обувь": "👟 Мужская обувь",
        "Аксессуары": "🕶 Мужские аксессуары",
        "Сумки": "💼 Мужские сумки",
    }

    female_names = {
        "Одежда": "👗 Женская одежда",
        "Обувь": "👠 Женская обувь",
        "Аксессуары": "💍 Женские аксессуары",
        "Сумки": "👜 Женские сумки",
    }

    current_names = female_names if current_gender == "female" else male_names

    rows = []
    for key in category_keys:
        text = current_names.get(key, f"📦 {key}")
        url = urls.get(key)
        if url:
            rows.append([InlineKeyboardButton(text=text, url=url)])
        else:
            rows.append([InlineKeyboardButton(text=text, callback_data=f"cat_no_channel:{current_gender}:{key}")])

    # Кнопка переключения между каталогами и возврата
    if show_other:
        # Если мы в чужом каталоге, кнопка должна возвращать в «свой» базовый каталог пользователя
        back_text = "🔙 В свой каталог"
        rows.append([InlineKeyboardButton(text=back_text, callback_data=f"cat_back:{gender}")])
    else:
        # Если мы в своем каталоге, предлагаем посмотреть противоположный
        opposite = "female" if gender == "male" else "male"
        other_text = "👗 Женский каталог" if gender == "male" else "👔 Мужской каталог"
        rows.append([InlineKeyboardButton(text=other_text, callback_data=f"cat_back:{opposite}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def kb_profile(repos, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_change_gender"), callback_data="profile:change_gender")],
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_change_language"), callback_data="profile:change_language")],
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_change_phone"), callback_data="profile:change_phone")],
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_back"), callback_data="go:main")],
    ])


def kb_language_profile(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "lang_ru"), callback_data="profile_lang:ru"),
         InlineKeyboardButton(text=t(lang, "lang_en"), callback_data="profile_lang:en")],
        [InlineKeyboardButton(text=t(lang, "lang_uk"), callback_data="profile_lang:uk"),
         InlineKeyboardButton(text=t(lang, "lang_es"), callback_data="profile_lang:es")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="go:profile")],
    ])


async def kb_cart(repos, lang: str, items: list[dict]) -> InlineKeyboardMarkup:
    fallback_title = await tt(repos, lang, "fallback_item_title")
    rows = []
    for item in items:
        title = (item.get("title") or fallback_title)[:28]
        price = item.get("price") or "—"
        rows.append([InlineKeyboardButton(
            text=f"🗑 {title} | {price}", callback_data=f"cart:remove:{item['cart_id']}"
        )])
    rows.append([
        InlineKeyboardButton(text=await tt(repos, lang, "btn_checkout"), callback_data="cart:checkout"),
        InlineKeyboardButton(text=await tt(repos, lang, "btn_clear"), callback_data="cart:clear"),
    ])
    rows.append([InlineKeyboardButton(text=await tt(repos, lang, "btn_back"), callback_data="go:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def kb_wishlist(repos, lang: str, items: list[dict]) -> InlineKeyboardMarkup:
    fallback_title = await tt(repos, lang, "fallback_item_title")
    rows = []
    for item in items:
        title = (item.get("title") or fallback_title)[:24]
        rows.append([
            InlineKeyboardButton(text="🛒", callback_data=f"wish:to_cart:{item['wish_id']}"),
            InlineKeyboardButton(text=f"🗑 {title}", callback_data=f"wish:remove:{item['wish_id']}"),
        ])
    rows.append([InlineKeyboardButton(text=await tt(repos, lang, "btn_back"), callback_data="go:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def kb_after_add(repos, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_cart"), callback_data="go:cart"),
         InlineKeyboardButton(text=await tt(repos, lang, "btn_wishlist"), callback_data="go:wishlist")],
        [InlineKeyboardButton(text=await tt(repos, lang, "main_menu"), callback_data="go:main")],
    ])


def kb_order_confirm(order_id: int, verified: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if verified:
        rows.append([InlineKeyboardButton(text="✅ Клиент подтвердил — оформить", callback_data=f"order:confirm:{order_id}")])
    else:
        rows.append([InlineKeyboardButton(text="📞 Уточнить у клиента", callback_data=f"order:verify:{order_id}")])
        rows.append([InlineKeyboardButton(text="✅ Подтвердить без уточнения", callback_data=f"order:confirm:{order_id}")])
    rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data=f"order:cancel:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def kb_client_verify(repos, lang: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_all_correct"), callback_data=f"client:verify_ok:{order_id}")],
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_need_fix"), callback_data=f"client:verify_fix:{order_id}")],
    ])


async def kb_my_order(repos, lang: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tt(repos, lang, "btn_edit_order"), callback_data=f"myorder:edit:{order_id}")],
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"myorder:cancel:{order_id}")],
    ])
