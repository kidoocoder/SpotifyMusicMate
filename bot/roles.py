"""User roles and permissions management module."""
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, Set

from bot.database import Database

logger = logging.getLogger(__name__)

class RoleManager:
    """Manager for user roles in chats."""
    
    def __init__(self, database: Database):
        """
        Initialize the role manager.
        
        Args:
            database: Database instance for storing role information.
        """
        self.database = database
        self.role_cache = {}  # chat_id -> {user_id: role}
        self.role_ttl = 300  # 5 minutes
        self.role_cache_timestamps = {}  # chat_id -> timestamp
        
        # Define role hierarchy and permissions
        self.roles = {
            "admin": {
                "level": 100,
                "title": "👑 Admin",
                "permissions": [
                    "play", "pause", "resume", "skip", "stop", "volume",
                    "add_to_queue", "clear_queue", "assign_roles", "remove_roles",
                    "kick_user", "vote_skip_override", "dj_mode"
                ]
            },
            "dj": {
                "level": 50,
                "title": "🎧 DJ",
                "permissions": [
                    "play", "pause", "resume", "skip", "stop", "volume",
                    "add_to_queue", "clear_queue"
                ]
            },
            "vip": {
                "level": 25,
                "title": "⭐ VIP",
                "permissions": [
                    "play", "add_to_queue", "vote_skip"
                ]
            },
            "user": {
                "level": 10,
                "title": "👤 User",
                "permissions": [
                    "play", "add_to_queue", "vote_skip"
                ]
            },
            "restricted": {
                "level": 0,
                "title": "🚫 Restricted",
                "permissions": []
            }
        }
    
    async def get_user_role(self, chat_id: int, user_id: int) -> str:
        """
        Get a user's role in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            user_id: The Telegram user ID.
            
        Returns:
            The role name (admin, dj, vip, user, restricted).
        """
        # First, check if roles for this chat are cached and valid
        if chat_id in self.role_cache and chat_id in self.role_cache_timestamps:
            if time.time() - self.role_cache_timestamps[chat_id] < self.role_ttl:
                return self.role_cache.get(chat_id, {}).get(user_id, "user")
        
        # If not cached or expired, load from database
        chat_roles = await self.database._get_from_file(f"roles_{chat_id}", {})
        
        # Update cache
        self.role_cache[chat_id] = chat_roles.get("roles", {})
        self.role_cache_timestamps[chat_id] = time.time()
        
        return self.role_cache[chat_id].get(str(user_id), "user")
    
    async def set_user_role(self, chat_id: int, user_id: int, role: str) -> bool:
        """
        Set a user's role in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            user_id: The Telegram user ID.
            role: The role name (admin, dj, vip, user, restricted).
            
        Returns:
            True if successful, False otherwise.
        """
        # Verify role is valid
        if role not in self.roles:
            logger.error(f"Invalid role: {role}")
            return False
        
        # Get existing roles
        chat_roles = await self.database._get_from_file(f"roles_{chat_id}", {"chat_id": chat_id, "roles": {}})
        
        # Update role
        chat_roles["roles"][str(user_id)] = role
        
        # Save to database
        await self.database._save_to_file(f"roles_{chat_id}", chat_roles)
        
        # Update cache
        if chat_id not in self.role_cache:
            self.role_cache[chat_id] = {}
        self.role_cache[chat_id][str(user_id)] = role
        self.role_cache_timestamps[chat_id] = time.time()
        
        return True
    
    async def remove_user_role(self, chat_id: int, user_id: int) -> bool:
        """
        Remove a user's custom role in a chat (revert to default "user").
        
        Args:
            chat_id: The Telegram chat ID.
            user_id: The Telegram user ID.
            
        Returns:
            True if successful, False otherwise.
        """
        # Get existing roles
        chat_roles = await self.database._get_from_file(f"roles_{chat_id}", {"chat_id": chat_id, "roles": {}})
        
        # Remove role if exists
        user_id_str = str(user_id)
        if user_id_str in chat_roles["roles"]:
            del chat_roles["roles"][user_id_str]
            
            # Save to database
            await self.database._save_to_file(f"roles_{chat_id}", chat_roles)
            
            # Update cache
            if chat_id in self.role_cache and user_id_str in self.role_cache[chat_id]:
                del self.role_cache[chat_id][user_id_str]
            
            return True
        
        # No role to remove
        return False
    
    async def get_users_with_role(self, chat_id: int, role: str) -> List[int]:
        """
        Get all users with a specific role in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            role: The role name (admin, dj, vip, user, restricted).
            
        Returns:
            List of user IDs with the specified role.
        """
        # Get existing roles
        chat_roles = await self.database._get_from_file(f"roles_{chat_id}", {"chat_id": chat_id, "roles": {}})
        
        # Find users with the specified role
        return [int(user_id) for user_id, user_role in chat_roles["roles"].items() if user_role == role]
    
    def has_permission(self, role: str, permission: str) -> bool:
        """
        Check if a role has a specific permission.
        
        Args:
            role: The role name (admin, dj, vip, user, restricted).
            permission: The permission name.
            
        Returns:
            True if the role has the permission, False otherwise.
        """
        if role not in self.roles:
            # Default to user permissions for unknown roles
            role = "user"
        
        return permission in self.roles[role]["permissions"]
    
    async def user_has_permission(self, chat_id: int, user_id: int, permission: str) -> bool:
        """
        Check if a user has a specific permission in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            user_id: The Telegram user ID.
            permission: The permission name.
            
        Returns:
            True if the user has the permission, False otherwise.
        """
        role = await self.get_user_role(chat_id, user_id)
        return self.has_permission(role, permission)
    
    def get_role_level(self, role: str) -> int:
        """
        Get the numeric level of a role.
        
        Args:
            role: The role name.
            
        Returns:
            The role level (higher is more privileged).
        """
        if role not in self.roles:
            # Default to user level for unknown roles
            return self.roles["user"]["level"]
        
        return self.roles[role]["level"]
    
    async def get_user_role_level(self, chat_id: int, user_id: int) -> int:
        """
        Get the numeric role level of a user in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            user_id: The Telegram user ID.
            
        Returns:
            The user's role level (higher is more privileged).
        """
        role = await self.get_user_role(chat_id, user_id)
        return self.get_role_level(role)
    
    def clear_cache(self, chat_id: Optional[int] = None):
        """
        Clear the role cache for a chat or all chats.
        
        Args:
            chat_id: The Telegram chat ID to clear cache for, or None to clear all.
        """
        if chat_id is None:
            # Clear all cache
            self.role_cache = {}
            self.role_cache_timestamps = {}
        elif chat_id in self.role_cache:
            # Clear cache for specific chat
            del self.role_cache[chat_id]
            if chat_id in self.role_cache_timestamps:
                del self.role_cache_timestamps[chat_id]