"""Telegram bot: wiring, owner lock and message handlers."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from .config import Config
from .db import Database

log = logging.getLogger(__name__)


def is_french(update: Update) -> bool:
    # Until Claude handles replies (stage 2), use the language of the user's Telegram app.
    user = update.effective_user
    return bool(user and user.language_code and user.language_code.startswith("fr"))


def check_owner(config: Config, db: Database, user_id: int, is_start: bool) -> bool:
    """Decide whether `user_id` may use the bot.

    Priority: OWNER_TELEGRAM_ID from the environment, then the owner saved in the
    database. If neither exists, whoever sends /start first becomes the owner.
    """
    if config.owner_telegram_id is not None:
        return user_id == config.owner_telegram_id
    owner = db.get_owner_id()
    if owner is not None:
        return user_id == owner
    if is_start:
        return db.claim_owner(user_id)
    return False


async def owner_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs before every other handler. Silently drops updates from anyone but the owner."""
    user = update.effective_user
    if user is None:
        raise ApplicationHandlerStop
    message = update.effective_message
    is_start = bool(message and message.text and message.text.split()[0].startswith("/start"))
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not check_owner(config, db, user.id, is_start):
        log.info("Ignored update from non-owner user %s", user.id)
        raise ApplicationHandlerStop


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_french(update):
        text = "Bonjour, je suis Majordome 🎩 Je suis prêt. Envoie-moi un message ou une note vocale."
    else:
        text = "Hello, I'm Majordome 🎩 I'm ready. Send me a message or a voice note."
    await update.effective_message.reply_text(text)


async def received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("Reçu ✅" if is_french(update) else "Received ✅")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and tell the user in plain words instead of staying silent."""
    log.exception("Error while handling an update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        text = (
            "Oups, quelque chose s'est mal passé. Réessaie dans un instant."
            if is_french(update)
            else "Oops, something went wrong. Please try again in a moment."
        )
        try:
            await update.effective_message.reply_text(text)
        except Exception:
            log.exception("Could not send the error message")


def build_application(config: Config, db: Database) -> Application:
    app = Application.builder().token(config.telegram_bot_token).build()
    # bot_data is a dict shared by all handlers: a simple way to give them config and db.
    app.bot_data["config"] = config
    app.bot_data["db"] = db

    # Group -1 runs before the default group 0, so the lock sees every update first.
    app.add_handler(TypeHandler(Update, owner_lock), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, received))
    app.add_error_handler(on_error)
    return app
