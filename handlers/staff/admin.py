from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

from config import CATEGORIES
from db.repos import Repos
from handlers.staff.auth import require_role
from utils import safe_edit

router = Router()


# ── Шаблоны постов по типу товара (публикуются в каналы — ТОЛЬКО на английском) ──
# Ключ: (gender, category). Для каждого — свой заголовок/эмодзи/CTA, чтобы пост не
# выглядел сухим шаблоном, а был "живым" и продающим.
#
# ИСПРАВЛЕНИЕ: ключи категорий здесь были на английском ("clothes"/"shoes"/...),
# а реальные категории в проекте — на русском (см. config.CATEGORIES:
# "Одежда"/"Обувь"/"Аксессуары"/"Сумки"). Из-за несовпадения POST_TEMPLATES.get()
# никогда не находил нужный шаблон и всегда падал на generic-заглушку.
# Также добавлен отсутствовавший шаблон для мужских сумок (категория "Сумки"
# есть и у мужского, и у женского пола в config.CATEGORIES).
POST_TEMPLATES = {
    ("male", "Одежда"): {
        "emoji": "👔", "heading": "NEW MEN'S ARRIVAL",
        "cta": "🔥 Fresh fit, limited pieces — don't sleep on it!",
    },
    ("male", "Обувь"): {
        "emoji": "👟", "heading": "FRESH KICKS JUST DROPPED",
        "cta": "🔥 Grab your size before they're gone!",
    },
    ("male", "Аксессуары"): {
        "emoji": "⌚️", "heading": "NEW ACCESSORY DROP",
        "cta": "✨ The detail that finishes the look — get it now!",
    },
    ("male", "Сумки"): {
        "emoji": "🎒", "heading": "NEW BAG JUST LANDED",
        "cta": "🔥 Only a few in stock — secure yours now!",
    },
    ("female", "Одежда"): {
        "emoji": "👗", "heading": "NEW WOMEN'S ARRIVAL",
        "cta": "🔥 Stunning piece, very limited quantity!",
    },
    ("female", "Обувь"): {
        "emoji": "👠", "heading": "NEW HEELS IN STOCK",
        "cta": "🔥 Step up your style — order before it sells out!",
    },
    ("female", "Аксессуары"): {
        "emoji": "💍", "heading": "NEW ACCESSORY DROP",
        "cta": "✨ The perfect finishing touch — yours today!",
    },
    ("female", "Сумки"): {
        "emoji": "👜", "heading": "NEW BAG JUST LANDED",
        "cta": "🔥 Only a few in stock — secure yours now!",
    },
}


def build_post_caption(gender: str, category: str, brand: dict, title: str,
                        size: str | None, price: str, description: str | None) -> str:
    """Собирает финальный текст поста для канала — строго на английском."""
    tpl = POST_TEMPLATES.get((gender, category), {
        "emoji": "🛍", "heading": "NEW ARRIVAL", "cta": "🔥 Don't miss out!",
    })
    lines = [f"{tpl['emoji']} <b>{tpl['heading']}</b>", "", f"<b>{brand['emoji']} {brand['name']} — {title}</b>"]
    if size:
        lines.append(f"📏 Size: {size}")
    lines.append(f"💰 Price: {price}")
    if description:
        lines += ["", description]
    lines += ["", tpl["cta"]]
    return "\n".join(lines)


def kb_admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Заказы", callback_data="adm:orders")],
        [InlineKeyboardButton(text="📝 Создать пост", callback_data="adm:new_post")],
        [InlineKeyboardButton(text="🎧 Поддержка", callback_data="adm:support")],
        [InlineKeyboardButton(text="📣 Рассылка", callback_data="adm:broadcast_menu")],
        [InlineKeyboardButton(text="📊 Мои публикации", callback_data="adm:my_posts")],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="adm:logout")],
    ])


def kb_back_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:panel_back")]])


def kb_gender_post() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="post_gender:male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="post_gender:female")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:panel_back")],
    ])


# ИСПРАВЛЕНИЕ: раньше был доступ CATEGORIES[gender].items() — но CATEGORIES[gender]
# это список строк ("Одежда", "Обувь", ...), а не словарь, у списков нет .items().
# Это гарантированно роняло весь флоу "Создать пост" сразу после выбора пола
# (AttributeError: 'list' object has no attribute 'items'). Теперь — обычная
# итерация по списку + красивые подписи с эмодзи через CATEGORY_POST_LABELS.
CATEGORY_POST_LABELS = {
    ("male", "Одежда"): "👔 Мужская одежда",
    ("male", "Обувь"): "👟 Мужская обувь",
    ("male", "Аксессуары"): "⌚️ Мужские аксессуары",
    ("male", "Сумки"): "🎒 Мужские сумки",
    ("female", "Одежда"): "👗 Женская одежда",
    ("female", "Обувь"): "👠 Женская обувь",
    ("female", "Аксессуары"): "💍 Женские аксессуары",
    ("female", "Сумки"): "👜 Женские сумки",
}


def kb_categories_post(gender: str) -> InlineKeyboardMarkup:
    category_keys = CATEGORIES.get(gender, []) if isinstance(CATEGORIES, dict) else CATEGORIES
    rows = [
        [InlineKeyboardButton(
            text=CATEGORY_POST_LABELS.get((gender, key), key),
            callback_data=f"post_cat:{gender}:{key}",
        )]
        for key in category_keys
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:new_post")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_select_brand(brands: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{b['emoji']} {b['name']}", callback_data=f"post_brand:{b['id']}")]
            for b in brands]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:new_post")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_photo_confirm(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Да, добавить ({count})", callback_data="photo_confirm:yes")],
        [InlineKeyboardButton(text="🔄 Заново", callback_data="photo_confirm:redo")],
    ])


def kb_broadcast_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣 Всем", callback_data="adm:bc:all")],
        [InlineKeyboardButton(text="👩 Женщинам", callback_data="adm:bc:female")],
        [InlineKeyboardButton(text="👨 Мужчинам", callback_data="adm:bc:male")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:panel_back")],
    ])


async def show_admin_panel(message: Message, session: dict):
    await message.answer(f"🛠 <b>Панель администратора</b>\n👤 {session.get('login','')}", reply_markup=kb_admin_panel())


class AdminStates(StatesGroup):
    post_waiting_photo = State()
    post_photo_confirm = State()
    post_waiting_title = State()
    post_waiting_size = State()
    post_waiting_price = State()
    post_waiting_description = State()
    broadcast_waiting = State()


@router.callback_query(F.data == "adm:logout")
async def cb_logout(call: CallbackQuery, state: FSMContext, repos: Repos):
    await repos.staff.delete_session(call.from_user.id)
    await state.clear()
    await safe_edit(call.message, "👋 Вы вышли из панели администратора.")
    await call.answer()


@router.callback_query(F.data == "adm:panel_back")
async def cb_panel_back(call: CallbackQuery, state: FSMContext, repos: Repos):
    session = await require_role(call.from_user.id, repos, "admin")
    if not session:
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await state.clear()
    await safe_edit(call.message, f"🛠 <b>Панель администратора</b>\n👤 {session.get('login','')}", reply_markup=kb_admin_panel())
    await call.answer()


@router.callback_query(F.data == "adm:support")
async def cb_support_entry(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    from handlers.client.support import kb_admin_support_menu
    await safe_edit(call.message, "🎧 <b>Поддержка</b>", reply_markup=kb_admin_support_menu())
    await call.answer()


# ── Создание поста ──────────────────────────────────────────────────

@router.callback_query(F.data == "adm:new_post")
async def cb_new_post(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await safe_edit(call.message, "📝 Выберите пол:", reply_markup=kb_gender_post())
    await call.answer()


@router.callback_query(F.data.startswith("post_gender:"))
async def cb_post_gender(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    gender = call.data.split(":")[1]
    await state.update_data(post_gender=gender)
    await safe_edit(call.message, "📝 Выберите категорию:", reply_markup=kb_categories_post(gender))
    await call.answer()


@router.callback_query(F.data.startswith("post_cat:"))
async def cb_post_category(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    _, gender, category = call.data.split(":")
    await state.update_data(post_category=category)

    brands = await repos.brands.list(gender, category)
    if not brands:
        await call.answer("В этой категории пока нет разделов. Создайте через менеджера.", show_alert=True)
        return

    await safe_edit(call.message, "📂 Выберите раздел (топик):", reply_markup=kb_select_brand(brands))
    await call.answer()


@router.callback_query(F.data.startswith("post_brand:"))
async def cb_post_brand(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    brand_id = int(call.data.split(":")[1])
    await state.update_data(post_brand_id=brand_id, post_photos=[])
    await state.set_state(AdminStates.post_waiting_photo)

    await safe_edit(call.message,
        "📸 Шаг 1/5 — отправьте фотографии товара (можно несколько). Когда закончите — нажмите кнопку.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Фото готовы", callback_data="photo_confirm:check")]
        ]),
    )
    await call.answer()


@router.message(AdminStates.post_waiting_photo, F.photo)
async def msg_post_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("post_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(post_photos=photos)
    await message.answer(f"📎 Добавлено ({len(photos)}). Отправьте ещё или нажмите «✅ Фото готовы».")


@router.message(AdminStates.post_waiting_photo)
async def msg_post_photo_bad(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте фото.")


@router.callback_query(F.data == "photo_confirm:check")
async def cb_photo_check(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    data = await state.get_data()
    photos = data.get("post_photos", [])
    if not photos:
        await call.answer("⚠️ Добавьте хотя бы одно фото!", show_alert=True)
        return
    await state.set_state(AdminStates.post_photo_confirm)
    await safe_edit(call.message, f"📸 Добавлено {len(photos)} фото.", reply_markup=kb_photo_confirm(len(photos)))
    await call.answer()


@router.callback_query(AdminStates.post_photo_confirm, F.data == "photo_confirm:yes")
async def cb_photo_yes(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await state.set_state(AdminStates.post_waiting_title)
    await safe_edit(
        call.message,
        "✅ Фото приняты!\n\n"
        "Шаг 2/5 — введите бренд и название товара одной строкой\n"
        "(например: <i>Nike Air Force 1</i> или <i>Zara Oversized Blazer</i>):",
    )
    await call.answer()


@router.callback_query(AdminStates.post_photo_confirm, F.data == "photo_confirm:redo")
async def cb_photo_redo(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await state.update_data(post_photos=[])
    await state.set_state(AdminStates.post_waiting_photo)
    await safe_edit(call.message,
        "🔄 Скиньте фото заново.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Фото готовы", callback_data="photo_confirm:check")]
        ]),
    )
    await call.answer()


@router.message(AdminStates.post_waiting_title)
async def msg_post_title(message: Message, state: FSMContext):
    await state.update_data(post_title=message.text.strip())
    await state.set_state(AdminStates.post_waiting_size)
    await message.answer(
        "✅ Сохранено!\n\n"
        "Шаг 3/5 — укажите размер(-ы) товара\n"
        "(например: <i>42</i>, <i>S-XL</i> или <i>One size</i>. Если размер не нужен — отправьте «-»):"
    )


@router.message(AdminStates.post_waiting_size)
async def msg_post_size(message: Message, state: FSMContext):
    raw = message.text.strip()
    size = None if raw in ("-", "—", "") else raw
    await state.update_data(post_size=size)
    await state.set_state(AdminStates.post_waiting_price)
    await message.answer("✅ Сохранено!\n\nШаг 4/5 — введите цену:")


@router.message(AdminStates.post_waiting_price)
async def msg_post_price(message: Message, state: FSMContext):
    await state.update_data(post_price=message.text.strip())
    await state.set_state(AdminStates.post_waiting_description)
    await message.answer(
        "✅ Сохранено!\n\n"
        "Шаг 5/5 — добавьте короткое описание товара <b>на английском</b> "
        "(материал, посадка, фишка модели и т.п. — 1-2 предложения).\n"
        "Если описание не нужно — отправьте «-»:"
    )


@router.message(AdminStates.post_waiting_description)
async def msg_post_description(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    session = await require_role(message.from_user.id, repos, "admin")
    if not session:
        await state.clear()
        return

    raw_desc = message.text.strip()
    description = None if raw_desc in ("-", "—", "") else raw_desc

    data = await state.get_data()
    await state.clear()

    gender = data.get("post_gender")
    category = data.get("post_category")
    title = data.get("post_title")
    size = data.get("post_size")
    price = data.get("post_price")
    photos = data.get("post_photos", [])
    brand_id = data.get("post_brand_id")
    login = session.get("login", "")

    brand = await repos.brands.get(brand_id)
    channel = await repos.brands.get_channel(gender, category)

    if not brand or not channel:
        await message.answer("❌ Канал/раздел не настроены.", reply_markup=kb_admin_panel())
        return

    caption = build_post_caption(gender, category, brand, title, size, price, description)

    try:
        if len(photos) == 1:
            sent = await bot.send_photo(
                chat_id=channel["chat_id"], message_thread_id=brand["topic_id"],
                photo=photos[0], caption=caption,
            )
            tg_msg_id = sent.message_id
        else:
            media = [InputMediaPhoto(media=photos[0], caption=caption)] + [InputMediaPhoto(media=p) for p in photos[1:]]
            sent_list = await bot.send_media_group(
                chat_id=channel["chat_id"], message_thread_id=brand["topic_id"], media=media,
            )
            tg_msg_id = sent_list[0].message_id

        post_id = await repos.posts.create(
            brand_id, gender, category, title, price, photos[0], tg_msg_id, login,
            size=size, description=description,
        )

        # Если склад уже регистрировал этот товар как "виртуальный" (лист ожидания,
        # товара ещё не было в канале) — переносим накопленный лист ожидания на
        # только что опубликованный реальный пост и уведомляем ждавших клиентов.
        # Уведомление уходит в личку клиенту-подписчику канала — тоже на английском.
        virtual = await repos.posts.find_virtual_duplicate(brand_id, title)
        if virtual and virtual["id"] != post_id:
            interested = await repos.posts.interested_users(virtual["id"])
            await repos.posts.merge_virtual_into_real(virtual["id"], post_id)
            for user_tg_id in interested:
                try:
                    await bot.send_message(
                        user_tg_id,
                        f"✅ <b>It's back in stock!</b>\n🏷 {title}\n💰 {price}\n\nGrab it before it's gone again!",
                    )
                except Exception:
                    pass

        # Кнопки "в корзину"/"сохранить" под постом (отдельным сообщением — Telegram не позволяет
        # добавить inline-кнопки с deep-link после публикации без редактирования через бота как автора)
        # Текст и кнопки видят клиенты в канале — только на английском.
        bot_me = await bot.get_me()
        cart_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🛒 Add to Cart", url=f"https://t.me/{bot_me.username}?start=cart_{post_id}"),
            InlineKeyboardButton(text="❤️ Save it", url=f"https://t.me/{bot_me.username}?start=wish_{post_id}"),
        ]])
        await bot.send_message(
            chat_id=channel["chat_id"], message_thread_id=brand["topic_id"],
            text="👇 Tap to add this to your bag:", reply_markup=cart_kb,
            reply_to_message_id=tg_msg_id,
        )

        await message.answer(
            f"✅ <b>Пост опубликован!</b>\n\n🏷 {title}\n📏 {size or '—'}\n💰 {price}\n📸 Фото: {len(photos)}",
            reply_markup=kb_admin_panel(),
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка публикации: <code>{e}</code>\nПроверьте права бота в канале/топике.",
            reply_markup=kb_admin_panel(),
        )


# ── Мои публикации ───────────────────────────────────────────────────

@router.callback_query(F.data == "adm:my_posts")
async def cb_my_posts(call: CallbackQuery, repos: Repos):
    session = await require_role(call.from_user.id, repos, "admin")
    if not session:
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    posts = await repos.posts.by_admin(session.get("login", ""))
    if not posts:
        await safe_edit(call.message, "📭 Публикаций пока нет.", reply_markup=kb_back_admin())
        await call.answer()
        return

    lines = [f"• {p['title']} | {p['price']} | {str(p['created_at'])[:10]}" for p in posts[:20]]
    await safe_edit(call.message, f"📊 <b>Мои публикации ({len(posts)})</b>\n\n" + "\n".join(lines), reply_markup=kb_back_admin())
    await call.answer()


# ── Рассылка ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:broadcast_menu")
async def cb_broadcast_menu(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await safe_edit(call.message, "📣 Выберите аудиторию:", reply_markup=kb_broadcast_menu())
    await call.answer()


@router.callback_query(F.data.startswith("adm:bc:"))
async def cb_broadcast_start(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    target = call.data.split(":")[2]
    await state.set_state(AdminStates.broadcast_waiting)
    await state.update_data(bc_target=target)
    await safe_edit(call.message, "✏️ Напишите текст рассылки (можно с фото):", reply_markup=kb_back_admin())
    await call.answer()


@router.message(AdminStates.broadcast_waiting)
async def msg_broadcast_send(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    if not await require_role(message.from_user.id, repos, "admin"):
        await state.clear()
        return

    data = await state.get_data()
    target = data.get("bc_target", "all")
    await state.clear()

    gender_filter = None if target == "all" else target
    users = await repos.users.all(gender=gender_filter)

    sent, failed = 0, 0
    for i, user in enumerate(users):
        try:
            if message.photo:
                await bot.send_photo(user["tg_id"], message.photo[-1].file_id, caption=message.caption or "")
            else:
                await bot.send_message(user["tg_id"], message.text or "")
            sent += 1
        except Exception:
            failed += 1
        # Telegram допускает не более ~30 сообщений/сек в разные чаты — небольшая
        # пауза защищает от flood-лимитов на крупных базах пользователей.
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

    await message.answer(f"✅ <b>Рассылка завершена</b>\n📨 {sent} / ❌ {failed}", reply_markup=kb_admin_panel())


# ── Заказы (обзор для админа, без необходимости ждать пуш-уведомление) ──

def kb_orders_overview(orders: list[dict]) -> InlineKeyboardMarkup:
    from db.repo_orders import status_label
    rows = []
    for o in orders:
        uname = f"@{o['username']}" if o.get("username") else f"ID {o['user_tg_id']}"
        short_status = status_label(o["status"]).split(" ", 1)[0]  # только иконка
        rows.append([InlineKeyboardButton(
            text=f"{short_status} #{o['id']} — {uname}", callback_data=f"adm:order_detail:{o['id']}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:panel_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "adm:orders")
async def cb_adm_orders(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    orders = await repos.orders.active_for_admin()
    if not orders:
        await safe_edit(call.message, "📭 Нет активных заказов.", reply_markup=kb_back_admin())
        await call.answer()
        return

    await safe_edit(call.message, f"📋 <b>Активные заказы ({len(orders)})</b>", reply_markup=kb_orders_overview(orders))
    await call.answer()


@router.callback_query(F.data.startswith("adm:order_detail:"))
async def cb_adm_order_detail(call: CallbackQuery, repos: Repos):
    from db.repo_orders import status_label
    from keyboards.client_kb import kb_order_confirm

    if not await require_role(call.from_user.id, repos, "admin"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return

    items = await repos.orders.get_items(order_id)
    lines = "\n".join(f"• {it.get('title','?')} — {it.get('price','—')}" for it in items)
    user = await repos.users.get(order["user_tg_id"])
    uname = f"@{user.get('username')}" if user and user.get("username") else f"ID {order['user_tg_id']}"
    phone = user.get("phone", "—") if user else "—"

    text = (
        f"📦 <b>Заказ #{order_id}</b>\n"
        f"Статус: <b>{status_label(order['status'])}</b>\n\n"
        f"👤 {uname}\n📱 {phone}\n📏 Размер: {order.get('size','—')}\n💬 {order.get('comment','—')}\n\n"
        f"{lines}"
    )

    kb = None
    if order["status"] == "pending":
        kb = kb_order_confirm(order_id)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:orders")]])

    await safe_edit(call.message, text, reply_markup=kb)
    await call.answer()
