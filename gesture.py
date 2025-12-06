import cv2
import mediapipe as mp
import math
import time

class GestureControl:
    def __init__(self, camera_index=0, show_display=False, callback=None):
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(camera_index)
        self.hands = self.mp_hands.Hands(
            max_num_hands=1, 
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.show_display = show_display
        self.callback = callback
        
        # Pinch tracking
        self.is_pinching = False
        self.pinch_start_x = None
        self.current_x = None
        self.last_callback_time = 0
    
    def dist(self, p1, p2):
        """Calculate distance between two points"""
        return math.hypot(p1.x - p2.x, p1.y - p2.y)
    
    def detect_pinch(self, lm):
        """Detect pinch gesture - thumb tip close to index tip"""
        thumb_tip = lm[4]
        index_tip = lm[8]
        distance = self.dist(thumb_tip, index_tip)
        return distance < 0.05  # Threshold for pinch
    
    def run_once(self):
        """Process single frame - Meta Quest style"""
        ret, frame = self.cap.read()
        if not ret:
            return
        
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        
        current_time = time.time()
        
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            lm = hand_landmarks.landmark
            
            # Get hand center X position (normalized 0-1)
            hand_center_x = lm[9].x
            
            # Detect pinch
            pinching_now = self.detect_pinch(lm)
            
            # Draw hand landmarks if display enabled
            if self.show_display:
                self.mp_draw.draw_landmarks(
                    frame, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS
                )
            
            # STATE: Starting pinch
            if pinching_now and not self.is_pinching:
                self.is_pinching = True
                self.pinch_start_x = hand_center_x
                self.current_x = hand_center_x
                
                if self.callback:
                    self.callback({
                        "type": "pinch_start",
                        "x": hand_center_x
                    })
                self.last_callback_time = current_time
            
            # STATE: Maintaining pinch and moving
            elif pinching_now and self.is_pinching:
                self.current_x = hand_center_x
                
                # Calculate offset from pinch start
                offset = hand_center_x - self.pinch_start_x
                
                # Send continuous updates (throttled to ~60fps)
                if current_time - self.last_callback_time > 0.016:  # ~60fps
                    if self.callback:
                        self.callback({
                            "type": "pinch_drag",
                            "x": hand_center_x,
                            "offset": offset,
                            "start_x": self.pinch_start_x
                        })
                    self.last_callback_time = current_time
            
            # STATE: Released pinch
            elif not pinching_now and self.is_pinching:
                final_offset = self.current_x - self.pinch_start_x if self.current_x else 0
                
                if self.callback:
                    self.callback({
                        "type": "pinch_release",
                        "final_offset": final_offset,
                        "x": hand_center_x
                    })
                
                # Reset state
                self.is_pinching = False
                self.pinch_start_x = None
                self.current_x = None
        
        else:
            # No hand detected
            if self.is_pinching:
                # Force release
                if self.callback:
                    self.callback({
                        "type": "pinch_release",
                        "final_offset": 0,
                        "x": 0.5
                    })
                
                self.is_pinching = False
                self.pinch_start_x = None
                self.current_x = None
        
        if self.show_display:
            # Draw pinch indicator
            if self.is_pinching:
                cv2.putText(frame, "PINCHING", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            cv2.imshow("Gesture Control", frame)
            cv2.waitKey(1)
    
    def cleanup(self):
        """Release resources"""
        self.cap.release()
        if self.show_display:
            cv2.destroyAllWindows()