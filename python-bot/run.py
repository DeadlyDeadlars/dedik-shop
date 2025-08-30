import asyncio
import os
import sys


def ensure_path():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


def main():
    ensure_path()
    from bot.main import main as bot_main
    asyncio.run(bot_main())


if __name__ == "__main__":
    main()


