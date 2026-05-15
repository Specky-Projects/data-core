import asyncio
import signal

from domains.crypto_coin.config.settings import load_config
from domains.crypto_coin.core.engine.trading_engine import TradingBot
from domains.crypto_coin.infra.logger import setup_logger


async def run_crypto_coin_bot(env_file: str = ".env") -> None:
    logger = setup_logger()
    shutdown = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown(signum=None, frame=None) -> None:
        logger.info("Shutdown signal received for crypto coin bot")
        loop.call_soon_threadsafe(shutdown.set)

    try:
        signal.signal(signal.SIGINT, request_shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, request_shutdown)
    except ValueError:
        logger.warning("Signal handlers are unavailable in this runtime context")

    config = load_config(env_file)
    bot = TradingBot(config, logger, shutdown_event=shutdown)

    try:
        await bot.run()
    finally:
        await bot.shutdown()


def main() -> None:
    asyncio.run(run_crypto_coin_bot())


if __name__ == "__main__":
    main()

