from aiogram import Router

# Подключаем роутеры клиентской части
from .client import support  # добавь сюда другие файлы из client через запятую, если они есть

# Подключаем роутеры персонала
from .staff import admin, auth, manager, partner, warehouse

# Главный роутер папки handlers
router = Router()

# Регистрируем все роутеры
router.include_routers(
    admin.router,
    auth.router,
    manager.router,
    partner.router,
    warehouse.router,
    support.router,
)
