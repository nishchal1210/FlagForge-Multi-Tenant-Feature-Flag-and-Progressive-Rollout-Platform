import asyncio

from app.realtime.connection_manager import (
    SSEConnectionManager,
)


def test_broadcast_reaches_only_target_environment():
    async def scenario():
        manager = SSEConnectionManager()

        production_queue = await manager.connect(
            "production"
        )
        development_queue = await manager.connect(
            "development"
        )

        event = {
            "type": "config_updated",
            "environment_id": "production",
            "version": 2,
            "checksum": "example-checksum",
        }

        await manager.broadcast(
            environment_id="production",
            event=event,
        )

        assert production_queue.get_nowait() == event
        assert development_queue.empty()

        await manager.disconnect(
            "production",
            production_queue,
        )
        await manager.disconnect(
            "development",
            development_queue,
        )

    asyncio.run(scenario())


def test_disconnected_queue_receives_no_more_events():
    async def scenario():
        manager = SSEConnectionManager()

        queue = await manager.connect("production")

        await manager.disconnect(
            "production",
            queue,
        )

        await manager.broadcast(
            environment_id="production",
            event={
                "type": "config_updated",
                "version": 2,
            },
        )

        assert queue.empty()

    asyncio.run(scenario())