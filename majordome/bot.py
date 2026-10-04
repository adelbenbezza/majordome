"""Telegram bot: wiring, owner lock and message handlers."""

import logging
from datetime import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from .actions import execute, format_tasks
from .brain import Brain, BrainError
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
        text = (
            "Bonjour, je suis Majordome 🎩\n\n"
            "Dis-moi ce que tu as à faire (« appeler la banque vendredi à 15h »), "
            "ce que tu as fait (« j'ai pris mes compléments »), "
            "ou demande « qu'est-ce qu'il me reste aujourd'hui ? ». /today affiche ta liste."
        )
    else:
        text = (
            "Hello, I'm Majordome 🎩\n\n"
            "Tell me what you need to do (\"call the bank on Friday at 3pm\"), "
            "what you've done (\"I took my supplements\"), "
            "or ask \"what's left today?\". /today shows your list."
        )
    await update.effective_message.reply_text(text)


BRAIN_ERRORS = {
    "auth": (
        "Ma clé Anthropic est refusée. Vérifie ANTHROPIC_API_KEY dans Railway.",
        "My Anthropic key was rejected. Check ANTHROPIC_API_KEY in Railway.",
    ),
    "busy": (
        "Claude est surchargé en ce moment. Réessaie dans une minute.",
        "Claude is overloaded right now. Please try again in a minute.",
    ),
    "network": (
        "Je n'arrive pas à joindre Claude. Réessaie dans un instant.",
        "I can't reach Claude right now. Please try again in a moment.",
    ),
    "refused": (
        "Je ne peux pas t'aider avec ça.",
        "I can't help with that one.",
    ),
}
BRAIN_ERROR_DEFAULT = (
    "Je n'ai pas bien compris. Tu peux reformuler ?",
    "I didn't quite get that. Could you rephrase?",
)


def owner_now(context: ContextTypes.DEFAULT_TYPE) -> datetime:
    return datetime.now(context.bot_data["config"].timezone)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Text message: Claude works out what's meant, then Python carries it out."""
    message = update.effective_message
    db: Database = context.bot_data["db"]
    brain: Brain = context.bot_data["brain"]
    await message.chat.send_action(ChatAction.TYPING)

    now = owner_now(context)
    try:
        actions = await brain.interpret(message.text, now, db.open_tasks(limit=50))
    except BrainError as error:
        log.warning("Claude failed: %s", error)
        french, english = BRAIN_ERRORS.get(error.kind, BRAIN_ERROR_DEFAULT)
        await message.reply_text(french if is_french(update) else english)
        return

    replies = [execute(action, db, now) for action in actions]
    await message.reply_text("\n\n".join(replies))


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/today: same as asking "what's left today?", without calling Claude."""
    db: Database = context.bot_data["db"]
    lang = "fr" if is_french(update) else "en"
    now = owner_now(context)
    await update.effective_message.reply_text(format_tasks(db, now, now.date(), now.date(), lang))


async def unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_french(update):
        text = "Pour l'instant je ne comprends que les messages texte."
    else:
        text = "For now I can only read text messages."
    await update.effective_message.reply_text(text)


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
    app.bot_data["brain"] = Brain(config.anthropic_api_key, config.claude_model)

    # Group -1 runs before the default group 0, so the lock sees every update first.
    app.add_handler(TypeHandler(Update, owner_lock), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(~filters.COMMAND, unsupported))
    app.add_error_handler(on_error)
    return app
