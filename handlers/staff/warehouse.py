"""
handlers/staff/warehouse.py

Склад:
  /warehouse — вход
  📦 Активные заказы — фотоотчёт по конкретному заказу (товар уже известен из каталога)
  📸 Новый фотоотчёт — свободный отчёт: пол → категория → раздел → фото(несколько) → название → цена.
      Бот сам проверяет, есть ли такой товар (по названию) в этом разделе каталога:
        - если есть и пост реальный (опубликован админом) → кнопка "Просмотреть" ведёт прямо на него
        - если нет → создаём "виртуальную" запись; кнопка работает как лист ожидания
          (клиент жмёт "Просмотреть" → если товара ещё нет, бот просит подождать и
          запоминает его, чтобы уведомить, как только склад отметит товар "в наличии")
  📋 Управление наличием — переключение в наличии/закончился, с автоуведомлением листа ожидания
  📊 Интерес за сегодня — аналитика кликов по закончившимся товарам
"""

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import CATEGORIES
from db.repos import Repos
from handlers.staff.auth import require_role
from utils import safe_edit
from translate import tr
from locales.texts import tt

router = Router()


class WarehouseAuth(StatesGroup):
    waiting_login = State()
    waiting_password = State()


class WarehouseReport(StatesGroup):
    new_gender = State()
    new_category = State()
    new_brand = State()
    waiting_photo = State()
    photo_confirm = State()
    waiting_title = State()
    waiting_price = State()
    asking_in_stock = State()


# ИСПРАВЛЕНИЕ: единая карта подписей категорий с эмодзи (русские ключи, как в
# config.CATEGORIES), используется и для "Новый фотоотчёт", и для "Управление
# наличием" — раньше их не было, категории брались через CATEGORIES[gender].items().
CATEGORY_LABELS = {
    ("male", "Одежда"): "👔 Мужская одежда",
    ("male", "Обувь"): "👟 Мужская обувь",
    ("male", "Аксессуары"): "⌚️ Мужские аксессуары",
    ("female", "Одежда"): "👗 Женская одежда",
    ("female", "Обувь"): "👠 Женская обувь",
    ("female", "Аксессуары"): "💍 Женские аксессуары",
    ("female", "Сумки"): "👜 Женские сумки",
}


# ── Клавиатуры ────────────────────────────────────────────────────────

def kb_warehouse_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Активные заказы", callback_data="wh:orders")],
        [InlineKeyboardButton(text="📸 Новый фотоотчёт", callback_data="wh:new_report")],
        [InlineKeyboardButton(text="📋 Управление наличием", callback_data="wh:stock")],
        [InlineKeyboardButton(text="📊 Интерес за сегодня", callback_data="wh:interest")],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="wh:logout")],
    ])


def kb_back_wh() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="wh:menu")]])


def kb_orders_list(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for o in orders:
        uname = f"@{o.get('username')}" if o.get("username") else f"ID {o['user_tg_id']}"
        rows.append([InlineKeyboardButton(text=f"#{o['id']} {uname}", callback_data=f"wh:order:{o['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="wh:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_order_items(order_id: int, items: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"📸 {(it.get('title') or 'Товар')[:30]}", callback_data=f"wh:report_item:{order_id}:{it['id']}")]
            for it in items]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="wh:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_whrep_gender() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="whrep:gender:male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="whrep:gender:female")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="wh:menu")],
    ])


def kb_whrep_category(gender: str) -> InlineKeyboardMarkup:
    # ИСПРАВЛЕНИЕ: было CATEGORIES[gender].items() — но CATEGORIES[gender] это
    # список строк, а не словарь, у списков нет .items(). Это гарантированно
    # роняло "Новый фотоотчёт" сразу после выбора пола (AttributeError).
    category_keys = CATEGORIES.get(gender, []) if isinstance(CATEGORIES, dict) else CATEGORIES
    rows = [[InlineKeyboardButton(text=CATEGORY_LABELS.get((gender, key), key), callback_data=f"whrep:cat:{gender}:{key}")]
            for key in category_keys]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="wh:new_report")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_whrep_brand(brands: list[dict], gender: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{b['emoji']} {b['name']}", callback_data=f"whrep:brand:{b['id']}")]
            for b in brands]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"whrep:gender:{gender}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_photo_confirm(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Да, добавить ({count})", callback_data="whrep:photo_confirm:yes")],
        [InlineKeyboardButton(text="🔄 Заново", callback_data="whrep:photo_confirm:redo")],
    ])


def kb_photos_done() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Фото готовы", callback_data="whrep:photo_check")]
    ])


def kb_stock_gender() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="wh:stockgender:male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="wh:stockgender:female")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="wh:menu")],
    ])


def kb_stock_category(gender: str) -> InlineKeyboardMarkup:
    # ИСПРАВЛЕНИЕ: тот же баг, что и в kb_whrep_category — CATEGORIES[gender].items()
    # на списке. Роняло "Управление наличием" сразу после выбора пола.
    category_keys = CATEGORIES.get(gender, []) if isinstance(CATEGORIES, dict) else CATEGORIES
    rows = [[InlineKeyboardButton(text=CATEGORY_LABELS.get((gender, key), key), callback_data=f"wh:stockcat:{gender}:{key}")]
            for key in category_keys]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="wh:stock")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_stock_brand(brands: list[dict], gender: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{b['emoji']} {b['name']}", callback_data=f"wh:stockbrand:{b['id']}")]
            for b in brands]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"wh:stockgender:{gender}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_stock_posts(posts: list[dict], brand: dict) -> InlineKeyboardMarkup:
    rows = []
    for p in posts:
        status_icon = "✅" if p.get("in_stock", True) else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{status_icon} {p['title'][:30]} | {p['price']}",
            callback_data=f"wh:toggle_stock:{brand['id']}:{p['id']}",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Назад", callback_data=f"wh:stockcat:{brand['gender']}:{brand['category']}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_warehouse_panel(message: Message):
    await message.answer("📦 <b>Панель склада</b>", reply_markup=kb_warehouse_menu())


# ── Меню / выход ──────────────────────────────────────────────────────

@router.callback_query(F.data == "wh:menu")
async def cb_wh_menu(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await state.clear()
    await safe_edit(call.message, "📦 <b>Панель склада</b>", reply_markup=kb_warehouse_menu())
    await call.answer()


@router.callback_query(F.data == "wh:logout")
async def cb_wh_logout(call: CallbackQuery, repos: Repos):
    await repos.staff.delete_session(call.from_user.id)
    await safe_edit(call.message, "👋 Вы вышли из панели склада.")
    await call.answer()


# ── Активные заказы ─────────────────────────────────────────────────

@router.callback_query(F.data == "wh:orders")
async def cb_wh_orders(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    orders = await repos.orders.confirmed()
    if not orders:
        await safe_edit(call.message, "📭 Нет активных заказов.", reply_markup=kb_back_wh())
        await call.answer()
        return

    await safe_edit(call.message, f"📦 <b>Активные заказы ({len(orders)})</b>", reply_markup=kb_orders_list(orders))
    await call.answer()


@router.callback_query(F.data.startswith("wh:order:"))
async def cb_wh_order_detail(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    items = await repos.orders.get_items(order_id)
    if not order:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return

    lines = "\n".join(f"• {it.get('title','?')} | {it.get('price','—')} | р. {it.get('size','—')}" for it in items)
    text = f"📦 <b>Заказ #{order_id}</b>\n\n{lines}\n\n💬 {order.get('comment','—')}\n\nВыберите товар для фотоотчёта:"
    await safe_edit(call.message, text, reply_markup=kb_order_items(order_id, items))
    await call.answer()


# ── Фотоотчёт по товару из заказа (бренд/категория уже известны) ──────

@router.callback_query(F.data.startswith("wh:report_item:"))
async def cb_wh_report_item(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    _, _, order_id, item_id = call.data.split(":")
    items = await repos.orders.get_items(int(order_id))
    item = next((i for i in items if i["id"] == int(item_id)), None)
    if not item:
        await call.answer("❌ Товар не найден", show_alert=True)
        return

    post_id = item.get("post_id")
    gender, category, brand_id = "male", None, item.get("brand_id")
    if post_id:
        post = await repos.posts.get(post_id)
        if post:
            gender = post.get("gender", "male")
            category = post.get("category")
            brand_id = post.get("brand_id")

    await state.set_state(WarehouseReport.waiting_photo)
    await state.update_data(
        order_id=int(order_id), prefill_title=item.get("title", ""), prefill_price=item.get("price", ""),
        known_post_id=post_id, report_gender=gender, report_category=category, report_brand_id=brand_id,
        photos=[],
    )
    await safe_edit(call.message,
        f"📸 Фотоотчёт — {item.get('title','Товар')}\n\nШаг 1/3 — отправьте фото товара (можно несколько):",
        reply_markup=kb_photos_done(),
    )
    await call.answer()


# ── Новый фотоотчёт: пол → категория → раздел ──────────────────────────

@router.callback_query(F.data == "wh:new_report")
async def cb_wh_new_report(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await safe_edit(call.message, "📸 <b>Новый фотоотчёт</b>\n\nВыберите пол товара:", reply_markup=kb_whrep_gender())
    await call.answer()


@router.callback_query(F.data.startswith("whrep:gender:"))
async def cb_whrep_gender(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    gender = call.data.split(":")[2]
    await state.update_data(report_gender=gender)
    await safe_edit(call.message, "Выберите категорию:", reply_markup=kb_whrep_category(gender))
    await call.answer()


@router.callback_query(F.data.startswith("whrep:cat:"))
async def cb_whrep_category(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    _, _, gender, category = call.data.split(":")
    brands = await repos.brands.list(gender, category)
    if not brands:
        await call.answer("В этой категории пока нет разделов. Создайте через менеджера.", show_alert=True)
        return
    await state.update_data(report_category=category)
    await safe_edit(call.message, "Выберите раздел:", reply_markup=kb_whrep_brand(brands, gender))
    await call.answer()


@router.callback_query(F.data.startswith("whrep:brand:"))
async def cb_whrep_brand(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    brand_id = int(call.data.split(":")[2])
    await state.update_data(
        report_brand_id=brand_id, order_id=None, prefill_title="", prefill_price="",
        known_post_id=None, photos=[],
    )
    await state.set_state(WarehouseReport.waiting_photo)
    await safe_edit(call.message,
        "📸 Шаг 1/3 — отправьте фото товара (можно несколько):", reply_markup=kb_photos_done()
    )
    await call.answer()


# ── Фото (несколько) ────────────────────────────────────────────────────

@router.message(WarehouseReport.waiting_photo, F.photo)
async def wh_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"📎 Добавлено ({len(photos)}). Отправьте ещё или нажмите «✅ Фото готовы».")


@router.message(WarehouseReport.waiting_photo)
async def wh_photo_bad(message: Message):
    await message.answer("⚠️ Отправьте фото товара.")


@router.callback_query(F.data == "whrep:photo_check")
async def cb_whrep_photo_check(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await call.answer("⚠️ Добавьте хотя бы одно фото!", show_alert=True)
        return
    await state.set_state(WarehouseReport.photo_confirm)
    await safe_edit(call.message, f"📸 Добавлено {len(photos)} фото.", reply_markup=kb_photo_confirm(len(photos)))
    await call.answer()


@router.callback_query(WarehouseReport.photo_confirm, F.data == "whrep:photo_confirm:yes")
async def cb_whrep_photo_yes(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    data = await state.get_data()
    hint = f"\n💡 Из заказа: <b>{data['prefill_title']}</b>" if data.get("prefill_title") else ""
    await state.set_state(WarehouseReport.waiting_title)
    await safe_edit(call.message, f"✅ Фото приняты!\n\nШаг 2/3 — название товара:{hint}")
    await call.answer()


@router.callback_query(WarehouseReport.photo_confirm, F.data == "whrep:photo_confirm:redo")
async def cb_whrep_photo_redo(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await state.update_data(photos=[])
    await state.set_state(WarehouseReport.waiting_photo)
    await safe_edit(call.message, "🔄 Скиньте фото заново:", reply_markup=kb_photos_done())
    await call.answer()


# ── Название / цена ──────────────────────────────────────────────────

@router.message(WarehouseReport.waiting_title)
async def wh_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(WarehouseReport.waiting_price)
    data = await state.get_data()
    hint = f"\n💡 Цена из заказа: <b>{data['prefill_price']}</b>" if data.get("prefill_price") else ""
    await message.answer(f"✅ Название сохранено!\n\nШаг 3/3 — цена:{hint}")


@router.message(WarehouseReport.waiting_price)
async def wh_price(message: Message, state: FSMContext, repos: Repos):
    session = await require_role(message.from_user.id, repos, "warehouse")
    if not session:
        await state.clear()
        return

    await state.update_data(price=message.text.strip())
    data = await state.get_data()

    order_id = data.get("order_id")
    if order_id:
        # Отчёт по заказу — товар точно есть (его только что собрали для отправки клиенту),
        # вопрос "в наличии?" тут не нужен.
        await _publish_report(message, state, repos, in_stock=True, warehouse_tg_id=message.from_user.id)
        return

    await state.set_state(WarehouseReport.asking_in_stock)
    await message.answer(
        "❓ Этот товар сейчас есть в наличии (уже выложен/доступен), или его пока нет?",
        reply_markup=kb_ask_in_stock(),
    )


def kb_ask_in_stock() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, есть в наличии", callback_data="whrep:instock:yes")],
        [InlineKeyboardButton(text="❌ Нет, пока отсутствует", callback_data="whrep:instock:no")],
    ])


@router.callback_query(WarehouseReport.asking_in_stock, F.data.startswith("whrep:instock:"))
async def cb_whrep_instock(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    in_stock = call.data.split(":")[2] == "yes"
    await safe_edit(call.message, "⏳ Публикую отчёт...")
    await _publish_report(call.message, state, repos, in_stock=in_stock, warehouse_tg_id=call.from_user.id)
    await call.answer()


_CATEGORY_LABELS_EN = {
    ("male", "Одежда"): "Men's Clothing", ("male", "Обувь"): "Men's Shoes",
    ("male", "Аксессуары"): "Men's Accessories",
    ("female", "Одежда"): "Women's Clothing", ("female", "Обувь"): "Women's Shoes",
    ("female", "Аксессуары"): "Women's Accessories", ("female", "Сумки"): "Women's Bags",
}


def _path_label(gender: str, category: str, brand: dict | None) -> str:
    """Текстовый путь категории — используется в отчёте, который публикуется в канал
    (видят клиенты), поэтому строго на английском."""
    gender_label = "👨 Men" if gender == "male" else "👩 Women"
    cat_label = _CATEGORY_LABELS_EN.get((gender, category), (category or "").capitalize())
    brand_part = f" → {brand['emoji']} {brand['name']}" if brand else ""
    return f"{gender_label} → {cat_label}{brand_part}"


async def _publish_report(target, state: FSMContext, repos: Repos, in_stock: bool, warehouse_tg_id: int):
    """target — Message, в которое можно ответить .answer(...) / .answer_photo(...)."""
    data = await state.get_data()
    await state.clear()

    photos = data.get("photos", [])
    title = data.get("title", "")
    price = data.get("price", "")
    order_id = data.get("order_id")
    gender = data.get("report_gender", "male")
    category = data.get("report_category")
    brand_id = data.get("report_brand_id")
    known_post_id = data.get("known_post_id")

    bot = target.bot

    if not photos:
        await target.answer("❌ Нет фото для отчёта.", reply_markup=kb_warehouse_menu())
        return

    brand = await repos.brands.get(brand_id) if brand_id else None
    path_text = _path_label(gender, category, brand)

    caption = (
        f"📦 <b>RESTOCK UPDATE</b>\n\n📂 {path_text}\n🏷 {title}\n💰 {price}\n"
        f"📋 Order: {'#' + str(order_id) if order_id else '—'}"
    )

    report_channel = await repos.settings.get(f"report_channel_{gender}_chat_id")
    if not report_channel:
        await target.answer(
            "⚠️ Канал отчётов склада не настроен.\n"
            "Менеджер может задать его через /manager → «📦 Канал отчётов склада».",
            reply_markup=kb_warehouse_menu(),
        )
        return

    report_msg_id = None
    try:
        if len(photos) == 1:
            sent = await bot.send_photo(chat_id=report_channel, photo=photos[0], caption=caption)
            report_msg_id = sent.message_id
        else:
            media = [InputMediaPhoto(media=photos[0], caption=caption)] + [InputMediaPhoto(media=p) for p in photos[1:]]
            sent_list = await bot.send_media_group(chat_id=report_channel, media=media)
            report_msg_id = sent_list[0].message_id
    except Exception as e:
        await target.answer(
            f"⚠️ Не удалось опубликовать в канал отчётности: <code>{e}</code>\n"
            "Проверь, что бот добавлен админом в этот канал.",
            reply_markup=kb_warehouse_menu(),
        )
        return

    # ── Определяем пост для трекинга наличия (только для свободных отчётов) ──
    target_post_id = known_post_id
    if not known_post_id and brand_id:
        existing = await repos.posts.find_by_brand_title(brand_id, title)
        if existing:
            target_post_id = existing["id"]
            await repos.posts.set_in_stock(target_post_id, in_stock)
        else:
            target_post_id = await repos.posts.create_virtual(
                brand_id, gender, category, title, price, photos[0], "warehouse"
            )
            if in_stock:
                await repos.posts.set_in_stock(target_post_id, True)

    if not in_stock and target_post_id:
        # Кнопка "уведомить когда появится" — ведёт в бота, надёжно работает без браузерных скачков
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔔 Notify me when it's back", callback_data=f"wnotify:{target_post_id}")
        ]])
        try:
            await bot.send_message(
                chat_id=report_channel,
                text=f"😔 <b>Currently out of stock:</b>\n📂 {path_text}\n🏷 {title}",
                reply_markup=kb,
                reply_to_message_id=report_msg_id,
            )
        except Exception:
            pass

    await repos.warehouse.save_report(warehouse_tg_id, order_id, title, price, photos[0], report_msg_id)

    if order_id:
        await repos.orders.update_status(order_id, "warehouse_received")
        order = await repos.orders.get(order_id)
        if order:
            client = await repos.users.get(order["user_tg_id"])
            client_lang = client.get("language", "ru") if client else "ru"
            client_text = await tt(repos, client_lang, "notify_warehouse_received")
            try:
                await bot.send_message(order["user_tg_id"], client_text.format(order_id=order_id))
            except Exception:
                pass
        try:
            price_val = float(str(price).replace("$", "").replace(",", ".").strip())
            cost_val = round(price_val / 2.2, 2)
            await repos.finance.add_entry(order_id, price_val, cost_val)
        except Exception:
            pass

    status_line = "✅ В наличии" if in_stock else "❌ Пока отсутствует (лист ожидания включён)"
    await target.answer_photo(
        photos[0],
        caption=f"✅ <b>Фотоотчёт опубликован!</b>\n\n📂 {path_text}\n🏷 {title}\n💰 {price}\n{status_line}",
        reply_markup=kb_warehouse_menu(),
    )

    # Заказ — обязательный последний шаг: подтвердить, что товар реально отправлен.
    # Без этого статус у клиента так и останется "склад собрал", он не узнает что заказ в пути.
    if order_id:
        await target.answer(
            f"❗️ <b>Завершите заказ #{order_id}</b>\n\n"
            "Отчёт опубликован. Теперь подтвердите, что товар передан в доставку:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Подтверждаю отправку", callback_data=f"wh:confirm_ship:{order_id}")
            ]]),
        )


@router.callback_query(F.data.startswith("wh:confirm_ship:"))
async def cb_wh_confirm_ship(call: CallbackQuery, repos: Repos, bot: Bot):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return

    await repos.orders.update_status(order_id, "shipping")
    await safe_edit(call.message, f"✅ Отправка по заказу #{order_id} подтверждена. Дальше — не ваша забота.")
    await call.answer("✅ Готово")

    user = await repos.users.get(order["user_tg_id"])
    lang = user.get("language", "ru") if user else "ru"
    gender = None
    items = await repos.orders.get_items(order_id)
    if items and items[0].get("brand_id"):
        brand = await repos.brands.get(items[0]["brand_id"])
        if brand:
            gender = brand.get("gender")

    report_url = await repos.settings.get(f"report_channel_{gender}_url") if gender else None
    link_line = f"\n\n🔗 {report_url}" if report_url else ""

    template = await tr(
        repos,
        "🚚 Ваш заказ #ORDERID передан в доставку!\n\n"
        "Фотоотчёт о вашем товаре можно посмотреть в канале отчётов склада:",
        lang,
    )
    client_text = template.replace("ORDERID", str(order_id)) + link_line
    received_btn = await tt(repos, lang, "order_delivered_confirm_btn")
    kb_received = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=received_btn, callback_data=f"myorder:received:{order_id}")
    ]])
    try:
        await bot.send_message(order["user_tg_id"], client_text, reply_markup=kb_received)
    except Exception:
        pass


# ── Управление наличием товара ────────────────────────────────────────

@router.callback_query(F.data == "wh:stock")
async def cb_wh_stock(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    await safe_edit(call.message,
        "📋 <b>Управление наличием</b>\n\nВыберите пол товара:",
        reply_markup=kb_stock_gender(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("wh:stockgender:"))
async def cb_wh_stock_gender(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    gender = call.data.split(":")[2]
    await safe_edit(call.message, "Выберите раздел (категорию):", reply_markup=kb_stock_category(gender))
    await call.answer()


@router.callback_query(F.data.startswith("wh:stockcat:"))
async def cb_wh_stock_category(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    _, _, gender, category = call.data.split(":")
    brands = await repos.brands.list(gender, category)
    if not brands:
        await call.answer("📭 В этой категории пока нет разделов.", show_alert=True)
        return
    await safe_edit(call.message, "Выберите бренд/раздел:", reply_markup=kb_stock_brand(brands, gender))
    await call.answer()


@router.callback_query(F.data.startswith("wh:stockbrand:"))
async def cb_wh_stock_brand(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    brand_id = int(call.data.split(":")[2])
    brand = await repos.brands.get(brand_id)
    if not brand:
        await call.answer("❌ Раздел не найден", show_alert=True)
        return
    posts = await repos.posts.by_brand(brand_id)
    if not posts:
        await safe_edit(
            call.message,
            f"📭 <b>{brand['emoji']} {brand['name']}</b>\n\nВ этом разделе пока нет товаров.",
            reply_markup=kb_stock_brand(await repos.brands.list(brand["gender"], brand["category"]), brand["gender"]),
        )
        await call.answer()
        return

    await safe_edit(call.message,
        f"📋 <b>{brand['emoji']} {brand['name']}</b>\n\n"
        "Нажмите на товар, чтобы переключить статус:\n✅ в наличии / ❌ закончился",
        reply_markup=kb_stock_posts(posts, brand),
    )
    await call.answer()


@router.callback_query(F.data.startswith("wh:toggle_stock:"))
async def cb_wh_toggle_stock(call: CallbackQuery, repos: Repos, bot: Bot):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    _, _, brand_id_str, post_id_str = call.data.split(":")
    brand_id, post_id = int(brand_id_str), int(post_id_str)
    post = await repos.posts.get(post_id)
    if not post:
        await call.answer("❌ Товар не найден", show_alert=True)
        return

    new_status = not post.get("in_stock", True)
    await repos.posts.set_in_stock(post_id, new_status)

    if new_status:
        interested = await repos.posts.interested_users(post_id)

        brand = await repos.brands.get(post["brand_id"]) if post.get("brand_id") else None
        path_text = _path_label(post.get("gender", "male"), post.get("category"), brand)

        # Кнопка ведёт прямо на канал/топик этой категории — раньше указывала на
        # несуществующий callback "cat:...", из-за чего просто ничего не происходило.
        channel = await repos.brands.get_channel(post.get("gender", "male"), post.get("category"))
        if channel and channel.get("invite_url"):
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="👉 Перейти в раздел", url=channel["invite_url"],
            )]])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="👉 Перейти в раздел", callback_data=f"cat_back:{post.get('gender','male')}",
            )]])

        for user_tg_id in interested:
            try:
                await bot.send_message(
                    user_tg_id,
                    f"✅ <b>Товар прибыл!</b>\n📂 {path_text}\n🏷 {post['title']}\n💰 {post['price']}\n\nМожете заказывать:",
                    reply_markup=kb,
                )
            except Exception:
                pass
        await repos.posts.clear_interest(post_id)
        await call.answer(f"✅ Отмечено «в наличии», уведомлено {len(interested)} клиент(ов)", show_alert=True)
    else:
        await call.answer("❌ Отмечено «закончился»", show_alert=True)

    brand = await repos.brands.get(brand_id)
    posts = await repos.posts.by_brand(brand_id)
    await safe_edit(call.message,
        f"📋 <b>{brand['emoji']} {brand['name']}</b>\n\n"
        "Нажмите на товар, чтобы переключить статус:\n✅ в наличии / ❌ закончился",
        reply_markup=kb_stock_posts(posts, brand),
    )


# ── Статистика интереса к закончившимся товарам ───────────────────────

@router.callback_query(F.data == "wh:interest")
async def cb_wh_interest(call: CallbackQuery, repos: Repos):
    if not await require_role(call.from_user.id, repos, "warehouse"):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    summary = await repos.posts.interest_today_summary()
    if not summary:
        await safe_edit(call.message, "📭 Сегодня никто не интересовался закончившимися товарами.", reply_markup=kb_back_wh())
        await call.answer()
        return

    lines = ["📊 <b>Интерес к закончившимся товарам за сегодня</b>\n"]
    for row in summary:
        users_str = ", ".join(
            f"@{u['username']}" if u.get("username") else f"ID {u['user_tg_id']}" for u in row["users"]
        )
        lines.append(
            f"\n🏷 <b>{row.get('title','?')}</b> — {row.get('price','—')}\n"
            f"   👆 кликов: {row['clicks']}\n   👥 {users_str}"
        )

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…"

    await safe_edit(call.message, text, reply_markup=kb_back_wh())
    await call.answer()
