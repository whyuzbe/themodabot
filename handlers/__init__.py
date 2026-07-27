from aiogram import Router

# Подключаем роутеры персонала (staff)
from .staff import admin, auth, manager, partner, warehouse

# Подключаем роутеры клиентов (client)
from .client import start, cart, catalog, profile, support

# Главный роутер
router = Router()

# Регистрируем абсолютно все роутеры
router.include_routers(
    # Client
    start.router,
    cart.router,
    catalog.router,
    profile.router,
    support.router,
    # Staff
    admin.router,
    auth.router,
    manager.router,
    partner.router,
    warehouse.router,
)
