"""
telegram package — Modularized Telegram Bot API Gateway for Project Anara.
Anara Standard plugins/platforms/telegram architecture.
Decomposed from a 1,842-line monolith into focused submodules (<350 lines each):
- client.py: Bot API HTTP client, media sending, attachment downloading.
- formatter.py: HTML formatting, GFM tables to ASCII grids, line-break normalization.
- keyboards.py: Multi-provider model selection menus, plan approval, question wizards.
- handlers.py: Inbound update router, slash commands, build mode execution.
- polling.py: Supervised background long-polling daemon.
"""

from .client import (
    TELEGRAM_API_BASE,
    get_stored_telegram_token,
    get_stored_telegram_chat_id,
    get_stored_telegram_admin_ids,
    save_telegram_config,
    get_telegram_status,
    get_telegram_messages,
    get_recent_telegram_updates,
    send_telegram_message,
    send_telegram_document,
    send_telegram_voice,
    send_telegram_photo,
    send_telegram_video,
    execute_remote_telegram_command,
    answer_telegram_callback_query,
    edit_telegram_message,
    delete_telegram_message,
    send_telegram_chat_action,
    download_telegram_attachment,
    setup_telegram_bot_commands,
)
from .formatter import (
    format_telegram_html,
    _render_markdown_table_to_ascii,
    _rich_normalize_linebreaks,
    has_rich_telegram_constructs,
)
from .keyboards import (
    send_telegram_provider_selector,
    send_telegram_models_for_provider,
    send_telegram_model_search,
    send_telegram_model_selector,
    send_telegram_plan_proposal,
    start_telegram_interactive_question,
    render_telegram_question,
    finish_telegram_interactive_question,
)
from .handlers import (
    process_incoming_telegram_update,
)
from .polling import (
    start_telegram_polling_daemon,
    stop_telegram_polling_daemon,
)

__all__ = [
    "TELEGRAM_API_BASE",
    "get_stored_telegram_token",
    "get_stored_telegram_chat_id",
    "get_stored_telegram_admin_ids",
    "save_telegram_config",
    "get_telegram_status",
    "get_telegram_messages",
    "get_recent_telegram_updates",
    "send_telegram_message",
    "send_telegram_document",
    "send_telegram_voice",
    "send_telegram_photo",
    "send_telegram_video",
    "execute_remote_telegram_command",
    "answer_telegram_callback_query",
    "edit_telegram_message",
    "delete_telegram_message",
    "send_telegram_chat_action",
    "download_telegram_attachment",
    "setup_telegram_bot_commands",
    "format_telegram_html",
    "_render_markdown_table_to_ascii",
    "_rich_normalize_linebreaks",
    "has_rich_telegram_constructs",
    "send_telegram_provider_selector",
    "send_telegram_models_for_provider",
    "send_telegram_model_search",
    "send_telegram_model_selector",
    "send_telegram_plan_proposal",
    "start_telegram_interactive_question",
    "render_telegram_question",
    "finish_telegram_interactive_question",
    "process_incoming_telegram_update",
    "start_telegram_polling_daemon",
    "stop_telegram_polling_daemon",
]
