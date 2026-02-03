import unittest
import asyncio
from desktop_aipet.src.bus.event_bus import EventBus
from desktop_aipet.src.bus.events import Event

class TestEvent(Event):
    pass

class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_subscribe_publish(self):
        received = []

        async def handler(event):
            received.append(event)

        self.bus.subscribe(TestEvent, handler)

        event = TestEvent()
        self.loop.run_until_complete(self.bus.publish(event))

        self.assertEqual(len(received), 1)
        self.assertIs(received[0], event)

    def test_multiple_subscribers(self):
        received_1 = []
        received_2 = []

        async def handler_1(event):
            received_1.append(event)

        def handler_2(event):
            received_2.append(event)

        self.bus.subscribe(TestEvent, handler_1)
        self.bus.subscribe(TestEvent, handler_2)

        event = TestEvent()
        self.loop.run_until_complete(self.bus.publish(event))

        self.assertEqual(len(received_1), 1)
        self.assertEqual(len(received_2), 1)
