"""Voting system for music bot features like skipping songs."""
import logging
import asyncio
import time
from typing import Dict, Set, Any, Optional, Tuple

from bot.roles import RoleManager

logger = logging.getLogger(__name__)

class VotingSession:
    """Represents a single voting session, e.g., for skipping a song."""
    
    def __init__(self, 
                chat_id: int, 
                session_type: str,
                target_id: Optional[str] = None,
                created_by: Optional[int] = None,
                threshold: float = 0.5,  # Default threshold of 50%
                expiry: float = 60.0):  # Default expiry of 60 seconds
        """
        Initialize a voting session.
        
        Args:
            chat_id: The Telegram chat ID.
            session_type: Type of voting session (e.g., 'skip', 'stop').
            target_id: Optional ID of the target (e.g., song ID for skip votes).
            created_by: User ID who created the voting session.
            threshold: Fraction of users required to pass (0.0 to 1.0).
            expiry: Time in seconds after which the vote expires.
        """
        self.chat_id = chat_id
        self.session_type = session_type
        self.target_id = target_id
        self.created_by = created_by
        self.threshold = threshold
        self.expiry = expiry
        
        self.votes = set()  # Set of user IDs who voted
        self.created_at = time.time()
        self.active = True
    
    def add_vote(self, user_id: int) -> bool:
        """
        Add a vote from a user.
        
        Args:
            user_id: The Telegram user ID.
            
        Returns:
            True if the vote was added, False if the user already voted.
        """
        if not self.active:
            return False
            
        if user_id in self.votes:
            return False
        
        self.votes.add(user_id)
        return True
    
    def remove_vote(self, user_id: int) -> bool:
        """
        Remove a vote from a user.
        
        Args:
            user_id: The Telegram user ID.
            
        Returns:
            True if the vote was removed, False if the user didn't vote.
        """
        if not self.active:
            return False
            
        if user_id not in self.votes:
            return False
        
        self.votes.remove(user_id)
        return True
    
    def has_expired(self) -> bool:
        """
        Check if the voting session has expired.
        
        Returns:
            True if expired, False otherwise.
        """
        return time.time() - self.created_at > self.expiry
    
    def get_vote_count(self) -> int:
        """
        Get the number of votes.
        
        Returns:
            The number of votes.
        """
        return len(self.votes)
    
    def close(self):
        """Close the voting session."""
        self.active = False
    
    def is_active(self) -> bool:
        """
        Check if the voting session is active.
        
        Returns:
            True if active, False otherwise.
        """
        return self.active and not self.has_expired()


class VotingSystem:
    """System for managing voting sessions."""
    
    def __init__(self, role_manager: RoleManager):
        """
        Initialize the voting system.
        
        Args:
            role_manager: Role manager for checking user permissions.
        """
        self.role_manager = role_manager
        self.sessions: Dict[Tuple[int, str], VotingSession] = {}  # (chat_id, session_type) -> session
        self.active_users: Dict[int, Set[int]] = {}  # chat_id -> set of active user IDs
        self.cleanup_task = None
    
    def start_cleanup_task(self):
        """Start a background task to clean up expired voting sessions."""
        if not self.cleanup_task or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background task to clean up expired voting sessions."""
        try:
            while True:
                # Find and remove expired sessions
                to_remove = []
                for key, session in self.sessions.items():
                    if session.has_expired():
                        to_remove.append(key)
                
                for key in to_remove:
                    del self.sessions[key]
                
                # Sleep for a while
                await asyncio.sleep(10)  # Check every 10 seconds
        except asyncio.CancelledError:
            # Task was cancelled
            pass
        except Exception as e:
            logger.error(f"Error in voting cleanup task: {e}", exc_info=True)
    
    def stop_cleanup_task(self):
        """Stop the cleanup task."""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
    
    def register_active_user(self, chat_id: int, user_id: int):
        """
        Register a user as active in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            user_id: The Telegram user ID.
        """
        if chat_id not in self.active_users:
            self.active_users[chat_id] = set()
        
        self.active_users[chat_id].add(user_id)
    
    def unregister_active_user(self, chat_id: int, user_id: int):
        """
        Unregister a user as active in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            user_id: The Telegram user ID.
        """
        if chat_id in self.active_users and user_id in self.active_users[chat_id]:
            self.active_users[chat_id].remove(user_id)
    
    def get_active_user_count(self, chat_id: int) -> int:
        """
        Get the number of active users in a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            
        Returns:
            The number of active users.
        """
        return len(self.active_users.get(chat_id, set()))
    
    def create_session(self, 
                      chat_id: int, 
                      session_type: str,
                      target_id: Optional[str] = None,
                      created_by: Optional[int] = None,
                      threshold: float = 0.5,
                      expiry: float = 60.0) -> VotingSession:
        """
        Create a new voting session.
        
        Args:
            chat_id: The Telegram chat ID.
            session_type: Type of voting session (e.g., 'skip', 'stop').
            target_id: Optional ID of the target (e.g., song ID for skip votes).
            created_by: User ID who created the voting session.
            threshold: Fraction of users required to pass (0.0 to 1.0).
            expiry: Time in seconds after which the vote expires.
            
        Returns:
            The created voting session.
        """
        key = (chat_id, session_type)
        
        # If there's already an active session of this type, close it
        if key in self.sessions and self.sessions[key].is_active():
            self.sessions[key].close()
        
        # Create new session
        session = VotingSession(
            chat_id=chat_id,
            session_type=session_type,
            target_id=target_id,
            created_by=created_by,
            threshold=threshold,
            expiry=expiry
        )
        
        self.sessions[key] = session
        
        # Start the cleanup task if it's not running
        self.start_cleanup_task()
        
        return session
    
    def get_session(self, chat_id: int, session_type: str) -> Optional[VotingSession]:
        """
        Get an active voting session.
        
        Args:
            chat_id: The Telegram chat ID.
            session_type: Type of voting session (e.g., 'skip', 'stop').
            
        Returns:
            The voting session if found and active, None otherwise.
        """
        key = (chat_id, session_type)
        session = self.sessions.get(key)
        
        if session and session.is_active():
            return session
        
        return None
    
    def close_session(self, chat_id: int, session_type: str):
        """
        Close a voting session.
        
        Args:
            chat_id: The Telegram chat ID.
            session_type: Type of voting session (e.g., 'skip', 'stop').
        """
        key = (chat_id, session_type)
        if key in self.sessions:
            self.sessions[key].close()
    
    async def add_vote(self, chat_id: int, session_type: str, user_id: int) -> Tuple[bool, VotingSession, bool]:
        """
        Add a vote to a session.
        
        Args:
            chat_id: The Telegram chat ID.
            session_type: Type of voting session (e.g., 'skip', 'stop').
            user_id: The Telegram user ID.
            
        Returns:
            Tuple of (vote added successfully, session, vote threshold reached)
        """
        # Register the user as active
        self.register_active_user(chat_id, user_id)
        
        # Get or create session
        session = self.get_session(chat_id, session_type)
        if not session:
            session = self.create_session(chat_id, session_type, created_by=user_id)
        
        # Add vote
        added = session.add_vote(user_id)
        
        # Check if vote threshold reached
        active_users = self.get_active_user_count(chat_id)
        if active_users == 0:
            active_users = 1  # Prevent division by zero
            
        vote_count = session.get_vote_count()
        vote_ratio = vote_count / active_users
        
        # Also check for admin or DJ override
        has_override = await self.role_manager.user_has_permission(chat_id, user_id, "vote_skip_override")
        
        threshold_reached = vote_ratio >= session.threshold or has_override
        
        return (added, session, threshold_reached)
    
    def remove_vote(self, chat_id: int, session_type: str, user_id: int) -> Tuple[bool, VotingSession, bool]:
        """
        Remove a vote from a session.
        
        Args:
            chat_id: The Telegram chat ID.
            session_type: Type of voting session (e.g., 'skip', 'stop').
            user_id: The Telegram user ID.
            
        Returns:
            Tuple of (vote removed successfully, session, vote threshold reached)
        """
        session = self.get_session(chat_id, session_type)
        if not session:
            return (False, None, False)
        
        # Remove vote
        removed = session.remove_vote(user_id)
        
        # Check if vote threshold reached
        active_users = self.get_active_user_count(chat_id)
        if active_users == 0:
            active_users = 1  # Prevent division by zero
            
        vote_count = session.get_vote_count()
        vote_ratio = vote_count / active_users
        
        threshold_reached = vote_ratio >= session.threshold
        
        return (removed, session, threshold_reached)