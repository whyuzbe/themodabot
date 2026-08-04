from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from db.repos import Repos

router = Router()

ROLE_COMMANDS = {"manager": "manager", "admin": "admin", "warehouse": "warehouse"}

BOOTSTRAP_SYNC_FLAG = "bootstrap_manager_synced"


class AuthStates(StatesGroup):
    waiting_login = State()
    waiting_password = State()


async def ensure_bootstrap_manager(repos: Repos):
    """
    Гарантирует, что аккаунт manager/<пароль из .env> реально доступен для входа.

    ИСПРАВЛЕНИЕ: раньше проверялось только "есть ли вообще хоть один менеджер"
    (count == 0), из-за чего если в базе уже был аккаунт manager с каким-то
    другим/непонятным паролем — .env-пароль никогда не подхватывался.

    Теперь: при первом запуске ПОСЛЕ этого фикса пароль аккаунта manager
    принудительно синхронизируется со значением из .env (создаём аккаунт,
    если его нет вовсе, либо сбрасываем пароль, если он уже существовал).
    Это происходит РОВНО ОДИН РАЗ — флаг bootstrap_manager_synced в settings
    защищает от повторного сброса, чтобы пароль, который потом сменят
    вручную через "🔑 Сменить пароль" в панели менеджера, не затирался
    при следующих рестартах бота.
    """
    already_synced = await repos.settings.get(BOOTSTRAP_SYNC_FLAG)
    if already_synced:
        return

    login = config.BOOTSTRAP_MANAGER_LOGIN
    password = config.BOOTSTRAP_MANAGER_PASSWORD

    account = await repos.staff.get_account("manager", login)
    if account is None:
        await repos.staff.create_account("manager", login, password)
    else:
        await repos.staff.change_password("manager", login, password)

    await repos.settings.set(BOOTSTRAP_SYNC_FLAG, "true")


async def require_role(tg_id: int, repos: Repos, role: str) -> dict | None:
    session = await repos.staff.get_session(tg_id)
    if session and session["role"] == role:
        return session
    return None


async def require_any_staff(tg_id: int, repos: Repos) -> dict | None:
    return await repos.staff.get_session(tg_id)


def _login_cmd(role: str):
    async def handler(message: Message, state: FSMContext, repos: Repos):
        session = await repos.staff.get_session(message.from_user.id)
        if session and session["role"] == role:
            await message.answer(f"✅ Вы уже вошли как {role}.")
            await _show_panel(message, role, session)
            return

        await state.set_state(AuthStates.waiting_login)
        await state.update_data(auth_role=role)
        await message.answer(f"🔐 <b>Вход ({role})</b>\n\nВведите логин:", parse_mode="HTML")
    return handler


router.message(Command("manager"))(_login_cmd("manager"))
router.message(Command("admin"))(_login_cmd("admin"))
router.message(Command("warehouse"))(_login_cmd("warehouse"))
router.message(Command("partner"))(_login_cmd("partner"))


@router.message(Command("logout"))
async def cmd_logout(message: Message, repos: Repos):
    await repos.staff.delete_session(message.from_user.id)
    await message.answer("👋 Вы вышли из системы.")


@router.message(AuthStates.waiting_login)
async def msg_login(message: Message, state: FSMContext):
    await state.update_data(login=message.text.strip())
    await state.set_state(AuthStates.waiting_password)
    await message.answer("🔑 Введите пароль:")


@router.message(AuthStates.waiting_password)
async def msg_password(message: Message, state: FSMContext, repos: Repos):
    data = await state.get_data()
    role = data.get("auth_role")
    login = data.get("login", "")
    password = message.text.strip()
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    account = await repos.staff.verify(role, login, password)
    if not account:
        await message.answer("❌ Неверный логин или пароль.")
        return

    await repos.staff.bind_tg(role, login, message.from_user.id)
    await repos.staff.create_session(message.from_user.id, role, login, hours=config.SESSION_HOURS)

    await message.answer("🔒", reply_markup=ReplyKeyboardRemove())
    await message.answer(f"✅ Добро пожаловать, {role} <b>{login}</b>!", parse_mode="HTML")

    session = await repos.staff.get_session(message.from_user.id)
    await _show_panel(message, role, session)


async def _show_panel(message: Message, role: str, session: dict):
    if role == "manager":
        from handlers.staff.manager import show_manager_panel
        await show_manager_panel(message)
    elif role == "admin":
        from handlers.staff.admin import show_admin_panel
        await show_admin_panel(message, session)
    elif role == "warehouse":
        from handlers.staff.warehouse import show_warehouse_panel
        await show_warehouse_panel(message)
    elif role == "partner":
        from handlers.staff.partner import show_partner_panel
        await show_partner_panel(message, session)
