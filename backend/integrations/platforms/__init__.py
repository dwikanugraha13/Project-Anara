"""
platforms/__init__.py — Omnichannel platform adapters package (Hermes Parity).
"""

from .telegram import TelegramPlatformAdapter
from .whatsapp import WhatsAppPlatformAdapter
from .discord import DiscordPlatformAdapter
from .slack import SlackPlatformAdapter
from .web_studio import WebStudioPlatformAdapter
from .cli import CliPlatformAdapter
from .voice import VoicePlatformAdapter

__all__ = [
    "TelegramPlatformAdapter",
    "WhatsAppPlatformAdapter",
    "DiscordPlatformAdapter",
    "SlackPlatformAdapter",
    "WebStudioPlatformAdapter",
    "CliPlatformAdapter",
    "VoicePlatformAdapter",
]
