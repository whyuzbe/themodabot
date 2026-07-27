"""
translate.py

Динамический перевод оставшихся "жёстких" ru/en фраз в коде на любой язык
интерфейса (uk/es и любой другой в будущем), через бесплатный Google Translate
(без API-ключа, через deep-translator). Каждая уникальная фраза переводится
только один раз — результат кэшируется в таблице translation_cache, повторные
обращения берутся из кэша без обращения к интернету.

Если перевод не удался (нет сети, сервис недоступен, лимит) — возвращается
оригинальный (русский) текст, а не ошибка. Бот никогда не должен падать
из-за недоступности переводчика.

ВАЖНО: вызов библиотеки синхронный (блокирующий) — выполняется в отдельном
потоке через run_in_executor, чтобы не подвешивать event loop бота.
"""
import asyncio
import logging

from db.repos import Repos

logger = logging.getLogger(__name__)

try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except ImportError:
    _TRANSLATOR_AVAILABLE = False


def _translate_sync(text: str, target_lang: str) -> str:
    """Блокирующий вызов библиотеки — должен запускаться в executor'е."""
    return GoogleTranslator(source="ru", target=target_lang).translate(text)


async def tr(repos: Repos, text: str, lang: str) -> str:
    """
    Переводит text (русский оригинал) на lang. Если lang == 'ru' — возвращает
    как есть. Результат кэшируется в БД, повторный перевод одной и той же
    фразы на тот же язык не делает нового сетевого запроса.
    """
    if lang == "ru" or not text:
        return text

    cached = await repos.translation_cache.get(text, lang)
    if cached is not None:
        return cached

    if not _TRANSLATOR_AVAILABLE:
        return text

    try:
        loop = asyncio.get_event_loop()
        translated = await loop.run_in_executor(None, _translate_sync, text, lang)
        if not translated:
            return text
        await repos.translation_cache.set(text, lang, translated)
        return translated
    except Exception as e:
        logger.warning(f"Перевод не удался ({lang}): {e}")
        return text