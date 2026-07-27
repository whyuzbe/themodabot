from aiogram import Router

# Подключаем роутеры персонала (staff)
from .staff import admin, auth, manager, partner, warehouse

# Подключаем ВСЕ роутеры клиентов (client)
from .client import (
    support,
    # Добавь сюда через запятую все файлы, которые у тебя есть в папке handlers/client/
    # Пример (раскомментируй то, что у тебя есть):
    # start,
    # catalog,
    # cart,
    # profile,
)

# Главный роутер
router = Router()

# Регистрируем все роутеры в диспетчере
router.include_routers(
    # Staff
    admin.router,
    auth.router,
    manager.router,
    partner.router,
    warehouse.router,
    # Client
    support.router,
    # Добавь сюда роутеры клиентов:
    # start.router,
    # catalog.router,
    # cart.router,
    # profile.router,
)
