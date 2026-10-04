"""Entry point: `python -m majordome`."""

import logging
import sys

from dotenv import load_dotenv
from telegram.error import InvalidToken

from .bot import build_application
from .config import ConfigError, load_config
from .db import Database


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
        # Python logs to stderr by default, which Railway marks as errors. Use stdout.
        stream=sys.stdout,
    )
    # httpx logs every request to Telegram (including the token in the URL): keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    load_dotenv()  # reads .env when running locally; does nothing on Railway
    try:
        config = load_config()
    except ConfigError as error:
        logging.error("Configuration problem: %s", error)
        sys.exit(1)

    if config.storage_is_temporary:
        logging.warning(
            "No volume attached: everything will be lost at the next update. In Railway, right-click "
            "the service > Attach volume, with mount path /data."
        )
    db = Database(config.database_path)
    logging.info(
        "Majordome starting (database: %s, dashboard: %s)",
        config.database_path,
        "on" if config.enable_dashboard else "off",
    )
    app = build_application(config, db)
    # Polling: the bot asks Telegram for new messages, so no public URL is needed.
    try:
        app.run_polling(allowed_updates=["message", "callback_query"])
    except InvalidToken:
        logging.error("Telegram rejected TELEGRAM_BOT_TOKEN. Copy it again from @BotFather.")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
