import pygame
from pyvidplayer2 import Video
import json
from datetime import datetime, timedelta
from PIL import Image
from gesture import GestureControl
import os
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import time

pygame.init()
pygame.font.init()
pygame.mixer.init()

# Configuration: Path to the general voice file for urgent ads
URGENT_VOICE_FILE = "luvvoice.com-20251129-MWN5ah.mp3"  # Change this to your voice file path
ARABIC_FONT_FILE = "Almarai-Regular.ttf"  # Path to Arabic font file


def load_arabic_font(size=36):
    """Load Arabic-compatible font with fallback options"""
    # Try to load Almarai font for Arabic support
    if os.path.exists(ARABIC_FONT_FILE):
        try:
            return pygame.font.Font(ARABIC_FONT_FILE, size)
        except Exception as e:
            print(f"Error loading Arabic font: {e}")
    
    # Fallback to system fonts
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return pygame.font.Font(font_path, size)
            except:
                continue
    
    # Final fallback
    return pygame.font.Font(None, size)


def load_posts(json_file="posts_history.json"):
    """Load and filter posts from JSON, removing expired entries"""
    try:
        with open(json_file, "r") as f:
            posts = json.load(f)
    except Exception as e:
        return []

    valid_posts = []
    remaining_posts = []
    now = datetime.now()

    for idx, post in enumerate(posts):
        status = post.get("status", "ordinary")
        # Fix: Handle None values from media_path
        media = post.get("media_path") or ""
        media = media.strip() if media else ""
        
        timestamp = post.get("timestamp")
        text = post.get("text", "").strip()

        # Skip posts with no media AND no text
        if not media and not text:
            continue
            
        if not timestamp:
            continue

        try:
            post_time = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        except ValueError as e:
            continue

        # Check expiration (urgent: 3hrs, ordinary: 24hrs)
        time_diff = now - post_time
        expiry_hours = 3 if status == "urgent" else 24
        expired = time_diff > timedelta(hours=expiry_hours)

        if expired:
            # Delete media file if it exists
            if media:
                media_path = media if os.path.isabs(media) else os.path.join(os.getcwd(), "static", media)
                if os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                        print(f"Deleted expired media: {media_path}")
                    except Exception as e:
                        print(f"Error deleting media: {e}")
            # Don't add expired posts to remaining_posts - this removes them from JSON
            print(f"Removed expired post: {timestamp}")
            continue

        # Handle text-only posts
        is_text_only = not media
        
        if not is_text_only:
            # Normalize media path
            if not os.path.isabs(media):
                media = os.path.join(os.getcwd(), "static", media)

            if not os.path.exists(media):
                # Media file missing, treat as text-only
                is_text_only = True
                media = ""

        # Detect media type
        is_video = False
        if media:
            ext = os.path.splitext(media)[1].lower()
            is_video = ext in [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"]

        valid_posts.append({
            "media": media,
            "caption": text,
            "urgent": (status == "urgent"),
            "is_video": is_video,
            "is_text_only": is_text_only,
            "timestamp": timestamp
        })
        remaining_posts.append(post)

    # Save non-expired posts back to JSON
    try:
        with open(json_file, "w") as f:
            json.dump(remaining_posts, f, indent=4)
        print(f"Saved {len(remaining_posts)} posts to JSON")
    except Exception as e:
        print(f"Error saving posts: {e}")
    
    return valid_posts


def draw_rounded_rect(surface, color, rect, radius):
    """Draw a rounded rectangle"""
    x, y, width, height = rect
    
    # Draw rectangles for the main body
    pygame.draw.rect(surface, color, (x + radius, y, width - 2*radius, height))
    pygame.draw.rect(surface, color, (x, y + radius, width, height - 2*radius))
    
    # Draw circles for corners
    pygame.draw.circle(surface, color, (x + radius, y + radius), radius)
    pygame.draw.circle(surface, color, (x + width - radius, y + radius), radius)
    pygame.draw.circle(surface, color, (x + radius, y + height - radius), radius)
    pygame.draw.circle(surface, color, (x + width - radius, y + height - radius), radius)


def wrap_text(text, font, max_width):
    """Wrap text to fit within max_width, handling newlines and Arabic text"""
    # Remove any carriage returns and clean up the text
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Split by newlines first
    paragraphs = text.split('\n')
    lines = []
    
    for paragraph in paragraphs:
        # Strip only the paragraph, not individual characters
        paragraph = paragraph.strip()
        
        if not paragraph:
            # Empty line - add it as a space to maintain spacing
            lines.append(' ')
            continue
        
        # Check if text contains Arabic characters
        has_arabic = any('\u0600' <= char <= '\u06FF' for char in paragraph)
        
        if has_arabic:
            # For Arabic text, reshape first then apply bidi
            try:
                reshaped_text = reshape(paragraph)
                bidi_text = get_display(reshaped_text)
            except Exception as e:
                print(f"Error processing Arabic text: {e}")
                bidi_text = paragraph
            
            # Check if the whole text fits in one line
            if font.size(bidi_text)[0] <= max_width:
                lines.append(bidi_text)
            else:
                # Need to wrap - split by words and process
                # For Arabic, split after reshaping and bidi
                words = paragraph.split(' ')
                current_words = []
                
                for word in words:
                    if not word.strip():
                        continue
                    
                    # Test with current words + new word
                    test_paragraph = ' '.join(current_words + [word])
                    test_reshaped = reshape(test_paragraph)
                    test_bidi = get_display(test_reshaped)
                    
                    if font.size(test_bidi)[0] <= max_width:
                        current_words.append(word)
                    else:
                        # Current line is full, add it
                        if current_words:
                            line_text = ' '.join(current_words)
                            line_reshaped = reshape(line_text)
                            line_bidi = get_display(line_reshaped)
                            lines.append(line_bidi)
                        current_words = [word]
                
                # Add remaining words
                if current_words:
                    line_text = ' '.join(current_words)
                    line_reshaped = reshape(line_text)
                    line_bidi = get_display(line_reshaped)
                    lines.append(line_bidi)
        else:
            # English text - normal LTR handling
            words = paragraph.split(' ')
            current_line = []
            
            for word in words:
                # Skip empty words
                if not word:
                    continue
                    
                test_line = ' '.join(current_line + [word])
                if font.size(test_line)[0] <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
    
    return lines


class VoiceManager:
    """Manages voice playback for urgent ads - plays general voice 3 times per urgent ad"""
    
    def __init__(self, voice_file):
        self.voice_file = voice_file
        self.voice_available = os.path.exists(voice_file)
        self.voice_states = {}  # {timestamp: {"play_times": [time1, time2, time3], "played_count": int}}
        
        if not self.voice_available:
            print(f"Warning: Voice file not found: {voice_file}")
    
    def register_urgent_ad(self, timestamp):
        """Register an urgent ad to schedule voice playback"""
        if not self.voice_available or timestamp in self.voice_states:
            return
        
        try:
            post_time = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        except ValueError:
            return
        
        # Calculate 3 play times: at 0 hours, 1 hour, and 2 hours from post time
        play_times = [
            post_time,
            post_time + timedelta(hours=1),
            post_time + timedelta(hours=2)
        ]
        
        self.voice_states[timestamp] = {
            "play_times": play_times,
            "played_count": 0,
            "last_check": None
        }
        
        print(f"Registered urgent ad voice schedule for {timestamp}")
        for i, pt in enumerate(play_times):
            print(f"  Play {i+1}: {pt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def should_play_voice(self, timestamp):
        """Check if voice should play for this timestamp at current time"""
        if not self.voice_available or timestamp not in self.voice_states:
            return False
        
        state = self.voice_states[timestamp]
        now = datetime.now()
        
        # Check if we've reached the next scheduled play time
        if state["played_count"] < len(state["play_times"]):
            next_play_time = state["play_times"][state["played_count"]]
            
            # Check if we've passed the scheduled time and haven't checked it yet
            if now >= next_play_time:
                # Ensure we don't play multiple times for the same scheduled slot
                if state["last_check"] is None or state["last_check"] < next_play_time:
                    state["last_check"] = now
                    return True
        
        return False
    
    def mark_played(self, timestamp):
        """Mark that voice has been played once"""
        if timestamp in self.voice_states:
            self.voice_states[timestamp]["played_count"] += 1
            print(f"Voice played {self.voice_states[timestamp]['played_count']}/3 for {timestamp}")
    
    def play_voice(self):
        """Play the general voice file"""
        if not self.voice_available:
            return False
        
        try:
            pygame.mixer.music.load(self.voice_file)
            pygame.mixer.music.play()
            print(f"Playing urgent voice: {self.voice_file}")
            return True
        except Exception as e:
            print(f"Error playing voice {self.voice_file}: {e}")
            return False
    
    def cleanup_expired(self):
        """Remove voice states for expired posts (older than 3 hours)"""
        now = datetime.now()
        expired = []
        
        for timestamp in self.voice_states:
            try:
                post_time = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
                if now - post_time > timedelta(hours=3):
                    expired.append(timestamp)
            except ValueError:
                expired.append(timestamp)
        
        for ts in expired:
            print(f"Removing expired voice state for {ts}")
            del self.voice_states[ts]


class MediaSlide:
    """Single slide containing media (image/video) and caption"""
    
    def __init__(self, screen, source, caption, is_video=False, slide_index=None, 
                 is_urgent=False, timestamp=None, is_text_only=False):
        self.screen = screen
        self.source = source
        self.caption = caption
        self.is_video = is_video
        self.slide_index = slide_index
        self.surface = None
        self.is_urgent = is_urgent
        self.timestamp = timestamp
        self.is_text_only = is_text_only
        
        # Video player setup
        self.video = None
        self.playing = False
        self.video_finished = False
        
        # Load media (skip if text-only)
        if not is_text_only:
            if is_video:
                self.load_video()
            else:
                self.load_image()
    
    def load_image(self):
        """Load image and scale to fit screen while keeping aspect ratio (no cropping)."""
        try:
            img = Image.open(self.source)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            screen_width, screen_height = self.screen.get_size()
            img_w, img_h = img.size

            img_ratio = img_w / img_h
            screen_ratio = screen_width / screen_height

            # Fit longest edge to screen
            if img_w > img_h:
                # Image is wider → fit width
                new_w = screen_width
                new_h = int(screen_width / img_ratio)
                if new_h > screen_height:
                    new_h = screen_height
                    new_w = int(screen_height * img_ratio)
            else:
                # Image is taller → fit height
                new_h = screen_height
                new_w = int(screen_height * img_ratio)
                if new_w > screen_width:
                    new_w = screen_width
                    new_h = int(screen_width / img_ratio)

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Center image on screen
            img_str = img.tobytes()
            self.surface = pygame.image.fromstring(img_str, img.size, 'RGB')

        except Exception as e:
            print(f"Error loading image {self.source}: {e}")
            self.surface = None

    def load_video(self):
        """Initialize video player with screen-fitted size"""
        try:
            screen_width, screen_height = self.screen.get_size()
            self.video = Video(self.source)
            
            # Get original video size
            video_width, video_height = self.video.original_size
            
            # Calculate aspect ratios
            video_ratio = video_width / video_height
            screen_ratio = screen_width / screen_height
            
            # Scale to fit screen while maintaining aspect ratio (contain, not cover)
            if video_ratio > screen_ratio:
                # Video is wider - fit to width
                new_width = screen_width
                new_height = int(screen_width / video_ratio)
            else:
                # Video is taller - fit to height
                new_height = screen_height
                new_width = int(screen_height * video_ratio)
            
            # Resize video to calculated dimensions
            self.video.resize((new_width, new_height))
        except Exception as e:
            print(f"Error initializing video for {self.source}: {e}")
            self.video = None
    
    def play_video(self):
        """Start playing video"""
        if not self.is_video or not self.video:
            return
        
        try:
            self.playing = True
            self.video_finished = False
            self.video.restart()
        except Exception as e:
            print(f"Error playing video {self.source}: {e}")
            self.playing = False
    
    def stop_video(self):
        """Stop playing video"""
        if self.is_video and self.video:
            try:
                self.video.stop()
                self.playing = False
            except Exception as e:
                print(f"Error stopping video: {e}")
    
    def is_video_finished(self):
        """Check if video has finished playing"""
        if not self.is_video or not self.video:
            return False
        
        try:
            if not self.video.active:
                self.video_finished = True
                self.playing = False
                return True
            return False
        except Exception as e:
            return False
    
    def draw(self):
        """Draw the slide"""
        screen_width, screen_height = self.screen.get_size()

        # Clear screen
        self.screen.fill((0, 0, 0))
        
        # Handle text-only posts
        if self.is_text_only:
            # Draw text centered on blank screen
            content_font = load_arabic_font(48)
            text_color = (255, 255, 255)
            max_width = screen_width - 100
            
            # Process text with Arabic support
            lines = wrap_text(self.caption, content_font, max_width)
            
            # Calculate total height of all lines
            line_height = 60
            total_height = len(lines) * line_height
            
            # Start from center and work outward
            y_offset = (screen_height - total_height) // 2
            
            for line in lines:
                text_surface = content_font.render(line, True, text_color)
                text_rect = text_surface.get_rect(center=(screen_width // 2, y_offset))
                self.screen.blit(text_surface, text_rect)
                y_offset += line_height
            
        elif self.is_video and self.video:
            # Draw video frame centered and fitted to screen
            video_width, video_height = self.video.current_size
            
            # Center the video on screen
            video_x = (screen_width - video_width) // 2
            video_y = (screen_height - video_height) // 2
            
            if self.video.draw(self.screen, (video_x, video_y), force_draw=False):
                # Video frame was updated
                pass
                
            # Draw caption box at the bottom for videos
            if self.caption:
                self._draw_caption_box()
                    
        elif self.surface:
            # Draw image centered
            img_rect = self.surface.get_rect()
            img_rect.center = (screen_width // 2, screen_height // 2)
            self.screen.blit(self.surface, img_rect)

            # Draw caption box at the bottom for images
            if self.caption:
                self._draw_caption_box()
        
        # Add urgent indicator if urgent (for all slide types)
        if self.is_urgent:
            urgent_font = pygame.font.SysFont("Calibri", 28, bold=True)
            urgent_text = urgent_font.render("URGENT", True, (255, 50, 50))
            screen_width, _ = self.screen.get_size()
            self.screen.blit(urgent_text, (screen_width - 150, 20))
    
    def _draw_caption_box(self):
        """Draw caption box with Arabic/English support at the bottom of the screen"""
        screen_width, screen_height = self.screen.get_size()
        caption_height = 150
        caption_y = screen_height - caption_height

        # Gradient overlay
        gradient_surface = pygame.Surface((screen_width, caption_height), pygame.SRCALPHA)
        steps = 20
        for i in range(steps):
            alpha = int(255 * 0.6 * (i / steps))
            color = (0, 0, 0, alpha)
            step_height = caption_height // steps
            pygame.draw.rect(gradient_surface, color,
                            (0, i * step_height, screen_width, step_height))

        self.screen.blit(gradient_surface, (0, screen_height - caption_height))

        # Draw caption text with Arabic support
        font = load_arabic_font(36)
        text_color = (255, 255, 255)
        max_width = screen_width - 40
        lines = wrap_text(self.caption, font, max_width)

        y_offset = caption_y + 20
        for line in lines[:3]:  # Max 3 lines
            text_surface = font.render(line, True, text_color)
            self.screen.blit(text_surface, (20, y_offset))
            y_offset += 40
    
    def cleanup(self):
        """Release resources"""
        self.stop_video()
        if self.video:
            try:
                self.video.close()
            except:
                pass
    def draw_with_offset(self, offset_ratio=0):
        """Draw slide with offset - smoother animation
        
        This should replace draw_with_offset in MediaSlide class
        """
        screen_width, screen_height = self.screen.get_size()
        
        # Amplify the offset for better visual feedback
        # But cap it to prevent sliding too far off screen
        pixel_offset = int(screen_width * offset_ratio * 1.0)  # 1.5x amplification
        pixel_offset = max(-screen_width // 2, min(screen_width // 2, pixel_offset))
        
        # Clear screen
        self.screen.fill((0, 0, 0))
        
        # Handle text-only posts
        if self.is_text_only:
            content_font = load_arabic_font(48)
            text_color = (255, 255, 255)
            max_width = screen_width - 100
            lines = wrap_text(self.caption, content_font, max_width)
            line_height = 60
            total_height = len(lines) * line_height
            y_offset = (screen_height - total_height) // 2
            
            for line in lines:
                text_surface = content_font.render(line, True, text_color)
                text_rect = text_surface.get_rect(
                    center=(screen_width // 2 + pixel_offset, y_offset)
                )
                self.screen.blit(text_surface, text_rect)
                y_offset += line_height
        
        # Handle video
        elif self.is_video and self.video:
            video_width, video_height = self.video.current_size
            video_x = (screen_width - video_width) // 2 + pixel_offset
            video_y = (screen_height - video_height) // 2
            self.video.draw(self.screen, (video_x, video_y), force_draw=False)
            
            if self.caption:
                self._draw_caption_box()
        
        # Handle image
        elif self.surface:
            img_rect = self.surface.get_rect()
            img_rect.center = (screen_width // 2 + pixel_offset, screen_height // 2)
            self.screen.blit(self.surface, img_rect)
            
            if self.caption:
                self._draw_caption_box()
        
        # Draw urgent indicator
        if self.is_urgent:
            urgent_font = pygame.font.SysFont("Calibri", 28, bold=True)
            urgent_text = urgent_font.render("URGENT", True, (255, 50, 50))
            self.screen.blit(urgent_text, (screen_width - 150 + pixel_offset, 20))

class NavigationBar:
    """Navigation bar with pill indicators that properly contains all indicators"""
    
    def __init__(self, screen, num_slides):
        self.screen = screen
        self.num_slides = num_slides
        self.active_index = 0
        
        # Navigation bar dimensions - obround (pill) shape
        self.indicator_width = 40
        self.indicator_height = 20
        self.spacing = 5
        self.padding = 10
        
        # Calculate required width for all indicators
        indicators_width = (self.indicator_width + self.spacing) * num_slides - self.spacing
        total_width = indicators_width + 2 * self.padding
        
        # Get screen dimensions
        screen_width, screen_height = screen.get_size()
        
        # Limit max width to 80% of screen width
        max_width = int(screen_width * 0.8)
        
        if total_width > max_width:
            # Too many indicators - adjust sizing to fit
            available_width = max_width - 2 * self.padding
            # Calculate how many indicators can fit with normal spacing
            self.indicator_width = min(40, (available_width + self.spacing) // num_slides - self.spacing)
            # Ensure minimum width of 15px per indicator
            self.indicator_width = max(15, self.indicator_width)
            # Recalculate spacing to distribute evenly
            if num_slides > 1:
                self.spacing = max(3, (available_width - self.indicator_width * num_slides) // (num_slides - 1))
            self.width = max_width
        else:
            self.width = total_width
        
        self.height = 40
        
        # Center horizontally, position at bottom
        self.x = (screen_width - self.width) // 2
        self.y = screen_height - 80
    
    def set_active(self, index):
        """Set active indicator"""
        self.active_index = index
    
    def draw(self):
        """Draw navigation bar with obround indicators that fit within the box"""
        # Draw background with rounded corners
        bg_rect = (self.x, self.y, self.width, self.height)
        draw_rounded_rect(self.screen, (50, 50, 50, 128), bg_rect, 20)
        
        # Calculate actual available width for indicators
        available_width = self.width - 2 * self.padding
        
        # Draw obround indicators (pill-shaped) - centered and evenly distributed
        indicator_y = self.y + (self.height - self.indicator_height) // 2
        
        # Calculate starting position to center indicators
        total_indicators_width = self.indicator_width * self.num_slides + self.spacing * (self.num_slides - 1)
        start_x = self.x + self.padding + (available_width - total_indicators_width) // 2
        
        for i in range(self.num_slides):
            indicator_x = start_x + i * (self.indicator_width + self.spacing)
            indicator_rect = (indicator_x, indicator_y, self.indicator_width, self.indicator_height)
            
            if i == self.active_index:
                # Active indicator - bright blue obround
                color = (32, 142, 208)
            else:
                # Inactive indicator - gray obround
                color = (128, 128, 128, 128)
            
            # Draw obround (pill shape)
            radius = self.indicator_height // 2
            draw_rounded_rect(self.screen, color, indicator_rect, radius)


class Notification:
    """Temporary notification overlay"""
    
    def __init__(self, screen, message):
        self.screen = screen
        self.message = message
        self.start_time = pygame.time.get_ticks()
        self.duration = 3000  # 3 seconds
        self.alpha = 255
    
    def is_active(self):
        """Check if notification is still active"""
        elapsed = pygame.time.get_ticks() - self.start_time
        return elapsed < self.duration
    
    def draw(self):
        """Draw notification"""
        if not self.is_active():
            return
        
        elapsed = pygame.time.get_ticks() - self.start_time
        
        # Fade out in last second
        if elapsed > self.duration - 1000:
            self.alpha = int(255 * (self.duration - elapsed) / 1000)
        
        screen_width, screen_height = self.screen.get_size()
        
        # Create notification surface
        notif_width = 400
        notif_height = 60
        notif_surface = pygame.Surface((notif_width, notif_height), pygame.SRCALPHA)
        
        # Draw rounded background
        draw_rounded_rect(notif_surface, (26, 26, 26, int(217 * self.alpha / 255)), 
                         (0, 0, notif_width, notif_height), 15)
        
        # Draw text
        font = pygame.font.Font(None, 32)
        text_surface = font.render(self.message, True, (255, 255, 255, self.alpha))
        text_rect = text_surface.get_rect(center=(notif_width // 2, notif_height // 2))
        notif_surface.blit(text_surface, text_rect)
        
        # Position at top center
        notif_x = (screen_width - notif_width) // 2
        notif_y = 50
        
        self.screen.blit(notif_surface, (notif_x, notif_y))


class ThelabApp:
    """Main application"""
    
    def __init__(self):
        # Setup display
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("The Lab Media Carousel")
        
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Voice manager for urgent ads (uses single general voice file)
        self.voice_manager = VoiceManager(URGENT_VOICE_FILE)
        
        # Load posts
        posts = load_posts()
        urgent = [p for p in posts if p.get("urgent")]
        
        self.slides_data = urgent if urgent else (posts if posts else [
            {"media": "", "caption": "Your ads here", "is_video": False, "is_text_only": True}
        ])
        
        # Create slides
        self.slides = []
        self.current_index = 0
        
        for i, slide_data in enumerate(self.slides_data):
            slide = MediaSlide(
                self.screen,
                slide_data["media"],
                slide_data.get("caption", ""),
                slide_data.get("is_video", False),
                slide_index=i,
                is_urgent=slide_data.get("urgent", False),
                timestamp=slide_data.get("timestamp"),
                is_text_only=slide_data.get("is_text_only", False)
            )
            self.slides.append(slide)
            
            # Register urgent ads with voice manager
            if slide_data.get("urgent") and slide_data.get("timestamp"):
                self.voice_manager.register_urgent_ad(slide_data["timestamp"])
        
        # Create navigation bar
        self.nav = NavigationBar(self.screen, len(self.slides))
        
        # Setup gesture control
        self.mode = "auto"
        self.gesture = GestureControl(show_display=False, callback=self.on_gesture)
        
        # Timers
        self.last_auto_scroll = pygame.time.get_ticks()
        self.last_refresh = pygame.time.get_ticks()
        self.last_voice_check = pygame.time.get_ticks()
        self.auto_scroll_interval = 10000  # 10 seconds
        self.refresh_interval = 10000  # 10 seconds
        self.voice_check_interval = 30000  # Check every 30 seconds
        
        # Notifications
        self.notifications = []
        
        # Start first slide
        if self.slides:
            self.start_current_slide()
        
        self.last_fingerprint = None
    
    def start_current_slide(self):
        """Start playing current slide"""
        if not self.slides:
            return
        
        # Stop all videos
        for slide in self.slides:
            slide.stop_video()
        
        # Clear screen before starting new slide
        self.screen.fill((0, 0, 0))
        pygame.display.flip()
        
        # Start current slide
        slide = self.slides[self.current_index]
        
        if slide.is_video:
            slide.play_video()
        
        self.nav.set_active(self.current_index)
        self.last_auto_scroll = pygame.time.get_ticks()
    
    def check_and_play_urgent_voices(self):
        """Check all urgent ads and play voice if scheduled"""
        for slide in self.slides:
            if slide.is_urgent and slide.timestamp:
                if self.voice_manager.should_play_voice(slide.timestamp):
                    self.voice_manager.play_voice()
                    self.voice_manager.mark_played(slide.timestamp)
    
    def next_slide(self):
        """Go to next slide"""
        self.current_index = (self.current_index + 1) % len(self.slides)
        self.start_current_slide()
    
    def previous_slide(self):
        """Go to previous slide"""
        self.current_index = (self.current_index - 1) % len(self.slides)
        self.start_current_slide()
    
    def show_notification(self, message):
        """Show notification"""
        notif = Notification(self.screen, message)
        self.notifications.append(notif)
    
    def on_gesture(self, event):
        """Handle gesture events - Meta Quest style
        
        This should replace the on_gesture method in ThelabApp class
        """
        event_type = event.get("type")
        
        # Initialize state
        if not hasattr(self, 'gesture_state'):
            self.gesture_state = {
                'dragging': False,
                'drag_offset': 0,
                'slide_changed': False
            }
        
        # PINCH START - Grab the slide
        if event_type == "pinch_start":
            self.gesture_state['dragging'] = True
            self.gesture_state['drag_offset'] = 0
            self.gesture_state['slide_changed'] = False
            self.mode = "gesture"
            self.show_notification("Pinched")
            return
        
        # PINCH DRAG - Slide follows hand
        elif event_type == "pinch_drag":
            if not self.gesture_state['dragging']:
                return
            
            offset = event.get("offset", 0)
            self.gesture_state['drag_offset'] = offset
            
            # Check if we should trigger slide change
            # Threshold for slide change (0.3 = 30% of screen width)
            threshold = 0.25
            
            # Change slide while dragging (Meta Quest style)
            if not self.gesture_state['slide_changed']:
                if offset > threshold:
                    # Swiped RIGHT -> Previous slide
                    self.previous_slide()
                    self.gesture_state['slide_changed'] = True
                    self.gesture_state['drag_offset'] = 0  # Reset visual offset
                    self.show_notification("← Previous")
                    
                elif offset < -threshold:
                    # Swiped LEFT -> Next slide
                    self.next_slide()
                    self.gesture_state['slide_changed'] = True
                    self.gesture_state['drag_offset'] = 0  # Reset visual offset
                    self.show_notification("Next →")
            
            return
        
        # PINCH RELEASE - Let go
        elif event_type == "pinch_release":
            if not self.gesture_state['dragging']:
                return
            
            # Clean up
            self.gesture_state['dragging'] = False
            self.gesture_state['drag_offset'] = 0
            self.gesture_state['slide_changed'] = False
            self.mode = "auto"
            self.show_notification("Released")
            return
        
    def refresh_posts(self):
        """Refresh posts and rebuild if changed"""
        posts = load_posts()
        new_fp = [(p["media"], p["caption"], p.get("urgent", False)) for p in posts]
        
        if self.last_fingerprint == new_fp:
            return
        
        self.last_fingerprint = new_fp
        
        # Clean up old slides
        for slide in self.slides:
            slide.cleanup()
        
        # Reload slides
        urgent = [p for p in posts if p.get("urgent")]
        self.slides_data = urgent if urgent else (posts if posts else [
            {"media": "", "caption": "Your ads here", "is_video": False, "is_text_only": True}
        ])
        
        self.slides = []
        # Don't reset voice manager - keep tracking existing urgent ads
        
        for i, slide_data in enumerate(self.slides_data):
            slide = MediaSlide(
                self.screen,
                slide_data["media"],
                slide_data.get("caption", ""),
                slide_data.get("is_video", False),
                slide_index=i,
                is_urgent=slide_data.get("urgent", False),
                timestamp=slide_data.get("timestamp"),
                is_text_only=slide_data.get("is_text_only", False)
            )
            self.slides.append(slide)
            
            # Register new urgent ads with voice manager
            if slide_data.get("urgent") and slide_data.get("timestamp"):
                self.voice_manager.register_urgent_ad(slide_data["timestamp"])
        
        # Update nav
        self.nav = NavigationBar(self.screen, len(self.slides))
        
        # Reset to first slide
        self.current_index = 0
        if self.slides:
            self.start_current_slide()
    
    def run(self):
        """Main game loop"""
        while self.running:
            current_time = pygame.time.get_ticks()
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_LEFT:
                        self.previous_slide()
                    elif event.key == pygame.K_RIGHT:
                        self.next_slide()
            
            # Run gesture detection
            try:
                self.gesture.run_once()
            except Exception as e:
                pass
            
            # Check scheduled voices periodically (every 30 seconds)
            if current_time - self.last_voice_check > self.voice_check_interval:
                self.check_and_play_urgent_voices()
                self.voice_manager.cleanup_expired()
                self.last_voice_check = current_time
            
            # Check if current video finished, then auto-advance
            current_slide = self.slides[self.current_index]
            if current_slide.is_video_finished():
                self.next_slide()
            
            # Auto-scroll for images and text-only slides
            if self.mode == "auto" and not current_slide.is_video:
                if current_time - self.last_auto_scroll > self.auto_scroll_interval:
                    self.next_slide()
            
            # Refresh posts
            if current_time - self.last_refresh > self.refresh_interval:
                self.refresh_posts()
                self.last_refresh = current_time
            
            # Draw current slide
            if self.slides:
                if (hasattr(self, 'gesture_state') and 
                    self.gesture_state.get('dragging', False) and 
                    abs(self.gesture_state.get('drag_offset', 0)) > 0.01):
                    # Draw with drag offset
                    self.slides[self.current_index].draw_with_offset(
                        self.gesture_state['drag_offset']
                    )
                else:
                    # Normal draw
                    self.slides[self.current_index].draw()
            
            # Draw navigation bar
            self.nav.draw()
            
            # Draw notifications
            self.notifications = [n for n in self.notifications if n.is_active()]
            for notif in self.notifications:
                notif.draw()
            
            # Update display
            pygame.display.flip()
            self.clock.tick(30)  # 30 FPS
        
        # Cleanup
        pygame.mixer.music.stop()
        for slide in self.slides:
            slide.cleanup()
        pygame.quit()


# if __name__ == '__main__':
#     app = ThelabApp()
#     app.run()