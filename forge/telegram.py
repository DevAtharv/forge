from __future__ import annotations

from typing import Any

from telegram import Bot, InputFile

from forge.schemas import DeliveryPayload


class TelegramTransport:
    def __init__(self, token: str) -> None:
        self.bot = Bot(token=token) if token else None

    async def start(self) -> None:
        if self.bot is not None:
            await self.bot.initialize()

    async def close(self) -> None:
        if self.bot is not None:
            await self.bot.shutdown()

    async def send_status_message(self, chat_id: int, text: str) -> int:
        if self.bot is None:
            raise RuntimeError("Telegram token is not configured.")
        message = await self.bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
        return message.message_id

    async def edit_status_message(self, chat_id: int, message_id: int, text: str) -> None:
        if self.bot is None:
            raise RuntimeError("Telegram token is not configured.")
        await self.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            disable_web_page_preview=True,
        )

    async def deliver(self, chat_id: int, payload: DeliveryPayload, *, status_message_id: int | None = None) -> None:
        if self.bot is None:
            raise RuntimeError("Telegram token is not configured.")

        text_chunks = self._chunk_text(payload.text)
        if status_message_id and text_chunks:
            await self.edit_status_message(chat_id, status_message_id, text_chunks[0])
            text_chunks = text_chunks[1:]
        for chunk in text_chunks:
            await self.bot.send_message(chat_id=chat_id, text=chunk, disable_web_page_preview=True)
        if payload.document_bytes and payload.document_name:
            document = InputFile(payload.document_bytes, filename=payload.document_name)
            await self.bot.send_document(chat_id=chat_id, document=document, caption="Forge full output")

    async def download_photo(self, photo_sizes: list[dict[str, Any]]) -> bytes | None:
        if self.bot is None or not photo_sizes:
            return None
        largest = max(photo_sizes, key=lambda item: item.get("file_size", 0))
        file_id = largest.get("file_id")
        if not file_id:
            return None
        telegram_file = await self.bot.get_file(file_id)
        data = await telegram_file.download_as_bytearray()
        return bytes(data)

    def _chunk_text(self, text: str, *, limit: int = 3900) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks: list[str] = []
        current = ""
        for line in text.splitlines():
            candidate = f"{current}\n{line}".strip() if current else line
            if len(candidate) > limit and current:
                chunks.append(current)
                current = line
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks
