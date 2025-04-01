import asyncio
import logging
from collections import defaultdict, deque
import time

logger = logging.getLogger(__name__)

class QueueManager:
    """Manager for song queues across different chats."""
    
    def __init__(self):
        self.queues = defaultdict(deque)  # chat_id -> queue of tracks
        self.history = defaultdict(list)  # chat_id -> list of played tracks
        self.locks = defaultdict(asyncio.Lock)  # chat_id -> lock
        self.max_history_size = 50
        self.max_queue_size = 100
    
    async def add_to_queue(self, chat_id, track, user_id=None):
        """Add a track to the queue for a specific chat."""
        async with self.locks[chat_id]:
            # Check if queue is full
            if len(self.queues[chat_id]) >= self.max_queue_size:
                return False, f"Queue limit of {self.max_queue_size} reached"
            
            # Add user info and timestamp to the track
            track_with_meta = {
                **track,
                "added_by": user_id,
                "added_at": time.time()
            }
            
            # Add to queue
            self.queues[chat_id].append(track_with_meta)
            queue_position = len(self.queues[chat_id])
            
            logger.info(f"Added {track['name']} to queue at position {queue_position} in {chat_id}")
            return True, f"Added to queue at position {queue_position}: {track['name']} by {track['artists']}"
    
    def get_next_track(self, chat_id):
        """Get the next track from the queue for a specific chat."""
        # Check if queue is empty
        if not self.queues[chat_id]:
            return None
        
        # Get the next track
        track = self.queues[chat_id].popleft()
        
        # Add to history
        self.add_to_history(chat_id, track)
        
        logger.info(f"Getting next track from queue in {chat_id}: {track['name']}")
        return track
    
    def peek_next_track(self, chat_id):
        """Peek at the next track without removing it from the queue."""
        if not self.queues[chat_id]:
            return None
        return self.queues[chat_id][0]
    
    def add_to_history(self, chat_id, track):
        """Add a track to the history."""
        self.history[chat_id].append(track)
        
        # Limit history size
        if len(self.history[chat_id]) > self.max_history_size:
            self.history[chat_id].pop(0)
    
    def get_queue(self, chat_id):
        """Get the current queue for a specific chat."""
        return list(self.queues[chat_id])
    
    def get_history(self, chat_id):
        """Get the history for a specific chat."""
        return self.history[chat_id]
    
    def clear_queue(self, chat_id):
        """Clear the queue for a specific chat."""
        self.queues[chat_id].clear()
        logger.info(f"Cleared queue for {chat_id}")
    
    def remove_from_queue(self, chat_id, index):
        """Remove a track from the queue by index."""
        if not 0 <= index < len(self.queues[chat_id]):
            return False, "Invalid track index"
        
        track_list = list(self.queues[chat_id])
        removed_track = track_list.pop(index)
        self.queues[chat_id] = deque(track_list)
        
        logger.info(f"Removed track {removed_track['name']} from queue in {chat_id}")
        return True, f"Removed from queue: {removed_track['name']}"
    
    def move_track(self, chat_id, old_index, new_index):
        """Move a track in the queue from one position to another."""
        if not 0 <= old_index < len(self.queues[chat_id]):
            return False, "Invalid source track index"
        
        if not 0 <= new_index < len(self.queues[chat_id]):
            return False, "Invalid destination track index"
        
        track_list = list(self.queues[chat_id])
        track = track_list.pop(old_index)
        track_list.insert(new_index, track)
        self.queues[chat_id] = deque(track_list)
        
        logger.info(f"Moved track {track['name']} from position {old_index} to {new_index} in {chat_id}")
        return True, f"Moved track from position {old_index + 1} to {new_index + 1}"
    
    def has_tracks(self, chat_id):
        """Check if there are any tracks in the queue for a specific chat."""
        return bool(self.queues[chat_id])
    
    def queue_length(self, chat_id):
        """Get the length of the queue for a specific chat."""
        return len(self.queues[chat_id])
