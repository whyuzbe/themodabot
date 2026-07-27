from aiogram import Router

# Подключаем роутеры персонала (staff)
from .staff import admin, auth, manager, partner, warehouse

# Подключаем роутеры клиентов (client)
# (Добавлены основные модули клиента)
from .client import (
    support,
    # Если какие-то из этих файлов у тебя отсутствуют в client/,
    # просто убери их из импорта ниже:
)

# Главный роутер папки handlers
router = Router()

# Регистрируем все роутеры в диспетчере
router.include_routers(
    # Staff роутеры
    admin.router,
    auth.router,
    manager.router,
    partner.router,
    warehouse.router,
    # Client роутеры
    support.router,
)
