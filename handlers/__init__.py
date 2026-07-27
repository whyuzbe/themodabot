from aiogram import Router

# Подключаем роутеры персонала (staff)
from .staff import admin, auth, manager, partner, warehouse

# Подключаем роутеры клиентов (client)
from .client import cart, catalog, profile, start, support

# Главный роутер проекта
router = Router()

# Регистрируем абсолютно все роутеры
router.include_routers(
    # Client роутеры
    start.router,
    catalog.router,
    cart.router,
    profile.router,
    support.router,
    # Staff роутеры
    admin.router,
    auth.router,
    manager.router,
    partner.router,
    warehouse.router,
)
