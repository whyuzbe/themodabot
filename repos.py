"""
Repos — единая точка доступа ко всем репозиториям.
Прокидывается в aiogram Dispatcher как dp["repos"], доступен в хендлерах
через параметр `repos: Repos`.
"""
from redis.asyncio import Redis
from db.pool import DB
from db.repo_users import UsersRepo
from db.repo_staff import StaffRepo
from db.repo_brands import BrandsRepo
from db.repo_cart import CartRepo
from db.repo_orders import OrdersRepo, FinanceRepo
from db.repo_tickets import TicketsRepo
from db.repo_texts import TextsRepo, SettingsRepo
from db.repo_warehouse import WarehouseRepo
from db.repo_posts import PostsRepo
from db.repo_partners import PartnersRepo
from db.repo_translation import TranslationCacheRepo


class Repos:
    def __init__(self, db: DB, redis: Redis | None = None):
        self.db = db
        self.redis = redis
        self.users = UsersRepo(db)
        self.staff = StaffRepo(db)
        self.brands = BrandsRepo(db)
        self.cart = CartRepo(db)
        self.orders = OrdersRepo(db)
        self.finance = FinanceRepo(db)
        self.tickets = TicketsRepo(db)
        self.texts = TextsRepo(db, redis=redis)
        self.settings = SettingsRepo(db, redis=redis)
        self.warehouse = WarehouseRepo(db)
        self.posts = PostsRepo(db)
        self.partners = PartnersRepo(db)
        self.translation_cache = TranslationCacheRepo(db)