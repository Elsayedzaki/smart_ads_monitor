import cv2
import mediapipe as mp
import math
import time

class GestureControl:
    def __init__(self, camera_index=0, show_display=False, callback=None):
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.prev_x = None
        self.prev_time = time.time()
        self.cap = cv2.VideoCapture(camera_index)
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.show_display = show_display
        self.callback = callback
        self.hand_visible_since = None
        self.hand_last_seen = None


    

    # --- Gesture detection helpers ---
    def distance(self, p1, p2):
        return math.hypot(p1.x - p2.x, p1.y - p2.y)

    def is_fist(self, landmarks):
        tips = [8, 12, 16, 20]
        palm = landmarks[0]
        for tip in tips:
            if self.distance(landmarks[tip], palm) > 0.12:
                return False
        return True
    
    def is_palm(self, landmarks):
        # Simple heuristic: fingers extended (tips far from palm)
        tips = [8, 12, 16, 20]
        palm = landmarks[0]
        extended = sum(1 for tip in tips if self.distance(landmarks[tip], palm) > 0.15)
        return extended >= 3  # at least 3 fingers extended


    def is_pinch(self, landmarks):
        thumb = landmarks[4]
        index = landmarks[8]
        return self.distance(thumb, index) < 0.05

    def swipe_direction(self, x):
        if self.prev_x is None:
            return None
        delta = x - self.prev_x
        if delta > 0.15:
            return "right"
        elif delta < -0.15:
            return "left"
        return None

    # --- Main loop ---
    def run(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("⚠️ Camera not accessible")
                break

            frame = cv2.flip(frame, 1)
            h, w, c = frame.shape

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb)

            if results.multi_hand_landmarks:
                for handLms in results.multi_hand_landmarks:
                    lm = handLms.landmark

                    # FIST → lock screen
                    if self.is_fist(lm):
                        cv2.putText(frame, "LOCK SCREEN", (10, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 3)

                    # SWIPE → next / previous page
                    x = lm[9].x
                    dir = self.swipe_direction(x)
                    self.prev_x = x

                    if dir == "right":
                        cv2.putText(frame, "NEXT PAGE →", (10, 150),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 3)
                    elif dir == "left":
                        cv2.putText(frame, "← PREVIOUS PAGE", (10, 150),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 3)

                    self.mp_draw.draw_landmarks(frame, handLms, self.mp_hands.HAND_CONNECTIONS)
            if self.show_display:
                cv2.imshow("Gesture Control", frame)
            if cv2.waitKey(1) == 27:  # ESC key
                break

        self.cap.release()
        cv2.destroyAllWindows()


    def run_once(self):
        ret, frame = self.cap.read()
        if not ret:
            return
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        if results.multi_hand_landmarks:
            for handLms in results.multi_hand_landmarks:
                lm = handLms.landmark
                x = lm[9].x

                # Palm detection
                if self.is_palm(lm):
                    if self.hand_visible_since is None:
                        self.hand_visible_since = time.time()
                    self.hand_last_seen = time.time()

                    # If palm held for 2s → enable gesture mode
                    if time.time() - self.hand_visible_since >= 2:
                        if self.callback:
                            self.callback({"mode": "gesture_ready"})
                else:
                    self.hand_visible_since = None
                    self.hand_last_seen = time.time()

                # Swipe detection (only in gesture mode)
                if self.callback:
                    self.callback({"x": x})
                if self.prev_x is not None:
                    delta = x - self.prev_x
                    if delta > 0.15 and self.callback:
                        self.callback({"swipe": "right"})
                    elif delta < -0.15 and self.callback:
                        self.callback({"swipe": "left"})
                self.prev_x = x
        else:
            # No hand detected
            if self.hand_last_seen and time.time() - self.hand_last_seen >= 5:
                if self.callback:
                    self.callback({"mode": "auto"})
            self.hand_visible_since = None




# # --- Run the program ---
# if __name__ == "__main__":
#     app = GestureControl(show_display=False)
#     app.run()