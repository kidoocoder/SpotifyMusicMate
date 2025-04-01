"""Music quiz game for the Telegram music bot."""
import logging
import asyncio
import random
import time
from typing import Dict, List, Any, Optional, Set, Tuple

from bot.spotify import SpotifyClient
from bot.database import Database

logger = logging.getLogger(__name__)

class QuizQuestion:
    """Represents a single music quiz question."""
    
    def __init__(self, track_info: Dict[str, Any], options: List[str], correct_index: int):
        """
        Initialize a quiz question.
        
        Args:
            track_info: Information about the track for this question.
            options: List of answer options.
            correct_index: Index of the correct answer in options.
        """
        self.track_info = track_info
        self.options = options
        self.correct_index = correct_index
        self.preview_url = track_info.get("preview_url")
        self.answered_by: Dict[int, int] = {}  # user_id -> selected_option_index
        self.start_time = time.time()
    
    def add_answer(self, user_id: int, option_index: int) -> bool:
        """
        Add a user's answer.
        
        Args:
            user_id: The Telegram user ID.
            option_index: The index of the selected option.
            
        Returns:
            True if this is the user's first answer, False if they already answered.
        """
        if user_id in self.answered_by:
            return False
        
        self.answered_by[user_id] = option_index
        return True
    
    def is_correct(self, option_index: int) -> bool:
        """
        Check if an answer is correct.
        
        Args:
            option_index: The index of the selected option.
            
        Returns:
            True if correct, False otherwise.
        """
        return option_index == self.correct_index
    
    def get_user_score(self, user_id: int) -> int:
        """
        Get a user's score for this question.
        
        Args:
            user_id: The Telegram user ID.
            
        Returns:
            Score for this question (0 if incorrect or didn't answer).
        """
        if user_id not in self.answered_by:
            return 0
        
        selected_index = self.answered_by[user_id]
        if not self.is_correct(selected_index):
            return 0
        
        # Calculate score based on speed (max 100 points per question)
        # Score decreases over time, minimum 50 points for correct answer
        elapsed_time = time.time() - self.start_time
        time_factor = max(0, 1 - (elapsed_time / 15))  # 15 seconds to answer for max points
        
        return int(50 + (50 * time_factor))
    
    def get_correct_answer(self) -> str:
        """
        Get the correct answer text.
        
        Returns:
            The correct answer option.
        """
        return self.options[self.correct_index]
    
    def get_correct_answer_details(self) -> str:
        """
        Get details about the correct answer.
        
        Returns:
            Formatted string with details about the correct track.
        """
        track = self.track_info
        details = f"🎵 **{track.get('name', 'Unknown')}**\n"
        details += f"👤 {track.get('artists', 'Unknown')}\n"
        
        album = track.get('album', '')
        if album:
            details += f"💽 {album}\n"
            
        if track.get('external_url'):
            details += f"🔗 [Listen on Spotify]({track.get('external_url')})"
        
        return details


class MusicQuiz:
    """Music quiz game with multiple question types."""
    
    def __init__(self, spotify: SpotifyClient, database: Database):
        """
        Initialize the music quiz.
        
        Args:
            spotify: SpotifyClient instance for fetching music data.
            database: Database instance for tracking stats and history.
        """
        self.spotify = spotify
        self.database = database
        self.active_quizzes: Dict[int, 'QuizSession'] = {}  # chat_id -> quiz session
    
    async def create_quiz(self, chat_id: int, creator_id: int, 
                        num_questions: int = 5, 
                        genre: Optional[str] = None,
                        difficulty: str = "medium") -> Optional['QuizSession']:
        """
        Create a new quiz session.
        
        Args:
            chat_id: The Telegram chat ID.
            creator_id: The user ID who created the quiz.
            num_questions: Number of questions in the quiz.
            genre: Optional music genre to focus on.
            difficulty: Quiz difficulty level ("easy", "medium", "hard").
            
        Returns:
            The created QuizSession or None if creation failed.
        """
        # Check if there's already an active quiz in this chat
        if chat_id in self.active_quizzes and self.active_quizzes[chat_id].is_active():
            return None
        
        # Create a new quiz session
        session = QuizSession(self, chat_id, creator_id, num_questions, genre, difficulty)
        
        # Generate questions
        success = await session.generate_questions()
        if not success:
            return None
        
        # Store the session
        self.active_quizzes[chat_id] = session
        
        return session
    
    def get_quiz(self, chat_id: int) -> Optional['QuizSession']:
        """
        Get an active quiz session for a chat.
        
        Args:
            chat_id: The Telegram chat ID.
            
        Returns:
            The QuizSession if found and active, None otherwise.
        """
        session = self.active_quizzes.get(chat_id)
        if session and session.is_active():
            return session
        
        return None
    
    def end_quiz(self, chat_id: int):
        """
        End an active quiz session.
        
        Args:
            chat_id: The Telegram chat ID.
        """
        if chat_id in self.active_quizzes:
            self.active_quizzes[chat_id].end()
            del self.active_quizzes[chat_id]
    
    async def get_random_tracks(self, 
                              count: int = 10, 
                              genre: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get random tracks for quiz questions.
        
        Args:
            count: Number of tracks to get.
            genre: Optional genre filter.
            
        Returns:
            List of track info dictionaries.
        """
        try:
            if genre:
                # Get tracks by genre
                tracks = await self.spotify.get_recommendations_by_genres(genre, limit=count)
            else:
                # Get trending tracks
                tracks = await self.spotify.get_trending_tracks(limit=count)
            
            # Filter tracks with preview URLs (needed for audio questions)
            tracks_with_preview = [t for t in tracks if t.get("preview_url")]
            
            if len(tracks_with_preview) < count:
                # If we don't have enough tracks with previews, supplement with more tracks
                more_tracks = await self.spotify.get_trending_tracks(limit=count*2)
                more_with_preview = [t for t in more_tracks if t.get("preview_url") and t not in tracks_with_preview]
                tracks_with_preview.extend(more_with_preview[:count-len(tracks_with_preview)])
            
            return tracks_with_preview[:count]
        
        except Exception as e:
            logger.error(f"Error getting random tracks for quiz: {e}", exc_info=True)
            return []


class QuizSession:
    """A session of the music quiz for a specific chat."""
    
    def __init__(self, quiz_manager: MusicQuiz, 
                chat_id: int, 
                creator_id: int,
                num_questions: int = 5,
                genre: Optional[str] = None,
                difficulty: str = "medium"):
        """
        Initialize a quiz session.
        
        Args:
            quiz_manager: The MusicQuiz instance.
            chat_id: The Telegram chat ID.
            creator_id: The user ID who created the quiz.
            num_questions: Number of questions in the quiz.
            genre: Optional music genre to focus on.
            difficulty: Quiz difficulty level ("easy", "medium", "hard").
        """
        self.quiz_manager = quiz_manager
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.num_questions = min(max(1, num_questions), 10)  # Limit to 1-10 questions
        self.genre = genre
        self.difficulty = difficulty
        
        self.questions: List[QuizQuestion] = []
        self.current_question_index = -1
        self.active = True
        self.scores: Dict[int, int] = {}  # user_id -> total score
        self.start_time = time.time()
        self.question_time_limit = 30  # seconds
        self.question_timer = None
    
    async def generate_questions(self) -> bool:
        """
        Generate quiz questions.
        
        Returns:
            True if successful, False otherwise.
        """
        # Get random tracks for questions
        tracks = await self.quiz_manager.get_random_tracks(
            count=self.num_questions * 3,  # Get more tracks than needed for variety
            genre=self.genre
        )
        
        if len(tracks) < self.num_questions:
            logger.error(f"Not enough tracks available for quiz. Got {len(tracks)}, need {self.num_questions}")
            return False
        
        # Shuffle tracks
        random.shuffle(tracks)
        
        # Create different types of questions
        question_types = self._get_question_types()
        self.questions = []
        
        for i in range(self.num_questions):
            if not tracks:
                break
                
            # Select a question type
            question_type = random.choice(question_types)
            
            # Get a track for this question
            main_track = tracks.pop(0)
            
            if question_type == "guess_song":
                # Create a "Guess the song" question
                options = [main_track["name"]]
                
                # Add wrong options
                for _ in range(3):
                    if tracks:
                        wrong_track = tracks.pop(0)
                        options.append(wrong_track["name"])
                    else:
                        # Generate a fake option if we run out of tracks
                        options.append(f"Wrong Song {i}")
                
                # Shuffle options
                correct_index = 0
                random.shuffle(options)
                for j, option in enumerate(options):
                    if option == main_track["name"]:
                        correct_index = j
                        break
                
                self.questions.append(QuizQuestion(main_track, options, correct_index))
                
            elif question_type == "guess_artist":
                # Create a "Guess the artist" question
                artist = main_track.get("artists", "Unknown Artist")
                options = [artist]
                
                # Add wrong options
                for _ in range(3):
                    if tracks:
                        wrong_track = tracks.pop(0)
                        wrong_artist = wrong_track.get("artists", "Unknown Artist")
                        if wrong_artist not in options:
                            options.append(wrong_artist)
                    else:
                        # Generate a fake option if we run out of tracks
                        options.append(f"Wrong Artist {i}")
                
                # Shuffle options
                correct_index = 0
                random.shuffle(options)
                for j, option in enumerate(options):
                    if option == artist:
                        correct_index = j
                        break
                
                self.questions.append(QuizQuestion(main_track, options, correct_index))
            
            elif question_type == "finish_lyrics":
                # Create a "Finish the lyrics" question
                # Note: In a real implementation, you would need to get actual lyrics for this
                # Here we'll just use placeholder options
                
                options = [
                    "This is the correct lyrics continuation",
                    "This is wrong lyrics option 1",
                    "This is wrong lyrics option 2",
                    "This is wrong lyrics option 3"
                ]
                
                # For demo purposes, first option is always correct
                correct_index = 0
                
                self.questions.append(QuizQuestion(main_track, options, correct_index))
        
        return len(self.questions) == self.num_questions
    
    def _get_question_types(self) -> List[str]:
        """
        Get question types based on difficulty.
        
        Returns:
            List of question type identifiers.
        """
        if self.difficulty == "easy":
            # Only basic question types for easy
            return ["guess_song", "guess_artist"]
        elif self.difficulty == "medium":
            # More variety in medium
            return ["guess_song", "guess_artist", "guess_song", "finish_lyrics"]
        else:  # hard
            # Most challenging mix for hard
            return ["guess_song", "guess_artist", "finish_lyrics", "finish_lyrics"]
    
    def is_active(self) -> bool:
        """
        Check if the quiz session is active.
        
        Returns:
            True if active, False otherwise.
        """
        return self.active
    
    def end(self):
        """End the quiz session."""
        self.active = False
        if self.question_timer:
            self.question_timer.cancel()
            self.question_timer = None
    
    def get_current_question(self) -> Optional[QuizQuestion]:
        """
        Get the current quiz question.
        
        Returns:
            The current question or None if no question is active.
        """
        if not self.is_active() or self.current_question_index < 0 or self.current_question_index >= len(self.questions):
            return None
        
        return self.questions[self.current_question_index]
    
    def next_question(self) -> Optional[QuizQuestion]:
        """
        Move to the next question.
        
        Returns:
            The next question or None if no more questions.
        """
        if not self.is_active():
            return None
        
        # Cancel any existing timer
        if self.question_timer:
            self.question_timer.cancel()
            self.question_timer = None
        
        # Increment index
        self.current_question_index += 1
        
        # Check if we've reached the end
        if self.current_question_index >= len(self.questions):
            return None
        
        # Start timer for this question
        self.question_timer = asyncio.create_task(self._question_timer())
        
        return self.get_current_question()
    
    async def _question_timer(self):
        """Timer task for the current question."""
        try:
            await asyncio.sleep(self.question_time_limit)
            
            # Time's up for this question - trigger next question
            # This would normally call back to the bot's command handler
            # to display results and move to the next question
            logger.info(f"Time's up for question {self.current_question_index + 1} in chat {self.chat_id}")
            
            # Note: In a real implementation, you'd trigger a callback here
            # to the bot's command handler to show the time's up message
        except asyncio.CancelledError:
            # Timer was cancelled, this is fine
            pass
        except Exception as e:
            logger.error(f"Error in question timer: {e}", exc_info=True)
    
    def add_answer(self, user_id: int, option_index: int) -> Tuple[bool, bool, int]:
        """
        Add a user's answer for the current question.
        
        Args:
            user_id: The Telegram user ID.
            option_index: The index of the selected option.
            
        Returns:
            Tuple of (answer_added, is_correct, points_earned)
        """
        question = self.get_current_question()
        if not question:
            return (False, False, 0)
        
        # Add the answer
        answer_added = question.add_answer(user_id, option_index)
        if not answer_added:
            return (False, False, 0)
        
        # Calculate points
        is_correct = question.is_correct(option_index)
        points = question.get_user_score(user_id)
        
        # Update user's total score
        if user_id not in self.scores:
            self.scores[user_id] = 0
        
        self.scores[user_id] += points
        
        return (True, is_correct, points)
    
    def get_leaderboard(self) -> List[Tuple[int, int]]:
        """
        Get the current leaderboard.
        
        Returns:
            List of (user_id, score) tuples, sorted by score (highest first).
        """
        return sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
    
    def get_results(self) -> Dict[str, Any]:
        """
        Get the final quiz results.
        
        Returns:
            Dictionary with quiz results.
        """
        duration = time.time() - self.start_time
        
        # Calculate stats
        total_answers = 0
        correct_answers = 0
        
        for question in self.questions:
            for user_id, option_index in question.answered_by.items():
                total_answers += 1
                if question.is_correct(option_index):
                    correct_answers += 1
        
        # Get unique participants count
        all_user_ids = set()
        for question in self.questions:
            all_user_ids.update(question.answered_by.keys())
        unique_participants = len(all_user_ids)
        
        return {
            "num_questions": len(self.questions),
            "total_answers": total_answers,
            "correct_answers": correct_answers,
            "accuracy": correct_answers / total_answers if total_answers > 0 else 0,
            "duration": duration,
            "participants": unique_participants,
            "leaderboard": self.get_leaderboard()
        }
    
    async def send_question(self, client, chat_id, usernames: Optional[Dict[int, str]] = None):
        """
        Send the current quiz question to the chat.
        
        Args:
            client: The Telegram client.
            chat_id: The chat ID to send the question to.
            usernames: Optional mapping of user_id to username.
            
        Returns:
            The sent message, or None if there was an error.
        """
        from bot.ui import send_quiz_question
        
        question = self.get_current_question()
        if not question:
            return None
        
        # Determine question type
        question_types = self._get_question_types()
        question_index = min(self.current_question_index, len(question_types) - 1)
        question_type = question_types[question_index % len(question_types)]
        
        # Create inline keyboard for answers
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        labels = ['A', 'B', 'C', 'D']
        for i, _ in enumerate(question.options[:4]):
            buttons.append([
                InlineKeyboardButton(f"{labels[i]}", callback_data=f"quiz_answer_{i}")
            ])
        
        # Add end quiz button
        buttons.append([
            InlineKeyboardButton("🛑 End Quiz", callback_data="quiz_end")
        ])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        # Use enhanced UI to send question
        return await send_quiz_question(
            client=client,
            message=await client.send_message(chat_id, "Loading quiz question..."),
            question_number=self.current_question_index + 1,
            total_questions=len(self.questions),
            track_info=question.track_info,
            question_type=question_type,
            options=question.options,
            reply_markup=reply_markup
        )
    
    async def send_results(self, client, chat_id, usernames: Optional[Dict[int, str]] = None):
        """
        Send the final quiz results to the chat.
        
        Args:
            client: The Telegram client.
            chat_id: The chat ID to send the results to.
            usernames: Optional mapping of user_id to username.
            
        Returns:
            The sent message, or None if there was an error.
        """
        from bot.ui import send_quiz_results
        
        results = self.get_results()
        
        # Convert user IDs to usernames in leaderboard
        formatted_leaderboard = []
        for user_id, score in results["leaderboard"]:
            username = usernames.get(user_id, f"User {user_id}") if usernames else f"User {user_id}"
            formatted_leaderboard.append((username, score))
        
        # Create a "play again" button
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 Play Again", callback_data="quiz_new")
        ]])
        
        # Use enhanced UI to send results
        return await send_quiz_results(
            client=client,
            chat_id=chat_id,
            total_questions=results["num_questions"],
            correct_answers=results["correct_answers"],
            total_participants=results["participants"],
            top_scorers=formatted_leaderboard,
            reply_markup=reply_markup
        )