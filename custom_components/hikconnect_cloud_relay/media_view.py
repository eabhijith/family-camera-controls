"""Separate loopback listener for HA FFmpeg, NEVER registered with hass.http.

HA's own camera/stream integration owns frontend authentication. This service
is container-local only; reverse proxies must never explicitly forward it.
"""
from __future__ import annotations

import asyncio
import queue
from aiohttp import web


class PrivateMediaFeed:
    def __init__(self, hass, relay):
        self.hass = hass
        self.relay = relay
        self.runner = None
        self.source = None

    async def start(self):
        app = web.Application()
        app.router.add_get("/stream.ts", self._stream)
        self.runner = web.AppRunner(app, access_log=None, shutdown_timeout=2)
        try:
            await self.runner.setup()
            site = web.TCPSite(self.runner, "127.0.0.1", 0)
            await site.start()
            port = self.runner.addresses[0][1]
            self.source = f"http://127.0.0.1:{port}/stream.ts"
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
        self.runner = None
        self.source = None

    async def _stream(self, request):
        client = self.relay.subscribe_mpegts()
        response = web.StreamResponse(headers={
            "Content-Type": "video/mp2t", "Cache-Control": "no-store",
        })
        try:
            await response.prepare(request)
            while not self.relay.stop_event.is_set():
                try:
                    chunk = await self.hass.async_add_executor_job(client.get, True, 2.0)
                except queue.Empty:
                    continue
                await response.write(chunk)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self.relay.unsubscribe_mpegts(client)
        return response
