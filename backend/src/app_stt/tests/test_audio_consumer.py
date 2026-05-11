import base64
import pytest
import asyncio
from unittest.mock import patch
from channels.testing import WebsocketCommunicator
from ..asgi import application
from ..services.audio_consumers import AudioConsumer

from .data.mock_data_audio import MOCK_AUDIO


@patch("stt.app_stt.services.transcriber.transcribe_audio_chunk", return_value="To jest testowa transkrypcja.")
@pytest.mark.asyncio
async def test_audio_consumer_transcription(mock_transcribe):
    communicator = WebsocketCommunicator(application, "/ws/audio/")
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_to(text_data=MOCK_AUDIO)

    await asyncio.sleep(6)

    response = await communicator.receive_from()
    assert response == "To jest testowa transkrypcja."

    await communicator.disconnect()
