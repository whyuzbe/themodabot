from aiogram import BaseMiddleware
from db.repos import Repos


class RepoMiddleware(BaseMiddleware):
    def __init__(self, repos: Repos):
        self.repos = repos

    async def __call__(self, handler, event, data):
        data["repos"] = self.repos
        return await handler(event, data)