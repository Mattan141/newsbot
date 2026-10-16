"""Live news: Alpaca pushes each story to us the moment it arrives.

Polling ("anything new?" every few minutes) means the bot can be up to 5
minutes late. A websocket stream keeps one connection open and the server
sends each headline as soon as Alpaca receives it, usually within seconds,
while making far *fewer* requests than polling every second would.

The stream runs in a background thread and only drops headlines into a
queue. The main loop takes them out and does the tagging, scoring and
database work, so the database is only ever touched from one thread.
"""
import queue
import threading
import time

from alpaca.data.live.news import NewsDataStream

from newsbot.config import Settings
from newsbot.news import Headline


def to_headline(news) -> Headline:
    return Headline(
        source=f"Alpaca-live/{news.source}",
        title=news.headline,
        url=news.url or "",
        published=news.created_at,
        symbols=list(news.symbols or []),
    )


class LiveNews:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.inbox: "queue.Queue[Headline]" = queue.Queue()
        self.received = 0
        self._thread: threading.Thread | None = None

    async def _on_news(self, news) -> None:
        self.received += 1
        self.inbox.put(to_headline(news))

    def _run(self) -> None:
        # The library reconnects by itself after short drops. This outer loop
        # restarts it if it ever gives up completely (e.g. Wi-Fi off for ages).
        while True:
            try:
                stream = NewsDataStream(self.settings.api_key, self.settings.secret_key)
                stream.subscribe_news(self._on_news, "*")
                stream.run()
            except Exception as exc:
                print(f"  [warn] live news stream stopped ({type(exc).__name__}); restarting in 30s")
            time.sleep(30)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="live-news", daemon=True)
        self._thread.start()

    def drain(self) -> list[Headline]:
        """Everything that's arrived since the last call."""
        items = []
        while True:
            try:
                items.append(self.inbox.get_nowait())
            except queue.Empty:
                return items
