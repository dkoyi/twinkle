"""One conversation owns the shared computer, across all voice transports."""
import asyncio

call_lock = asyncio.Lock()
