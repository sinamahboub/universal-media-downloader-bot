"""
Services module initialization.

Exposes business logic services for dependency injection.

Imports are lazy on purpose: ``bot.downloader.factory`` needs
``Platform`` from ``bot.services.url_parser``, and an eager import
of ``media_service`` here would create a circular import
(factory -> services -> media_service -> factory).
"""

__all__ = [
    "URLParserService",
    "ParsedURL",
    "Platform",
    "MediaDownloadService",
]


def __getattr__(name: str):
    if name in ("URLParserService", "ParsedURL", "Platform"):
        from .url_parser import ParsedURL, Platform, URLParserService

        return {"URLParserService": URLParserService, "ParsedURL": ParsedURL, "Platform": Platform}[name]
    if name == "MediaDownloadService":
        from .media_service import MediaDownloadService

        return MediaDownloadService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
