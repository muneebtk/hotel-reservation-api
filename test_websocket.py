import asyncio
import websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQxNjc1OTk3LCJpYXQiOjE3NDE1ODk1OTcsImp0aSI6ImUwNzlhNTFiODhkNDRlZjFhYTU2NjBmZmRlMjJkMzUwIiwidXNlcl9pZCI6MTN9.dGWzl2ocB8PHrUoYh6NwLtgoXE9LaryV90TlQcdCHf4"

async def test_websocket():
    uri = f"ws://127.0.0.1:5000/ws/booking_updates/?token={TOKEN}"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket!")
        while True:
            message = await websocket.recv()
            print(f"Received message: {message}")

asyncio.run(test_websocket())
