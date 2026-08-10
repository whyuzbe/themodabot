from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.repos import Repos
from translate import tr
from locales.texts import tt
from filters import ButtonText

router = Router()


class SupportStates(StatesGroup):
    waiting_question = State()
    admin_replying = State()


async def kb_client_in_dialog(repos, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=await tt(repos, lang, "btn_close_ticket"), callback_data="client:close_ticket")
    ]])


def kb_new_ticket(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✋ Взять в работу", callback_data=f"tkt:take:{ticket_id}")],
        [InlineKeyboardButton(text="⏳ В ожидание", callback_data=f"tkt:wait:{ticket_id}")],
    ])


def kb_in_progress(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ В ожидание", callback_data=f"tkt:wait:{ticket_id}")],
        [InlineKeyboardButton(text="✅ Завершить", callback_data=f"tkt:close:{ticket_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="tkt:back")],
    ])


async def kb_rating(repos, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=await tt(repos, lang, "btn_rating_yes"), callback_data="rating:yes"),
        InlineKeyboardButton(text=await tt(repos, lang, "btn_rating_no"), callback_data="rating:no"),
    ]])


def kb_admin_support_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Ожидающие", callback_data="tkt:list")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="tkt:mystats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:panel_back")],
    ])


def kb_waiting_list(tickets: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for tk in tickets:
        uname = f"@{tk['username']}" if tk.get("username") else f"ID {tk['user_tg_id']}"
        status = "🆕" if tk["status"] == "new" else "⏳"
        rows.append([InlineKeyboardButton(
            text=f"{status} {uname} — {(tk.get('last_message') or '')[:30]}",
            callback_data=f"tkt:take:{tk['id']}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="tkt:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def get_admin_session(tg_id: int, repos: Repos) -> dict | None:
    session = await repos.staff.get_session(tg_id)
    if session and session["role"] == "admin":
        return session
    return None


async def notifiable_admin_ids(repos: Repos, exclude_tg_id: int) -> list[int]:
    """
    Список онлайн-админов для уведомления, без самого клиента — на случай,
    если человек, написавший в поддержку, сам является админом. Админ не должен
    обрабатывать собственное обращение, его должен принять кто-то другой.
    """
    online_ids = await repos.staff.online_ids("admin")
    return [aid for aid in online_ids if aid != exclude_tg_id]


# ─────────────────────────────── КЛИЕНТ ───────────────────────────────

@router.message(ButtonText("btn_support"))
async def msg_support_open(message: Message, state: FSMContext, repos: Repos):
    user = await repos.users.get(message.from_user.id)
    if not user:
        return
    lang = user.get("language", "ru")

    existing = await repos.tickets.get_open_by_user(message.from_user.id)
    if existing:
        status_keys = {"new": "ticket_status_new", "waiting": "ticket_status_waiting", "in_progress": "ticket_status_in_progress"}
        status_key = status_keys.get(existing["status"], "ticket_status_new")
        status_label = await tt(repos, lang, status_key)
        heading = await tr(repos, "💬 У вас уже есть открытое обращение.\nСтатус:", lang)
        footer = await tr(repos, "Напишите следующее сообщение.", lang)
        await message.answer(f"{heading} {status_label}\n\n{footer}")
        await state.set_state(SupportStates.waiting_question)
        await state.update_data(lang=lang, ticket_id=existing["id"])
        return

    support_text = await repos.texts.get(f"text_support_{lang}")
    if not support_text:
        # ИСПРАВЛЕНИЕ: раньше здесь мог быть None (раздел "Тексты и баннер"
        # в панели менеджера — пока заглушка), а message.answer(None) падает
        # с исключением. Теперь есть переведённый запасной текст.
        support_text = await tt(repos, lang, "support_default_text")
    await state.set_state(SupportStates.waiting_question)
    await state.update_data(lang=lang)
    await message.answer(support_text)


@router.message(SupportStates.waiting_question)
async def msg_user_question(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    username = message.from_user.username
    text = message.text or "[медиа]"
    ticket_id = data.get("ticket_id")

    if ticket_id:
        ticket = await repos.tickets.get(ticket_id)
    else:
        ticket = None

    if ticket_id and ticket and ticket["status"] != "closed":
        await repos.tickets.add_message(ticket_id, "user", text)
        await repos.tickets.update(ticket_id, last_message=text)

        if ticket["status"] == "in_progress" and ticket.get("admin_tg_id"):
            try:
                await bot.send_message(
                    ticket["admin_tg_id"],
                    f"💬 <b>Новое сообщение</b>\n👤 @{username or '—'} (тикет #{ticket_id})\n\n{text}",
                    reply_markup=kb_in_progress(ticket_id),
                )
            except Exception:
                pass

        online_ids = await notifiable_admin_ids(repos, message.from_user.id)
        if not online_ids:
            await message.answer(
                await tr(repos, "😔 Сейчас нет свободных администраторов. Ваше обращение сохранено.", lang),
                reply_markup=await kb_client_in_dialog(repos, lang),
            )
        else:
            await message.answer(
                await tr(repos, "✉️ Сообщение отправлено.", lang),
                reply_markup=await kb_client_in_dialog(repos, lang),
            )
        return

    # Тикета не было, либо прошлый уже закрыт администратором — открываем новое обращение
    ticket_id = await repos.tickets.create(message.from_user.id, username, text)
    await state.update_data(ticket_id=ticket_id)

    online_ids = await notifiable_admin_ids(repos, message.from_user.id)
    if not online_ids:
        await message.answer(
            await tr(repos, "😔 Сейчас нет свободных администраторов. Ваше обращение сохранено.", lang),
            reply_markup=await kb_client_in_dialog(repos, lang),
        )
    else:
        await message.answer(
            await tr(repos, "✅ Вопрос отправлен!", lang),
            reply_markup=await kb_client_in_dialog(repos, lang),
        )

    for admin_tg_id in online_ids:
        try:
            await bot.send_message(
                admin_tg_id,
                f"🆕 <b>Новое обращение #{ticket_id}</b>\n👤 @{username or '—'} (ID: <code>{message.from_user.id}</code>)\n\n💬 {text}",
                reply_markup=kb_new_ticket(ticket_id),
            )
        except Exception:
            pass


@router.callback_query(F.data == "client:close_ticket")
async def cb_client_close_ticket(call: CallbackQuery, state: FSMContext, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    ticket = await repos.tickets.get_open_by_user(call.from_user.id)
    await state.clear()

    if ticket:
        # ИСПРАВЛЕНИЕ: closed_at в Postgres — колонка TIMESTAMPTZ, asyncpg не
        # принимает строку вместо настоящего datetime (падало с DataError).
        # Раньше здесь ещё и не проставлялся closed_at вовсе — теперь и то,
        # и другое исправлено разом.
        await repos.tickets.update(
            ticket["id"], status="closed",
            closed_at=datetime.now(),
        )

    await call.message.edit_text(await tr(repos, "✅ Обращение закрыто. Спасибо!", lang))
    await call.answer()


# ─────────────────────────────── ОЦЕНКА ───────────────────────────────

@router.callback_query(F.data == "rating:yes")
async def cb_rating_yes(call: CallbackQuery, repos: Repos):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    ticket = await repos.tickets.get_last_by_user(call.from_user.id)
    if ticket:
        await repos.tickets.update(ticket["id"], rating=1, status="closed")
    await call.message.edit_text(await tr(repos, "😊 Спасибо за оценку!", lang))
    await call.answer()


def kb_dissatisfied(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"tkt:reopen:{ticket_id}")],
        [InlineKeyboardButton(text="⏳ В ожидание", callback_data=f"tkt:wait_after_no:{ticket_id}")],
    ])


@router.callback_query(F.data == "rating:no")
async def cb_rating_no(call: CallbackQuery, repos: Repos, bot: Bot):
    user = await repos.users.get(call.from_user.id)
    lang = user.get("language", "ru") if user else "ru"
    ticket = await repos.tickets.get_last_by_user(call.from_user.id)
    if not ticket:
        await call.answer()
        return

    await repos.tickets.update(ticket["id"], rating=0, status="in_progress")
    await call.message.edit_text(await tr(repos, "😔 Жаль! Администратор снова свяжется с вами.", lang))

    if ticket.get("admin_tg_id"):
        try:
            await bot.send_message(
                ticket["admin_tg_id"],
                f"⚠️ <b>Клиент недоволен</b> — тикет #{ticket['id']}\n\nВыберите действие:",
                reply_markup=kb_dissatisfied(ticket["id"]),
            )
        except Exception:
            pass
    await call.answer()


@router.callback_query(F.data.startswith("tkt:reopen:"))
async def cb_ticket_reopen(call: CallbackQuery, state: FSMContext, repos: Repos):
    session = await get_admin_session(call.from_user.id, repos)
    if not session:
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    ticket_id = int(call.data.split(":")[2])
    ticket = await repos.tickets.get(ticket_id)
    if not ticket:
        await call.answer("❌ Тикет не найден", show_alert=True)
        return

    await state.set_state(SupportStates.admin_replying)
    await state.update_data(ticket_id=ticket_id, admin_login=session["login"])
    await call.message.edit_text(f"🔄 Тикет #{ticket_id}\n\n✍️ Напишите ответ клиенту:", reply_markup=kb_in_progress(ticket_id))
    await call.answer()


@router.callback_query(F.data.startswith("tkt:wait_after_no:"))
async def cb_wait_after_no(call: CallbackQuery, state: FSMContext, repos: Repos, bot: Bot):
    session = await get_admin_session(call.from_user.id, repos)
    if not session:
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    ticket_id = int(call.data.split(":")[2])
    ticket = await repos.tickets.get(ticket_id)
    await repos.tickets.update(ticket_id, status="waiting")
    await state.clear()

    online_ids = await notifiable_admin_ids(repos, ticket.get("user_tg_id"))
    for adm_id in online_ids:
        admin_acc = await repos.staff.get_by_tg(adm_id)
        if admin_acc and admin_acc.get("login") == ticket.get("admin_login"):
            continue
        try:
            await bot.send_message(adm_id, f"⏳ Тикет #{ticket_id} ожидает помощи.", reply_markup=kb_new_ticket(ticket_id))
        except Exception:
            pass

    await call.message.edit_text(f"⏳ Тикет #{ticket_id} переведён в ожидание.", reply_markup=kb_admin_support_menu())
    await call.answer()


# ─────────────────────────────── АДМИН ───────────────────────────────

@router.callback_query(F.data == "tkt:back")
async def cb_tkt_back(call: CallbackQuery, state: FSMContext, repos: Repos):
    if not await get_admin_session(call.from_user.id, repos):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text("🎧 <b>Поддержка</b>", reply_markup=kb_admin_support_menu())
    await call.answer()


@router.callback_query(F.data == "tkt:list")
async def cb_ticket_list(call: CallbackQuery, repos: Repos):
    if not await get_admin_session(call.from_user.id, repos):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    tickets = await repos.tickets.open_list()
    if not tickets:
        await call.message.edit_text("📭 Нет ожидающих обращений.", reply_markup=kb_admin_support_menu())
        await call.answer()
        return

    await call.message.edit_text(f"📋 <b>Ожидающие ({len(tickets)})</b>", reply_markup=kb_waiting_list(tickets))
    await call.answer()


@router.callback_query(F.data.startswith("tkt:take:"))
async def cb_ticket_take(call: CallbackQuery, state: FSMContext, repos: Repos, bot: Bot):
    session = await get_admin_session(call.from_user.id, repos)
    if not session:
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    ticket_id = int(call.data.split(":")[2])
    ticket = await repos.tickets.get(ticket_id)
    admin_login = session["login"]
    if not ticket:
        await call.answer("❌ Тикет не найден", show_alert=True)
        return

    if ticket["user_tg_id"] == call.from_user.id:
        await call.answer(
            "🚫 Это ваше собственное обращение — обработать его должен другой администратор.",
            show_alert=True,
        )
        return

    if ticket["status"] == "in_progress" and ticket.get("admin_tg_id") != call.from_user.id:
        await call.answer(f"⚠️ Уже взят {ticket.get('admin_login','?')}", show_alert=True)
        return

    await repos.tickets.update(
        ticket_id, status="in_progress", admin_login=admin_login,
        admin_tg_id=call.from_user.id, taken_at=datetime.now(),
    )

    messages = await repos.tickets.get_messages(ticket_id)
    history = "\n".join(f"{'👤' if m['sender']=='user' else '🛠'} {m['text']}" for m in messages[-10:])

    await state.set_state(SupportStates.admin_replying)
    await state.update_data(ticket_id=ticket_id, admin_login=admin_login)
    await call.message.edit_text(
        f"🔄 <b>Тикет #{ticket_id} — в работе</b>\n\n{history or '—'}\n\n✍️ Напишите ответ:",
        reply_markup=kb_in_progress(ticket_id),
    )

    online_ids = await repos.staff.online_ids("admin")
    for adm_id in online_ids:
        if adm_id == call.from_user.id:
            continue
        try:
            await bot.send_message(adm_id, f"ℹ️ Тикет #{ticket_id} взят <b>{admin_login}</b>.")
        except Exception:
            pass
    await call.answer()


@router.callback_query(F.data.startswith("tkt:wait:"))
async def cb_ticket_wait(call: CallbackQuery, state: FSMContext, repos: Repos, bot: Bot):
    if not await get_admin_session(call.from_user.id, repos):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    ticket_id = int(call.data.split(":")[2])
    ticket = await repos.tickets.get(ticket_id)
    await repos.tickets.update(ticket_id, status="waiting")
    await state.clear()

    online_ids = await notifiable_admin_ids(repos, ticket.get("user_tg_id") if ticket else None)
    for adm_id in online_ids:
        if adm_id == call.from_user.id:
            continue
        try:
            await bot.send_message(adm_id, f"⏳ Тикет #{ticket_id} в ожидании.", reply_markup=kb_new_ticket(ticket_id))
        except Exception:
            pass

    await call.message.edit_text(f"⏳ Тикет #{ticket_id} переведён в ожидание.", reply_markup=kb_admin_support_menu())
    await call.answer()


@router.callback_query(F.data.startswith("tkt:close:"))
async def cb_ticket_close(call: CallbackQuery, state: FSMContext, repos: Repos, bot: Bot):
    if not await get_admin_session(call.from_user.id, repos):
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    ticket_id = int(call.data.split(":")[2])
    ticket = await repos.tickets.get(ticket_id)
    if not ticket:
        await call.answer("❌ Тикет не найден", show_alert=True)
        return

    await repos.tickets.update(ticket_id, status="closed", closed_at=datetime.now())
    await state.clear()

    user = await repos.users.get(ticket["user_tg_id"])
    lang = user.get("language", "ru") if user else "ru"
    try:
        await bot.send_message(
            ticket["user_tg_id"],
            await tr(repos, "🙏 Спасибо что обратились! Довольны ли вы поддержкой?", lang),
            reply_markup=await kb_rating(repos, lang),
        )
    except Exception:
        pass

    await call.message.edit_text(f"✅ Тикет #{ticket_id} закрыт.", reply_markup=kb_admin_support_menu())
    await call.answer()


@router.message(SupportStates.admin_replying)
async def msg_admin_reply(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    session = await get_admin_session(message.from_user.id, repos)
    if not session:
        await state.clear()
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        return

    ticket = await repos.tickets.get(ticket_id)
    if not ticket:
        await state.clear()
        return

    text = message.text or ""
    await repos.tickets.add_message(ticket_id, "admin", text)
    await repos.tickets.update(ticket_id, last_message=f"[Админ]: {text}")

    user = await repos.users.get(ticket["user_tg_id"])
    lang = user.get("language", "ru") if user else "ru"
    prefix = await tr(repos, "💬 <b>Ответ от поддержки:</b>\n\n", lang)

    try:
        await bot.send_message(ticket["user_tg_id"], prefix + text)
    except Exception:
        await message.answer("❌ Не удалось доставить сообщение.")
        return

    await message.answer(f"✅ Ответ доставлен (тикет #{ticket_id})", reply_markup=kb_in_progress(ticket_id))


@router.callback_query(F.data == "tkt:mystats")
async def cb_my_ticket_stats(call: CallbackQuery, repos: Repos):
    session = await get_admin_session(call.from_user.id, repos)
    if not session:
        await call.answer("❌ Сессия истекла", show_alert=True)
        return

    s = await repos.tickets.admin_stats_today(session["login"])
    text = (
        f"📊 <b>Моя статистика за сегодня</b>\n\n"
        f"✋ Взято: <b>{s['taken']}</b>\n✅ Закрыто: <b>{s['closed']}</b>\n⏳ В ожидании: <b>{s['waiting']}</b>\n\n"
        f"👍 <b>{s['satisfied']}</b>  👎 <b>{s['unsatisfied']}</b>"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="tkt:back")]
    ]))
    await call.answer()
