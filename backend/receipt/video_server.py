import io
import threading
from typing import List

import websockets.sync.server
from PIL import Image


def receive_frames(host: str = "0.0.0.0", port: int = 8765) -> List[Image.Image]:
    """Start a WebSocket server, receive JPEG frames from a Flutter client,
    and return them as PIL Images once the client disconnects."""
    frames: List[Image.Image] = []
    connection_done = threading.Event()

    def handler(websocket):
        for message in websocket:
            if isinstance(message, bytes):
                image = Image.open(io.BytesIO(message))
                frames.append(image.copy())
        connection_done.set()

    with websockets.sync.server.serve(handler, host, port):
        print("[video_server.py]Waiting for connection...")
        connection_done.wait()

    return frames

if __name__=='__main__':
    receive_frames()