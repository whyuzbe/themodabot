from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.repos import Repos
from locales.texts import t, tt
from keyboards.client_kb import (
    kb_cart, kb_wishlist, kb_after_add, kb_order_confirm, kb_client_verify, kb_my_order, kb_share_phone, kb_remove,
)
from utils import client_menu_kb
from translate import tr
from filters import ButtonText

router = Router()


class CartStates(StatesGroup):
    waiting_phone = State()
    waiting_size = State()
    waiting_comment = State()
    fixing_size = State()
    fixing_comment = State()


# ── Deep-link обработка: вызывается из start.py при /start cart_<id> / wish_<id> ──

async def handle_deeplink(message: Message, payload: str, repos: Repos, user_tg_id: int | None = None):
    user_tg_id = user_tg_id or message.from_user.id
    user = await repos.users.get(user_tg_id)
    if not user:
        return
    lang = user.get("language", "ru")

    try:
        action, post_id_str = payload.split("_", 1)
        post_id = int(post_id_str)
    except Exception:
        return

    post = await repos.posts.get(post_id)
    if not post:
        return

    if action == "cart":
        if not post.get("in_stock", True):
            await repos.posts.add_interest(post_id, user_tg_id)
            template = (
                "😔 «PRODUCTNAME» закончился, но скоро снова появится!\n"
                "Мы напишем вам, как только товар будет в наличии."
            )
            msg = (await tr(repos, template, lang)).replace("PRODUCTNAME", post["title"])
            await message.answer(msg)
            return
        added = await repos.cart.add(user_tg_id, post_id)
        msg = t(lang, "added_to_cart") if added else t(lang, "already_in_cart")
    elif action == "wish":
        if not post.get("in_stock", True):
            await repos.posts.add_interest(post_id, user_tg_id)
            template = (
                "😔 «PRODUCTNAME» закончился, но скоро снова появится!\n"
                "Мы напишем вам, как только товар будет в наличии."
            )
            msg = (await tr(repos, template, lang)).replace("PRODUCTNAME", post["title"])
            await message.answer(msg)
            return
        added = await repos.cart.wish_add(user_tg_id, post_id)
        msg = t(lang, "added_to_wish") if added else t(lang, "already_in_wish")
    elif action == "interest":
        if post.get("in_stock", True):
            # товар уже снова в наличии — просто добавим в корзину вместо ожидания
            added = await repos.cart.add(user_tg_id, post_id)
            template = await tr(repos, "✅ Товар «PRODUCTNAME» уже в наличии!", lang)
            msg = template.replace("PRODUCTNAME", post["title"]) + "\n" + (t(lang, "added_to_cart") if added else t(lang, "already_in_cart"))
        else:
            await repos.posts.add_interest(post_id, user_tg_id)
            template = await tr(repos, "🔔 Хорошо! Как только «PRODUCTNAME» снова появится в наличии — мы вам напишем.", lang)
            msg = template.replace("PRODUCTNAME", post["title"])
        await message.answer(msg, reply_markup=await kb_after_add(repos, lang))
        return
    else:
        return

    await message.answer(msg, reply_markup=await kb_after_add(repos, lang))


# ── Корзина ────────────────────────────────────────────────────────

def _cart_lines(items: list[dict]) -> str:
    return "\n".join(
        f"{i}. <b>{it.get('title','Товар')}</b> — {it.get('price','—')}"
        for i, it in enumerate(items, 1)
    )


@router.message(ButtonText("btn_cart"))
async def msg_cart(message: Message, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    if not user:
        return
    lang = user.get("language", "ru")
    items = await repos.cart.get(message.from_user.id)

    if not items:
        await message.answer(t(lang, "cart_empty"))
        return

    cart_title = await tt(repos, lang, "cart_title")
    await message.answer(cart_title + _cart_lines(items), reply_markup=await kb_cart(repos, lang, items))


@router.callback_query(F.data == "go:cart")
async def cb_go_cart(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    items = await repos.cart.get(call.from_user.id)

    if not items:
        await call.message.edit_text(t(lang, "cart_empty"))
        await call.answer()
        return

    cart_title = await tt(repos, lang, "cart_title")
    await call.message.edit_text(cart_title + _cart_lines(items), reply_markup=await kb_cart(repos, lang, items))
    await call.answer()


@router.callback_query(F.data.startswith("cart:remove:"))
async def cb_cart_remove(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    cart_id = int(call.data.split(":")[2])
    await repos.cart.remove(cart_id, call.from_user.id)

    items = await repos.cart.get(call.from_user.id)
    if not items:
        await call.message.edit_text(t(lang, "cart_empty"))
        await call.answer("🗑")
        return
    cart_title = await tt(repos, lang, "cart_title")
    await call.message.edit_text(cart_title + _cart_lines(items), reply_markup=await kb_cart(repos, lang, items))
    await call.answer("🗑")


@router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    await repos.cart.clear(call.from_user.id)
    await call.message.edit_text(t(lang, "cart_empty"))
    await call.answer()


# ── Оформление заказа ───────────────────────────────────────────────

def kb_reuse_or_manual(reuse_label: str, reuse_cb: str, manual_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {reuse_label}", callback_data=reuse_cb)],
        [InlineKeyboardButton(text="✏️ Указать другой", callback_data=manual_cb)],
    ])


@router.callback_query(F.data == "cart:checkout")
async def cb_checkout(call: CallbackQuery, state: FSMContext, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    items = await repos.cart.get(call.from_user.id)

    if not items:
        await call.answer(await tr(repos, "Корзина пуста!", lang), show_alert=True)
        return

    # Перепроверяем наличие прямо перед оформлением: товар мог быть отмечен
    # складом как «закончился» уже ПОСЛЕ того, как клиент положил его в корзину.
    available = [it for it in items if it.get("in_stock", True)]
    unavailable = [it for it in items if not it.get("in_stock", True)]

    if unavailable:
        for it in unavailable:
            await repos.posts.add_interest(it["post_id"], call.from_user.id)
            await repos.cart.remove(it["cart_id"], call.from_user.id)
        titles = "\n".join(f"• {it.get('title','?')}" for it in unavailable)
        msg = await tr(
            repos,
            "😔 Пока вы оформляли заказ, часть товаров закончилась на складе. "
            "Мы уберём их из корзины и уведомим вас, как только они снова появятся:",
            lang,
        )
        await call.message.answer(f"{msg}\n\n{titles}")

    if not available:
        await call.message.edit_text(t(lang, "cart_empty"))
        await call.answer()
        return

    await state.update_data(lang=lang, cart_items=available)

    if not user or not user.get("phone"):
        await state.set_state(CartStates.waiting_phone)
        await call.message.delete()
        msg = await tr(repos, "📱 Для оформления заказа поделитесь номером телефона:", lang)
        await call.message.answer(msg, reply_markup=await kb_share_phone(repos, lang))
        await call.answer()
        return

    await _proceed_to_size(call.message, state, repos, available, lang, edit=True)
    await call.answer()


@router.message(CartStates.waiting_phone, F.contact)
async def msg_checkout_phone(message: Message, state: FSMContext, repos: Repos):
    phone = message.contact.phone_number
    await repos.users.update(message.from_user.id, phone=phone)

    user = await repos.users.get(message.from_user.id)
    data = await state.get_data()
    lang = data.get("lang", "ru")

    items = data.get("cart_items", [])

    await message.answer(
        await tr(repos, "✅ Номер сохранён!", lang),
        reply_markup=kb_remove(),
    )
    await _proceed_to_size(message, state, repos, items, lang, edit=False)


@router.message(CartStates.waiting_phone)
async def msg_checkout_phone_invalid(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await message.answer(t(lang, "invalid_phone"))


async def _proceed_to_size(target, state: FSMContext, repos: Repos, items: list[dict], lang: str, edit: bool):
    """target — Message; используем target.chat.id как tg_id (совпадает в приватном чате с ботом)."""
    user_tg_id = target.chat.id
    category = items[0].get("category") if items else None
    await state.update_data(checkout_category=category)

    saved_size = await repos.users.get_size(user_tg_id, category) if category else None

    if saved_size:
        text = (
            _cart_lines(items) + f"\n\n📏 У вас сохранён размер для этой категории: <b>{saved_size}</b>\n"
            "Использовать его или указать другой?"
        )
        kb = kb_reuse_or_manual(f"Использовать {saved_size}", "checkout:size:saved", "checkout:size:manual")
        if edit:
            await target.edit_text(text, reply_markup=kb)
        else:
            await target.answer(text, reply_markup=kb)
    else:
        await state.set_state(CartStates.waiting_size)
        text = _cart_lines(items) + "\n\n" + t(lang, "ask_size")
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)


@router.callback_query(F.data == "checkout:size:saved")
async def cb_size_saved(call: CallbackQuery, state: FSMContext, repos: Repos):
    data = await state.get_data()
    category = data.get("checkout_category")
    size = await repos.users.get_size(call.from_user.id, category)
    await state.update_data(size=size or "—")
    await _ask_comment_step(call.message, state, repos, call.from_user.id, edit=True)
    await call.answer()


@router.callback_query(F.data == "checkout:size:manual")
async def cb_size_manual(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.set_state(CartStates.waiting_size)
    await call.message.edit_text(t(lang, "ask_size"))
    await call.answer()


@router.message(CartStates.waiting_size)
async def msg_size(message: Message, state: FSMContext, repos: Repos):
    await state.update_data(size=message.text.strip())
    await _ask_comment_step(message, state, repos, message.from_user.id, edit=False)


async def _ask_comment_step(target, state: FSMContext, repos: Repos, user_tg_id: int, edit: bool):
    """Показывает либо вариант 'использовать прошлый адрес', либо просит ввести новый."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    last_address = await repos.users.get_last_address(user_tg_id)

    if last_address:
        text = f"💬 Ваш сохранённый адрес/комментарий:\n<i>{last_address}</i>\n\nИспользовать его или указать другой?"
        kb = kb_reuse_or_manual("Использовать этот", "checkout:comment:saved", "checkout:comment:manual")
        if edit:
            await target.edit_text(text, reply_markup=kb)
        else:
            await target.answer(text, reply_markup=kb)
    else:
        await state.set_state(CartStates.waiting_comment)
        if edit:
            await target.edit_text(t(lang, "ask_comment"))
        else:
            await target.answer(t(lang, "ask_comment"))


@router.callback_query(F.data == "checkout:comment:saved")
async def cb_comment_saved(call: CallbackQuery, state: FSMContext, repos: Repos, bot: Bot):
    last_address = await repos.users.get_last_address(call.from_user.id) or "—"
    await state.update_data(comment=last_address)
    await _finalize_order(call.message, state, repos, bot, call.from_user.id, edit=True)
    await call.answer()


@router.callback_query(F.data == "checkout:comment:manual")
async def cb_comment_manual(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.set_state(CartStates.waiting_comment)
    await call.message.edit_text(t(lang, "ask_comment"))
    await call.answer()


@router.message(CartStates.waiting_comment)
async def msg_comment(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    await state.update_data(comment=message.text.strip())
    await _finalize_order(message, state, repos, bot, message.from_user.id, edit=False)


async def _finalize_order(target, state: FSMContext, repos: Repos, bot: Bot, user_tg_id: int, edit: bool):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    size = data.get("size", "—")
    comment = data.get("comment", "—")
    items = data.get("cart_items", [])
    category = data.get("checkout_category")
    await state.clear()

    items_for_order = [
        {"post_id": it["post_id"], "title": it.get("title"), "price": it.get("price"),
         "photo_file_id": it.get("photo_file_id"), "brand_id": it.get("brand_id")}
        for it in items
    ]
    order_id = await repos.orders.create(user_tg_id, items_for_order, size, comment)

    # Запоминаем размер (по категории) и адрес/комментарий для следующего заказа
    if category:
        await repos.users.set_size(user_tg_id, category, size)
    await repos.users.set_last_address(user_tg_id, comment)

    text = t(lang, "order_received", order_id=order_id)
    main_kb = await client_menu_kb(repos, user_tg_id, lang)
    if edit:
        await target.edit_text(text)
        await target.answer(t(lang, "main_menu"), reply_markup=main_kb)
    else:
        await target.answer(text, reply_markup=main_kb)

    # Отдельным сообщением — кнопки редактирования/отмены, пока заказ не подтверждён админом
    edit_hint = await tr(
        repos,
        "Если заметили ошибку в размере или адресе — можно исправить, пока заказ не подтверждён администратором:",
        lang,
    )
    try:
        await bot.send_message(user_tg_id, edit_hint, reply_markup=await kb_my_order(repos, lang, order_id))
    except Exception:
        pass

    await repos.cart.clear(user_tg_id)

    user = await repos.users.get(user_tg_id)
    username = f"@{user.get('username')}" if user and user.get("username") else f"ID {user_tg_id}"
    phone = user.get("phone", "—") if user else "—"

    admin_text = (
        f"🛍 <b>Новый заказ #{order_id}</b>\n\n"
        f"👤 Клиент: {username}\n📱 Телефон: {phone}\n📏 Размер: {size}\n💬 Комментарий: {comment}\n\n"
        "<b>Товары:</b>\n" + _cart_lines(items)
    )

    online_ids = await repos.staff.online_ids("admin")
    for admin_tg_id in online_ids:
        try:
            await bot.send_message(admin_tg_id, admin_text, reply_markup=kb_order_confirm(order_id))
        except Exception:
            pass


# ── Уточнение деталей заказа у клиента (по запросу админа) ──────────

@router.callback_query(F.data.startswith("order:verify:"))
async def cb_order_verify(call: CallbackQuery, repos: Repos, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    user = await repos.users.get(order["user_tg_id"])
    lang = user.get("language", "ru") if user else "ru"

    heading_template = await tr(repos, "🔎 Пожалуйста, проверьте детали вашего заказа #ORDERID:", lang)
    heading = heading_template.replace("ORDERID", str(order_id))
    size_label = await tr(repos, "Размер", lang)
    address_label = await tr(repos, "Адрес/комментарий", lang)
    question = await tr(repos, "Всё верно?", lang)
    verify_text = (
        f"🔎 <b>{heading}</b>\n\n"
        f"📏 {size_label}: <b>{order.get('size','—')}</b>\n"
        f"💬 {address_label}: <b>{order.get('comment','—')}</b>\n\n"
        f"{question}"
    )
    try:
        await bot.send_message(order["user_tg_id"], verify_text, reply_markup=await kb_client_verify(repos, lang, order_id))
    except Exception:
        await call.answer("❌ Не удалось связаться с клиентом.", show_alert=True)
        return

    await call.message.edit_text(
        call.message.text + f"\n\n📞 <b>Отправлен запрос клиенту на проверку заказа #{order_id}.</b>",
        reply_markup=kb_order_confirm(order_id),
    )
    await call.answer("Запрос отправлен клиенту")


@router.callback_query(F.data.startswith("client:verify_ok:"))
async def cb_client_verify_ok(call: CallbackQuery, repos: Repos, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await repos.orders.set_client_verified(order_id, True)
    await call.message.edit_text("✅ Спасибо, заказ подтверждён! Передаём администратору.")
    await call.answer()

    online_ids = await repos.staff.online_ids("admin")
    items = await repos.orders.get_items(order_id)
    lines = "\n".join(f"• {it.get('title','?')} — {it.get('price','—')}" for it in items)
    notify_text = (
        f"✅ <b>Клиент подтвердил заказ #{order_id}</b>\n\n"
        f"📏 Размер: {order.get('size','—')}\n💬 Адрес: {order.get('comment','—')}\n\n{lines}"
    )
    for admin_tg_id in online_ids:
        try:
            await bot.send_message(admin_tg_id, notify_text, reply_markup=kb_order_confirm(order_id, verified=True))
        except Exception:
            pass


async def _start_order_fix(message_target, state: FSMContext, order_id: int, lang: str):
    await state.set_state(CartStates.fixing_size)
    await state.update_data(fixing_order_id=order_id, lang=lang)
    await message_target.edit_text(t(lang, "ask_size"))


@router.callback_query(F.data.startswith("client:verify_fix:"))
async def cb_client_verify_fix(call: CallbackQuery, state: FSMContext, repos: Repos):
    order_id = int(call.data.split(":")[2])
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    await _start_order_fix(call.message, state, order_id, lang)
    await call.answer()


# ── Клиент сам редактирует/отменяет свой заказ (пока не подтверждён) ─

@router.callback_query(F.data.startswith("myorder:edit:"))
async def cb_myorder_edit(call: CallbackQuery, state: FSMContext, repos: Repos):
    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    if not order or order["user_tg_id"] != call.from_user.id:
        await call.answer(await tr(repos, "❌ Заказ не найден", lang), show_alert=True)
        return
    if order["status"] != "pending":
        msg = await tr(
            repos,
            "⚠️ Заказ уже обрабатывается администратором, изменить его больше нельзя. "
            "Напишите в поддержку, если нужно что-то поправить.",
            lang,
        )
        await call.answer(msg, show_alert=True)
        return

    await _start_order_fix(call.message, state, order_id, lang)
    await call.answer()


@router.callback_query(F.data.startswith("myorder:cancel:"))
async def cb_myorder_cancel(call: CallbackQuery, repos: Repos, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    if not order or order["user_tg_id"] != call.from_user.id:
        await call.answer(await tr(repos, "❌ Заказ не найден", lang), show_alert=True)
        return
    if order["status"] != "pending":
        msg = await tr(
            repos,
            "⚠️ Заказ уже обрабатывается администратором, отменить его самостоятельно нельзя. "
            "Напишите в поддержку.",
            lang,
        )
        await call.answer(msg, show_alert=True)
        return

    await repos.orders.update_status(order_id, "cancelled")
    cancel_template = await tr(repos, "❌ Заказ #ORDERID отменён.", lang)
    await call.message.edit_text(cancel_template.replace("ORDERID", str(order_id)))
    await call.answer()

    online_ids = await repos.staff.online_ids("admin")
    for admin_tg_id in online_ids:
        try:
            await bot.send_message(admin_tg_id, f"❌ Клиент сам отменил заказ #{order_id} до подтверждения.")
        except Exception:
            pass


@router.message(CartStates.fixing_size)
async def msg_fix_size(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(fix_size=message.text.strip())
    await state.set_state(CartStates.fixing_comment)
    await message.answer(t(lang, "ask_comment"))


@router.message(CartStates.fixing_comment)
async def msg_fix_comment(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    data = await state.get_data()
    order_id = data.get("fixing_order_id")
    new_size = data.get("fix_size", "—")
    new_comment = message.text.strip()
    await state.clear()

    await repos.orders.update_details(order_id, size=new_size, comment=new_comment)
    await repos.orders.set_client_verified(order_id, True)
    await repos.users.set_last_address(message.from_user.id, new_comment)

    await message.answer("✅ Спасибо, данные обновлены! Передаём администратору.")

    online_ids = await repos.staff.online_ids("admin")
    items = await repos.orders.get_items(order_id)
    lines = "\n".join(f"• {it.get('title','?')} — {it.get('price','—')}" for it in items)
    notify_text = (
        f"✏️ <b>Клиент исправил данные заказа #{order_id}</b>\n\n"
        f"📏 Новый размер: {new_size}\n💬 Новый адрес: {new_comment}\n\n{lines}"
    )
    for admin_tg_id in online_ids:
        try:
            await bot.send_message(admin_tg_id, notify_text, reply_markup=kb_order_confirm(order_id, verified=True))
        except Exception:
            pass


@router.callback_query(F.data.startswith("wnotify:"))
async def cb_wnotify(call: CallbackQuery, repos: Repos):
    """Кнопка '🔔 Уведомить, когда появится' прямо под постом в канале отчётов склада."""
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    post_id = int(call.data.split(":")[1])
    post = await repos.posts.get(post_id)
    if not post:
        await call.answer(await tr(repos, "❌ Товар не найден", lang), show_alert=True)
        return
    if post.get("in_stock", True):
        await call.answer(await tr(repos, "✅ Товар уже в наличии!", lang), show_alert=True)
        return
    await repos.posts.add_interest(post_id, call.from_user.id)
    await call.answer(await tr(repos, "🔔 Хорошо! Мы напишем вам, как только товар появится.", lang), show_alert=True)


# ── Подтверждение/отмена заказа (админ) ─────────────────────────────

@router.callback_query(F.data.startswith("order:confirm:"))
async def cb_order_confirm(call: CallbackQuery, repos: Repos, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await repos.orders.update_status(order_id, "confirmed")

    user = await repos.users.get(order["user_tg_id"])
    lang = user.get("language", "ru") if user else "ru"
    try:
        confirm_template = await tr(repos, "✅ Ваш заказ #ORDERID подтверждён!\n\nСкоро с вами свяжутся.", lang)
        await bot.send_message(order["user_tg_id"], confirm_template.replace("ORDERID", str(order_id)))
    except Exception:
        pass

    wh_workers = await repos.staff.list_by_role("warehouse")
    items = await repos.orders.get_items(order_id)
    lines = "\n".join(f"• {it.get('title','?')} — {it.get('price','—')} (р. {it.get('size','—')})" for it in items)
    wh_text = f"📦 <b>Заказ #{order_id} подтверждён</b>\n\n{lines}\n\nПримите через /warehouse"
    for wh in wh_workers:
        if wh.get("tg_id"):
            try:
                await bot.send_message(wh["tg_id"], wh_text)
            except Exception:
                pass

    await call.message.edit_text(call.message.text + f"\n\n✅ <b>Подтверждено {call.from_user.first_name}</b>")
    await call.answer("✅ Подтверждено")


@router.callback_query(F.data.startswith("order:cancel:"))
async def cb_order_cancel(call: CallbackQuery, repos: Repos, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await repos.orders.update_status(order_id, "cancelled")
    user = await repos.users.get(order["user_tg_id"])
    lang = user.get("language", "ru") if user else "ru"
    try:
        cancel_template = await tr(repos, "❌ Заказ #ORDERID отменён.", lang)
        await bot.send_message(order["user_tg_id"], cancel_template.replace("ORDERID", str(order_id)))
    except Exception:
        pass

    await call.message.edit_text(call.message.text + f"\n\n❌ <b>Отменено {call.from_user.first_name}</b>")
    await call.answer("❌ Отменено")


# ── Wishlist ─────────────────────────────────────────────────────────

@router.message(ButtonText("btn_wishlist"))
async def msg_wishlist(message: Message, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    if not user:
        return
    lang = user.get("language", "ru")
    items = await repos.cart.wish_get(message.from_user.id)

    if not items:
        await message.answer(t(lang, "wishlist_empty"))
        return
    wishlist_title = await tt(repos, lang, "wishlist_title")
    await message.answer(wishlist_title + _cart_lines(items), reply_markup=await kb_wishlist(repos, lang, items))


@router.callback_query(F.data == "go:wishlist")
async def cb_go_wishlist(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    items = await repos.cart.wish_get(call.from_user.id)

    if not items:
        await call.message.edit_text(t(lang, "wishlist_empty"))
        await call.answer()
        return
    wishlist_title = await tt(repos, lang, "wishlist_title")
    await call.message.edit_text(wishlist_title + _cart_lines(items), reply_markup=await kb_wishlist(repos, lang, items))
    await call.answer()


@router.callback_query(F.data.startswith("wish:to_cart:"))
async def cb_wish_to_cart(call: CallbackQuery, repos: Repos):
    wish_id = int(call.data.split(":")[2])
    items = await repos.cart.wish_get(call.from_user.id)
    item = next((i for i in items if i["wish_id"] == wish_id), None)
    if not item:
        await call.answer()
        return
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    if not item.get("in_stock", True):
        await repos.posts.add_interest(item["post_id"], call.from_user.id)
        msg = await tr(
            repos,
            "😔 «PRODUCTNAME» закончился, но скоро снова появится!\nМы напишем вам, как только товар будет в наличии.",
            lang,
        )
        await call.answer(msg.replace("PRODUCTNAME", item.get("title") or "?"), show_alert=True)
        return

    added = await repos.cart.add(call.from_user.id, item["post_id"])
    await call.answer(t(lang, "added_to_cart") if added else t(lang, "already_in_cart"))


@router.callback_query(F.data.startswith("wish:remove:"))
async def cb_wish_remove(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    wish_id = int(call.data.split(":")[2])
    await repos.cart.wish_remove(wish_id, call.from_user.id)

    items = await repos.cart.wish_get(call.from_user.id)
    if not items:
        await call.message.edit_text(t(lang, "wishlist_empty"))
        await call.answer("🗑")
        return
    wishlist_title = await tt(repos, lang, "wishlist_title")
    await call.message.edit_text(wishlist_title + _cart_lines(items), reply_markup=await kb_wishlist(repos, lang, items))
    await call.answer("🗑")


# ── Мой заказ / История заказов ──────────────────────────────────────

async def _order_summary_text(repos: Repos, order: dict, items: list[dict], lang: str) -> str:
    from db.repo_orders import status_label

    lines = "\n".join(f"• {it.get('title','?')} — {it.get('price','—')}" for it in items)
    status_text = await tr(repos, status_label(order["status"]), lang)
    status_word = await tr(repos, "Статус", lang)
    size_word = await tr(repos, "Размер", lang)
    address_word = await tr(repos, "Адрес", lang)

    template = await tr(repos, "📦 Заказ #ORDERID", lang)
    heading = template.replace("ORDERID", str(order["id"]))

    return (
        f"{heading}\n"
        f"{status_word}: <b>{status_text}</b>\n\n"
        f"{lines}\n\n"
        f"📏 {size_word}: {order.get('size','—')}\n💬 {address_word}: {order.get('comment','—')}"
    )


@router.message(ButtonText("btn_my_order"))
async def msg_my_order(message: Message, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    order = await repos.orders.active_for_user(message.from_user.id)
    if not order:
        await message.answer(await tr(repos, "📭 У вас сейчас нет активных заказов.", lang))
        return

    items = await repos.orders.get_items(order["id"])
    text = await _order_summary_text(repos, order, items, lang)

    kb_rows = []
    if order["status"] == "pending":
        edit_btn = await tr(repos, "✏️ Изменить размер/адрес", lang)
        cancel_btn = await tr(repos, "❌ Отменить заказ", lang)
        kb_rows.append([InlineKeyboardButton(text=edit_btn, callback_data=f"myorder:edit:{order['id']}")])
        kb_rows.append([InlineKeyboardButton(text=cancel_btn, callback_data=f"myorder:cancel:{order['id']}")])

    if kb_rows:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    else:
        await message.answer(text)


@router.message(ButtonText("btn_order_history"))
async def msg_order_history(message: Message, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    orders = await repos.orders.history_for_user(message.from_user.id)
    if not orders:
        await message.answer(await tr(repos, "📭 У вас пока нет подтверждённых заказов.", lang))
        return

    from db.repo_orders import status_label

    heading = await tr(repos, "📜 История заказов", lang)
    lines = [f"📜 <b>{heading}</b>\n"]
    reorder_btn_text = await tt(repos, lang, "btn_reorder")
    kb_rows = []
    for o in orders[:20]:
        status_text = await tr(repos, status_label(o["status"]), lang)
        lines.append(f"#{o['id']} — {status_text} ({str(o.get('created_at',''))[:10]})")
        kb_rows.append([InlineKeyboardButton(
            text=f"{reorder_btn_text} — #{o['id']}", callback_data=f"reorder:start:{o['id']}"
        )])

    text = "\n".join(lines)
    if len(orders) > 20:
        more_template = await tr(repos, "…и ещё COUNT", lang)
        text += "\n\n" + more_template.replace("COUNT", str(len(orders) - 20))

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else None
    await message.answer(text, reply_markup=kb)


# ── «Заказать снова» ──────────────────────────────────────────────────

async def _notify_warehouse_restock(bot: Bot, repos: Repos, title: str, price: str,
                                     photo_file_id: str | None, gender: str | None, username: str):
    """Активно пингует склад, что клиент хочет повторить заказ товара, которого нет в наличии."""
    text = (
        f"🔁 <b>Запрос на дозаказ</b>\n\n"
        f"🏷 {title}\n💰 {price}\n\n"
        f"👤 Клиент {username} пытался заказать этот товар снова, но он сейчас отсутствует."
    )
    report_channel = await repos.settings.get(f"report_channel_{gender}_chat_id") if gender else None
    if report_channel:
        try:
            if photo_file_id:
                await bot.send_photo(report_channel, photo_file_id, caption=text)
            else:
                await bot.send_message(report_channel, text)
        except Exception:
            pass
    wh_ids = await repos.staff.online_ids("warehouse")
    for wh_id in wh_ids:
        try:
            await bot.send_message(wh_id, text)
        except Exception:
            pass


async def _split_reorder_items(repos: Repos, items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Проверяет каждую позицию старого заказа по актуальному состоянию каталога.
    Возвращает (доступные_сейчас, недоступные) — доступные обновлены свежими
    ценой/фото/названием на случай, если они изменились с прошлого заказа.
    """
    available, unavailable = [], []
    for it in items:
        post = await repos.posts.get(it["post_id"]) if it.get("post_id") else None
        if post and post.get("in_stock", True):
            available.append({
                "post_id": post["id"], "title": post.get("title") or it.get("title"),
                "price": post.get("price") or it.get("price"),
                "photo_file_id": post.get("photo_file_id") or it.get("photo_file_id"),
                "brand_id": post.get("brand_id") or it.get("brand_id"),
                "gender": post.get("gender"), "category": post.get("category"),
            })
        else:
            unavailable.append({
                "post_id": it.get("post_id"),
                "title": (post.get("title") if post else None) or it.get("title", "?"),
                "price": (post.get("price") if post else None) or it.get("price", "—"),
                "photo_file_id": (post.get("photo_file_id") if post else None) or it.get("photo_file_id"),
                "gender": post.get("gender") if post else None,
            })
    return available, unavailable


@router.callback_query(F.data.startswith("reorder:start:"))
async def cb_reorder_start(call: CallbackQuery, repos: Repos, bot: Bot):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order or order["user_tg_id"] != call.from_user.id:
        await call.answer(await tr(repos, "❌ Заказ не найден", lang), show_alert=True)
        return

    items = await repos.orders.get_items(order_id)
    available, unavailable = await _split_reorder_items(repos, items)
    username = f"@{user.get('username')}" if user and user.get("username") else f"ID {call.from_user.id}"

    if unavailable:
        for it in unavailable:
            if it.get("post_id"):
                await repos.posts.add_interest(it["post_id"], call.from_user.id)
            await _notify_warehouse_restock(
                bot, repos, it["title"], it.get("price", "—"),
                it.get("photo_file_id"), it.get("gender"), username,
            )

    if not available:
        msg = await tt(repos, lang, "reorder_out_of_stock_all")
        titles = "\n".join(f"• {it['title']}" for it in unavailable)
        await call.answer()
        await call.message.answer(f"{msg}\n\n{titles}")
        return

    kb_rows = []
    repeat_label = (await tt(repos, lang, "reorder_repeat_btn")).format(size=order.get("size") or "—")
    fresh_label = await tt(repos, lang, "reorder_fresh_btn")
    kb_rows.append([InlineKeyboardButton(text=repeat_label, callback_data=f"reorder:repeat:{order_id}")])
    kb_rows.append([InlineKeyboardButton(text=fresh_label, callback_data=f"reorder:fresh:{order_id}")])

    lines = "\n".join(f"• {it['title']} — {it['price']}" for it in available)
    text = lines
    if unavailable:
        warn = await tt(repos, lang, "reorder_partial_out_of_stock")
        text = f"{warn}\n{lines}"

    await call.answer()
    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("reorder:repeat:"))
async def cb_reorder_repeat(call: CallbackQuery, repos: Repos, bot: Bot):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order or order["user_tg_id"] != call.from_user.id:
        await call.answer(await tr(repos, "❌ Заказ не найден", lang), show_alert=True)
        return

    items = await repos.orders.get_items(order_id)
    available, unavailable = await _split_reorder_items(repos, items)
    if not available:
        await call.answer(await tr(repos, "😔 Товар(ы) только что закончились. Оформление невозможно.", lang), show_alert=True)
        return

    size = order.get("size") or "—"
    comment = order.get("comment") or "—"
    category = available[0].get("category")

    new_order_id = await repos.orders.create(call.from_user.id, available, size, comment)
    if category:
        await repos.users.set_size(call.from_user.id, category, size)
    if comment and comment != "—":
        await repos.users.set_last_address(call.from_user.id, comment)

    await call.answer("✅")
    await call.message.edit_text(t(lang, "order_received", order_id=new_order_id))

    edit_hint = await tr(
        repos,
        "Если заметили ошибку в размере или адресе — можно исправить, пока заказ не подтверждён администратором:",
        lang,
    )
    try:
        await bot.send_message(call.from_user.id, edit_hint, reply_markup=await kb_my_order(repos, lang, new_order_id))
    except Exception:
        pass

    username = f"@{user.get('username')}" if user and user.get("username") else f"ID {call.from_user.id}"
    phone = user.get("phone", "—") if user else "—"
    admin_text = (
        f"🛍 <b>Новый заказ #{new_order_id}</b> (повтор заказа #{order_id})\n\n"
        f"👤 Клиент: {username}\n📱 Телефон: {phone}\n📏 Размер: {size}\n💬 Комментарий: {comment}\n\n"
        "<b>Товары:</b>\n" + _cart_lines(available)
    )
    online_ids = await repos.staff.online_ids("admin")
    for admin_tg_id in online_ids:
        try:
            await bot.send_message(admin_tg_id, admin_text, reply_markup=kb_order_confirm(new_order_id))
        except Exception:
            pass


@router.callback_query(F.data.startswith("reorder:fresh:"))
async def cb_reorder_fresh(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order or order["user_tg_id"] != call.from_user.id:
        await call.answer(await tr(repos, "❌ Заказ не найден", lang), show_alert=True)
        return

    items = await repos.orders.get_items(order_id)
    available, _ = await _split_reorder_items(repos, items)
    if not available:
        await call.answer(await tr(repos, "😔 Товар(ы) только что закончились.", lang), show_alert=True)
        return

    for it in available:
        await repos.cart.add(call.from_user.id, it["post_id"])

    checkout_btn = await tt(repos, lang, "btn_checkout")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=checkout_btn, callback_data="cart:checkout"),
    ]])
    await call.answer("✅")
    await call.message.edit_text(await tt(repos, lang, "reorder_added_to_cart"), reply_markup=kb)


# ── Подтверждение получения заказа и оценка ─────────────────────────

@router.callback_query(F.data.startswith("myorder:received:"))
async def cb_myorder_received(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    order_id = int(call.data.split(":")[2])
    order = await repos.orders.get(order_id)
    if not order or order["user_tg_id"] != call.from_user.id:
        await call.answer(await tr(repos, "❌ Заказ не найден", lang), show_alert=True)
        return

    if order["status"] not in ("shipping", "warehouse_received", "confirmed"):
        await call.answer()
        return

    await repos.orders.update_status(order_id, "delivered")

    prompt = (await tt(repos, lang, "order_rate_prompt")).format(order_id=order_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=await tt(repos, lang, "btn_rating_yes"), callback_data=f"orderrating:yes:{order_id}"),
        InlineKeyboardButton(text=await tt(repos, lang, "btn_rating_no"), callback_data=f"orderrating:no:{order_id}"),
    ]])
    await call.message.edit_text(prompt, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("orderrating:"))
async def cb_order_rating(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"

    _, verdict, order_id_str = call.data.split(":")
    order_id = int(order_id_str)
    order = await repos.orders.get(order_id)
    if not order or order["user_tg_id"] != call.from_user.id:
        await call.answer(await tr(repos, "❌ Заказ не найден", lang), show_alert=True)
        return

    await repos.orders.set_rating(order_id, 1 if verdict == "yes" else 0)
    key = "order_rate_thanks" if verdict == "yes" else "order_rate_sorry"
    await call.message.edit_text(await tt(repos, lang, key))
    await call.answer()