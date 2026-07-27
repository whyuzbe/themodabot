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

# ОБЯЗАТЕЛЬНО объявляем router в самом начале, перед любыми хендлерами!
router = Router()


class RegStates(StatesGroup):
    choosing_language = State()
    choosing_gender = State()
