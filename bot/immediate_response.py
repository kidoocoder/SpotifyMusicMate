"""Module for handling immediate acknowledgment responses."""
import asyncio
import logging
from typing import Optional, Callable, Awaitable, Dict, Any

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, MessageNotModified

logger = logging.getLogger(__name__)

# Cooldown tracking to prevent too many acknowledgments
_last_ack = {}  # chat_id -> timestamp


class ImmediateResponse:
    """Manager for immediate acknowledgment responses."""
    
    def __init__(self):
        self.cooldown = 3  # Seconds between acknowledgments in same chat
    
    async def acknowledge(self, 
                         client: Client, 
                         message: Message, 
                         text: str, 
                         reply_markup: Optional[InlineKeyboardMarkup] = None,
                         delete_after: Optional[float] = None) -> Optional[Message]:
        """
        Send an immediate acknowledgment message.
        
        Args:
            client: The pyrogram client.
            message: The original message to acknowledge.
            text: The acknowledgment text.
            reply_markup: Optional inline keyboard.
            delete_after: If provided, delete the acknowledgment after this many seconds.
            
        Returns:
            The acknowledgment message if sent, None otherwise.
        """
        chat_id = message.chat.id
        
        # Check cooldown
        now = asyncio.get_event_loop().time()
        if chat_id in _last_ack and (now - _last_ack[chat_id]) < self.cooldown:
            return None
        
        _last_ack[chat_id] = now
        
        try:
            ack_msg = await client.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=message.id,
                reply_markup=reply_markup
            )
            
            if delete_after:
                # Schedule deletion
                asyncio.create_task(self._delete_later(client, ack_msg, delete_after))
                
            return ack_msg
        except FloodWait as e:
            logger.warning(f"FloodWait: {e.value}s when sending acknowledgment")
            await asyncio.sleep(e.value)
            return None
        except Exception as e:
            logger.error(f"Error sending acknowledgment: {e}", exc_info=True)
            return None
    
    async def update_processing_status(self, 
                                      client: Client, 
                                      ack_message: Message, 
                                      text: str,
                                      reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """
        Update an existing acknowledgment message with a progress update.
        
        Args:
            client: The pyrogram client.
            ack_message: The acknowledgment message to update.
            text: The new text.
            reply_markup: Optional new inline keyboard.
            
        Returns:
            True if updated successfully, False otherwise.
        """
        try:
            await client.edit_message_text(
                chat_id=ack_message.chat.id,
                message_id=ack_message.id,
                text=text,
                reply_markup=reply_markup
            )
            return True
        except MessageNotModified:
            # Message not modified, which is fine
            return True
        except FloodWait as e:
            logger.warning(f"FloodWait: {e.value}s when updating acknowledgment")
            await asyncio.sleep(e.value)
            return False
        except Exception as e:
            logger.error(f"Error updating acknowledgment: {e}", exc_info=True)
            return False

    async def finish_with_result(self, 
                               client: Client, 
                               ack_message: Message, 
                               text: str,
                               reply_markup: Optional[InlineKeyboardMarkup] = None,
                               delete_original: bool = False) -> bool:
        """
        Update an acknowledgment message with the final result.
        
        Args:
            client: The pyrogram client.
            ack_message: The acknowledgment message to update.
            text: The result text.
            reply_markup: Optional new inline keyboard.
            delete_original: If True, delete the original acknowledgment instead of updating it.
            
        Returns:
            True if updated successfully, False otherwise.
        """
        if delete_original:
            try:
                await client.delete_messages(ack_message.chat.id, ack_message.id)
                await client.send_message(
                    chat_id=ack_message.chat.id,
                    text=text,
                    reply_to_message_id=ack_message.reply_to_message_id,
                    reply_markup=reply_markup
                )
                return True
            except Exception as e:
                logger.error(f"Error finishing with result (delete mode): {e}", exc_info=True)
                return False
        else:
            return await self.update_processing_status(client, ack_message, text, reply_markup)
    
    async def _delete_later(self, client: Client, message: Message, delay: float):
        """Delete a message after the specified delay."""
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except Exception as e:
            logger.error(f"Error deleting acknowledgment: {e}", exc_info=True)


# Singleton instance
immediate_response = ImmediateResponse()