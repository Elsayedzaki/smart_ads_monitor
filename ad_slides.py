import pygame
from pyvidplayer2 import Video
import json
from datetime import datetime, timedelta
import threading
from PIL import Image
from gesture import GestureControl
import os
pygame.init()
pygame.font.init()
pygame.mixer.init()

# Configuration: Path to the general voice file for urgent ads
URGENT_VOICE_FILE = "luvvoice.com-20251129-MWN5ah.mp3"  # Change this to your voice file path


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
        media = post.get("media_path", "").strip()
        timestamp = post.get("timestamp")

        if not media or not timestamp:
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
            media_path = media if os.path.isabs(media) else os.path.join(os.getcwd(), "static", media)
            if os.path.exists(media_path):
                try:
                    os.remove(media_path)
                except Exception as e:
                    pass
            continue

        # Normalize media path
        if not os.path.isabs(media):
            media = os.path.join(os.getcwd(), "static", media)

        if not os.path.exists(media):
            continue

        # Detect media type
        ext = os.path.splitext(media)[1].lower()
        is_video = ext in [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"]

        valid_posts.append({
            "media": media,
            "caption": post.get("text", ""),
            "urgent": (status == "urgent"),
            "is_video": is_video,
            "timestamp": timestamp
        })
        remaining_posts.append(post)

    # Save non-expired posts back to JSON
    try:
        with open(json_file, "w") as f:
            json.dump(remaining_posts, f, indent=4)
    except Exception as e:
        pass
    
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
    """Wrap text to fit within max_width"""
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
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
                 is_urgent=False, timestamp=None):
        self.screen = screen
        self.source = source
        self.caption = caption
        self.is_video = is_video
        self.slide_index = slide_index
        self.surface = None
        self.is_urgent = is_urgent
        self.timestamp = timestamp
        
        # Video player setup
        self.video = None
        self.playing = False
        self.video_finished = False
        
        # Load media
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
        
        if self.is_video and self.video:
            # Draw video frame centered and fitted to screen
            screen_width, screen_height = self.screen.get_size()
            
            # Get video size
            video_width, video_height = self.video.current_size
            
            # Center the video on screen
            video_x = (screen_width - video_width) // 2
            video_y = (screen_height - video_height) // 2
            
            if self.video.draw(self.screen, (video_x, video_y), force_draw=False):
                # Video frame was updated
                pass
        elif self.surface:
            # Draw image centered
            img_rect = self.surface.get_rect()
            img_rect.center = (screen_width // 2, screen_height // 2)
            self.screen.blit(self.surface, img_rect)

        # Draw caption box at the bottom (for both image and video)
        caption_height = 150
        caption_y = screen_height - caption_height

        # Gradient overlay (transparent black)
        gradient_surface = pygame.Surface((screen_width, caption_height), pygame.SRCALPHA)
        steps = 20
        for i in range(steps):
            alpha = int(255 * 0.6 * (i / steps))
            color = (0, 0, 0, alpha)
            step_height = caption_height // steps
            pygame.draw.rect(gradient_surface, color,
                            (0, i * step_height, screen_width, step_height))

        self.screen.blit(gradient_surface, (0, screen_height - caption_height))

        # Draw caption text
        font = pygame.font.SysFont("Calibri", 36) 
        text_color = (255, 255, 255)
        max_width = screen_width - 40
        lines = wrap_text(self.caption, font, max_width)

        y_offset = caption_y + 20
        for line in lines[:3]:  # Max 3 lines
            text_surface = font.render(line, True, text_color)
            self.screen.blit(text_surface, (20, y_offset))
            y_offset += 40
        
        # Add urgent indicator if urgent
        if self.is_urgent:
            urgent_font = pygame.font.SysFont("Calibri", 28, bold=True)
            urgent_text = urgent_font.render("🔴 URGENT", True, (255, 50, 50))
            self.screen.blit(urgent_text, (screen_width - 150, 20))
    
    def cleanup(self):
        """Release resources"""
        self.stop_video()
        if self.video:
            try:
                self.video.close()
            except:
                pass


class NavigationBar:
    """Navigation bar with pill indicators"""
    
    def __init__(self, screen, num_slides):
        self.screen = screen
        self.num_slides = num_slides
        self.active_index = 0
        
        # Navigation bar dimensions - obround (pill) shape
        self.indicator_width = 40
        self.indicator_height = 20
        self.spacing = 5
        self.padding = 10
        
        total_width = (self.indicator_width + self.spacing) * num_slides + 2 * self.padding
        self.width = min(total_width, 400)
        self.height = 40
        
        screen_width, screen_height = screen.get_size()
        self.x = (screen_width - self.width) // 2
        self.y = screen_height - 80
    
    def set_active(self, index):
        """Set active indicator"""
        self.active_index = index
    
    def draw(self):
        """Draw navigation bar with obround indicators"""
        # Draw background with rounded corners
        bg_rect = (self.x, self.y, self.width, self.height)
        draw_rounded_rect(self.screen, (50, 50, 50, 128), bg_rect, 20)
        
        # Draw obround indicators (pill-shaped)
        start_x = self.x + self.padding
        indicator_y = self.y + (self.height - self.indicator_height) // 2
        
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
            {"media": "", "caption": "Your ads here", "is_video": False}
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
                timestamp=slide_data.get("timestamp")
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
        """Handle gesture events"""
        if "mode" in event:
            if event["mode"] == "gesture_ready":
                self.mode = "gesture"
                self.show_notification("Gesture mode enabled")
            elif event["mode"] == "auto":
                self.mode = "auto"
        
        if self.mode == "gesture" and "swipe" in event:
            if event["swipe"] == "right":
                self.previous_slide()
            elif event["swipe"] == "left":
                self.next_slide()
    
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
            {"media": "", "caption": "Your ads here", "is_video": False}
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
                timestamp=slide_data.get("timestamp")
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
            
            # Auto-scroll for images only
            if self.mode == "auto" and not current_slide.is_video:
                if current_time - self.last_auto_scroll > self.auto_scroll_interval:
                    self.next_slide()
            
            # Refresh posts
            if current_time - self.last_refresh > self.refresh_interval:
                self.refresh_posts()
                self.last_refresh = current_time
            
            # Draw current slide
            if self.slides:
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