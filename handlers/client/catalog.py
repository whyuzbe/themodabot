from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

router = Router()

# Пример базы данных (замени на реальный запрос к БД/ORM)
MOCK_PRODUCTS = [
    {
        "id": 1,
        "title": "Nike Air Force 1 '07",
        "price": 120,
        "category": "Кроссовки",
        "photo": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a",
        "description": "Классика баскетбольного стиля. Натуральная кожа, амортизация Air."
    },
    {
        "id": 2,
        "title": "Adidas Ultraboost Light",
        "price": 180,
        "category": "Кроссовки",
        "photo": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2",
        "description": "Легчайшая амортизация Boost для максимального комфорта каждый день."
    },
    {
        "id": 3,
        "title": "Puma Velocity Nitro 2",
        "price": 110,
        "category": "Бег",
        "photo": "https://images.unsplash.com/photo-1542291026-7eec264c27ff",
        "description": "Универсальные беговые кроссовки с пеной NITRO для отличного отклика."
    },
    {
        "id": 4,
        "title": "New Balance 530",
        "price": 130,
        "category": "Кроссовки",
        "photo": "https://images.unsplash.com/photo-1539185441755-769473a23570",
        "description": "Ретро-силуэт в стиле 2000-х. Легкие, дышащие и очень стильные."
    }
]


def get_catalog_keyboard(page: int, total_pages: int, product_id: int) -> InlineKeyboardMarkup:
    """Формирует клавиатуру с пагинацией и кнопками действий."""
    nav_buttons = []
    
    # Кнопка «Назад»
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"catalog_page:{page - 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text="⛔️", callback_data="noop"))

    # Счетчик страниц
    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))

    # Кнопка «Вперед»
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"catalog_page:{page + 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text="⛔️", callback_data="noop"))

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            nav_buttons,
            [
                InlineKeyboardButton(text="🛒 В корзину", callback_data=f"add_to_cart:{product_id}"),
                InlineKeyboardButton(text="❤️ В избранное", callback_data=f"add_to_fav:{product_id}")
            ],
            [
                InlineKeyboardButton(text="🔍 Фильтр / Поиск", callback_data="catalog_search")
            ]
        ]
    )
    return keyboard


def format_product_caption(product: dict) -> str:
    """Красиво оформляет текст карточки товара."""
    return (
        f"👟 **{product['title']}**\n\n"
        f"📝 {product['description']}\n\n"
        f"🏷 Категория: #{product['category']}\n"
        f"💰 Цена: **${product['price']}**"
    )


@router.message(Command("catalog"))
@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: Message):
    """Открывает первую страницу каталога."""
    if not MOCK_PRODUCTS:
        await message.answer("Каталог пока пуст 😔")
        return

    page = 0
    product = MOCK_PRODUCTS[page]
    total_pages = len(MOCK_PRODUCTS)

    await message.answer_photo(
        photo=product["photo"],
        caption=format_product_caption(product),
        reply_markup=get_catalog_keyboard(page, total_pages, product["id"]),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("catalog_page:"))
async def process_catalog_pagination(callback: CallbackQuery):
    """Обрабатывает переключение страниц."""
    page = int(callback.data.split(":")[1])
    
    if page < 0 or page >= len(MOCK_PRODUCTS):
        await callback.answer()
        return

    product = MOCK_PRODUCTS[page]
    total_pages = len(MOCK_PRODUCTS)

    # Обновляем фото и подпись в существующем сообщении
    await callback.message.edit_media(
        media={
            "type": "photo",
            "media": product["photo"],
            "caption": format_product_caption(product),
            "parse_mode": "Markdown"
        },
        reply_markup=get_catalog_keyboard(page, total_pages, product["id"])
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def process_noop(callback: CallbackQuery):
    """Пустой обработчик для неактивных кнопок (например, крайние страницы)."""
    await callback.answer()
