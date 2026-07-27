"""
filters.py

F.text.in_([...]) работает только со статическим списком заранее известных
строк. Для динамически переводимых языков (любой код, не входящий в число
4 "быстрых") текст кнопки генерируется на лету и не совпадёт ни с одной
строкой из заранее заданного списка.

ButtonText — кастомный фильтр, который вместо сравнения со списком вычисляет,
каким должен быть текст этой кнопки именно для языка ЭТОГО конкретного
пользователя (через tt()), и сравнивает с этим. Работает одинаково для
статических и для динамически переведённых языков.
"""
from aiogram.filters import BaseFilter
from aiogram.types import Message

from db.repos import Repos
from locales.texts import tt


class ButtonText(BaseFilter):
    def __init__(self, key: str):
        self.key = key

    async def __call__(self, message: Message, repos: Repos) -> bool:
        if not message.text:
            return False
        user = await repos.users.get(message.from_user.id)
        lang = user.get("language", "ru") if user else "ru"
        expected = await tt(repos, lang, self.key)
        return message.text == expected