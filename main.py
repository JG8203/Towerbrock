import pygame
from pygame import mixer
from math import sin, cos
from pygame.locals import *
import cv2
import numpy as np
import dlib
import imutils
from imutils import face_utils
from scipy.spatial import distance as dist
import sys
import threading
import queue
import time
import random

# -------------------------------
# Blink detection setup
# -------------------------------

def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

class BlinkDetector:
    def __init__(self):
        self.EYE_AR_THRESH = 0.25  # Increased sensitivity (was 0.22)
        self.EYE_AR_CONSEC_FRAMES = 2  # Faster detection (was 3)
        self.counter = 0
        self.detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
        self.lStart, self.lEnd = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
        self.rStart, self.rEnd = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
        
    def detect_blink(self, gray_frame):
        """Process a frame and return blink_detected (True/False)"""
        rects = self.detector(gray_frame, 0)
        blink_detected = False
        
        for rect in rects:
            shape = self.predictor(gray_frame, rect)
            shape = face_utils.shape_to_np(shape)
            
            # Blink detection
            leftEye = shape[self.lStart:self.lEnd]
            rightEye = shape[self.rStart:self.rEnd]
            leftEAR = eye_aspect_ratio(leftEye)
            rightEAR = eye_aspect_ratio(rightEye)
            ear = (leftEAR + rightEAR) / 2.0
            
            if ear < self.EYE_AR_THRESH:
                self.counter += 1
            else:
                if self.counter >= self.EYE_AR_CONSEC_FRAMES:
                    self.counter = 0
                    blink_detected = True
                self.counter = 0
            
        return blink_detected

class CameraThread(threading.Thread):
    def __init__(self, frame_queue, blink_queue):
        super().__init__()
        self.frame_queue = frame_queue
        self.blink_queue = blink_queue
        self.camera = cv2.VideoCapture(0)
        self.blink_detector = BlinkDetector()
        self.running = True
        self.daemon = True  # Dies when main thread dies
        
        # Set camera properties for better performance
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_FPS, 30)
        
    def run(self):
        """Main camera processing loop running in separate thread"""
        while self.running and self.camera.isOpened():
            ret, frame = self.camera.read()
            if not ret:
                continue
                
            # Mirror the frame
            frame = cv2.flip(frame, 1)
            
            # Process blink detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blink_detected = self.blink_detector.detect_blink(gray)
            
            # Convert frame for pygame display
            display_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            display_frame = np.rot90(display_frame)
            
            # Put frame in queue (non-blocking, replace old frame if queue is full)
            try:
                self.frame_queue.put_nowait(display_frame)
            except queue.Full:
                try:
                    self.frame_queue.get_nowait()  # Remove old frame
                    self.frame_queue.put_nowait(display_frame)  # Add new frame
                except queue.Empty:
                    pass
            
            # Put blink detection result in queue
            if blink_detected:
                try:
                    self.blink_queue.put_nowait(True)
                except queue.Full:
                    pass  # Skip if queue is full
                    
            # More frequent checking (was 0.016)
            time.sleep(0.008)  # ~120 FPS for camera thread
    
    def stop(self):
        """Stop the camera thread"""
        self.running = False
        if self.camera.isOpened():
            self.camera.release()

# -------------------------------
# Game setup
# -------------------------------
pygame.init()
pygame.mixer.pre_init(44100, 16, 2, 4096)
pygame.mixer.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Tower Brocks")
icon = pygame.image.load("assets/icon.png")
pygame.display.set_icon(icon)

#background
background = pygame.image.load("assets/background0.jpg")
background2 = pygame.image.load("assets/background1.jpg")
background3 = pygame.image.load("assets/background2.jpg")
background4 = pygame.image.load("assets/background3.jpg")
screenX = 0
screenY = 0

#background music
mixer.music.load("assets/bgm.wav")
mixer.music.play(-1)

#sound
build_sound = mixer.Sound("assets/build.wav")
gold_build_sound = mixer.Sound("assets/gold.wav")
over_music = mixer.Sound("assets/overmusic.wav")
fall_sound = mixer.Sound("assets/fall.wav")

#score
score_value = 0
textX = 10
textY = 10

#font
over_font = pygame.font.Font("freesansbold.ttf", 64)
mini_font = pygame.font.Font("freesansbold.ttf",16)
score_font = pygame.font.Font("freesansbold.ttf",32)

#gravity settings
grav = 0.5
rope_length = 120
force = -0.001
origin = (400,3)

#FPS CONTROL
clock = pygame.time.Clock()
BLINK_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(BLINK_EVENT, 800)

def show_score(x,y):
    score = score_font.render("Score: " + str(score_value), True, (0,0,0))
    screen.blit(score,(x,y))

class Block(pygame.sprite.Sprite):
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.image.load("assets/block.png")
        self.rotimg = self.image
        self.x = 37
        self.y = 150
        self.xlast = 0
        self.xchange = 100
        self.speed = 0
        self.acceleration = 0
        self.speedmultiplier = 1
        self.rect = self.image.get_rect()
        # ready, dropped , landed, scroll ,over, miss
        self.state = "ready"
        self.angle = 45
        
    def swing(self, tower_level=0):
        """Original swinging behavior (no nose control)"""
        self.x = 370 + rope_length * sin(self.angle)
        self.y = 20 + rope_length * cos(self.angle)
        self.angle += self.speed
        self.acceleration = sin(self.angle) * force
        self.speed += self.acceleration

    def drop(self, tower):
        if self.state == "ready":
            self.state = "dropped"
            self.xlast = self.x

        if self.collided(tower):
            self.state = "landed"

        if tower.size == 0 and self.y>=536:
            self.state = "landed"

        if tower.size >=1 and self.y>=536:
            self.state = "miss"

        if self.state == "dropped":
            self.speed += grav
            self.y += self.speed

    def get_state(self):
        return self.state

    def collided(self,tower):
        # check if fits
        if tower.size == 0:
            return False
        if (self.xlast < tower.xlist[-1] + 60) and (self.xlast > tower.xlist[-1] - 60) and (tower.y - self.y <= 70 ):
            if (self.xlast < tower.xlist[-1] + 5) and (self.xlast > tower.xlist[-1] - 5):
                tower.golden = True
            else:
                tower.golden = False
                tower.image = tower.imageMAIN
            return True
        else:
            return False

    def to_build(self,tower):
        brock.state = "scroll"
        if tower.size == 0 or self.collided(tower):
            return True
        return False

    def collapse(self, tower):
        if (self.xlast > tower.xlist[-2] + 40) or (self.xlast < tower.xlist[-2] - 40):
            if brock.collided(tower):
                brock.state = "over"

    def rotate(self,direction):
        self.rotimg = pygame.transform.rotate(self.image, self.angle)
        if direction == "l":
            self.angle += 1 % 360
        if direction == "r":
            self.angle -= 1 % 360

    def to_fall(self, tower):
        self.y += 5

        if (self.xlast < tower.xlist[-2] + 30):
            self.x -= 2
            self.rotate("l")

        elif (self.xlast > tower.xlist[-2] - 30):
            self.x += 2
            self.rotate("r")

    def display(self, tower):
        if not tower.is_scrolling():
            pygame.draw.circle(screen, (200, 0, 0), origin, 5, 0)
            screen.blit(self.rotimg, (self.x, self.y))
            if self.state == "ready":
                self.draw_rope()

    def draw_rope(self):
        pygame.draw.aaline(screen, (0, 0, 0), origin, (self.x+32,self.y))
        pygame.draw.aaline(screen, (0, 0, 0), (401,3), (self.x + 33, self.y))
        pygame.draw.aaline(screen, (0, 0, 0), (402,3), (self.x + 34, self.y))
        pygame.draw.aaline(screen, (0, 0, 0), (399,3), (self.x + 31, self.y))
        pygame.draw.aaline(screen, (0, 0, 0), (398,3), (self.x + 30, self.y))
        pygame.draw.circle(screen, (200, 0, 0), (int(self.x+32),int(self.y+2.5)), 5, 0)

    def respawn(self, tower):
        if tower.size%2 ==0:
            self.angle = -45
        else:
            self.angle = 45
        self.y = 150
        self.x = 370
        self.speed = 0
        self.state = "ready"
        global force
        force *= 1.02

class Tower(pygame.sprite.Sprite):
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.size = 0
        self.image = pygame.image.load("assets/block.png")
        self.image2 = pygame.image.load("assets/blockgold.png")
        self.imageMAIN = pygame.image.load("assets/block.png")
        self.rect = self.image.get_rect()
        self.xbase = 0
        self.y = 600
        self.x = 0
        self.height = 0
        self.xlist = []
        self.onscreen = 0
        self.change = 0
        self.speed = 0.4
        self.wobbling = False
        self.scrolling = False
        self.golden = False
        self.redraw = False
        self.display_status = True
        
        # Shaking system
        self.shake_x = 0
        self.shake_y = 0
        self.shake_intensity = 0
        self.shake_timer = 0
        self.base_shake_speed = 8  # How fast the shake oscillates

    def get_display(self):
        return self.display_status

    def is_scrolling(self):
        return self.scrolling

    def is_golden(self):
        return self.golden

    def build(self):
        self.size += 1
        self.onscreen += 1

        if self.size == 1:
            self.xbase = brock.xlast
            self.xlist.append(self.xbase)
        else:
            self.xlist.append(brock.xlast)

        if self.size <= 5:
            self.height = self.size * 64
            self.y = 600 - self.height
        else:
            self.height += 64
            self.y -= 64

    def get_width(self):
        width = 64
        if tower.size == 0 or tower.size == -1:
            return width
        # newblock to the right
        if self.xlist[-1] > self.xbase:
            width = (self.xlist[-1] - self.xbase) + 64
        # new block to the left
        if self.xlist[-1] < self.xbase:
            width = -((self.xbase - self.xlist[-1]) + 64)
        return width

    def draw(self):
        if self.golden == True:
            self.image = self.image2

        if self.redraw == True:
            surf = pygame.Surface((800, self.onscreen*64), pygame.SRCALPHA)
            surf.convert_alpha()
            buildlist = self.xlist[-self.onscreen:]
            for i in range(len(buildlist)):
                surf.blit(self.image, (buildlist[i],self.onscreen*64 - 64*(i+1)))

        elif self.size >= 1:
            surf = pygame.Surface((800, self.onscreen * 64), pygame.SRCALPHA)
            surf.convert_alpha()
            buildlist = self.xlist
            for i in range(len(buildlist)):
                surf.blit(self.image, (buildlist[i], self.onscreen*64 - 64 * (i + 1)))
        else:
             surf = pygame.Surface((0,0))

        self.rect = surf.get_rect()
        return surf

    def unbuild(self, brock):
        self.display_status = False
        if self.y > brock.y:
            brock.y = self.y
            self.size -= 1
        surf = pygame.Surface((800, (self.onscreen-1) * 64), pygame.SRCALPHA)
        surf.convert_alpha()
        buildlist = self.xlist[-self.onscreen:-1]
        for i in range(len(buildlist)):
            surf.blit(self.image, (buildlist[i], (self.onscreen-1) * 64 - 64 * (i + 1)))
        self.rect = surf.get_rect()
        screen.blit(surf, (self.x+self.change, self.y+64))

    def collapse(self, direction):
        self.y += 5
        if direction == "l":
            self.x -=5
        elif direction == "r":
            self.x += 5

    def wobble(self):
        width = self.get_width()
        abs_width = abs(width)
        
        # Determine if tower should be wobbling (existing logic)
        if ((width > 100 or width <-100) and tower.size>=5) or tower.size >=20:
            self.wobbling = True

        if self.wobbling:
            self.change += self.speed

        if self.change > 20:
            self.speed = -0.4
        elif self.change < -20:
            self.speed = 0.4
            
        # Calculate shake intensity based on tower instability
        self.calculate_shake_intensity(abs_width)
        
        # Apply shaking if intensity > 0
        if self.shake_intensity > 0:
            self.update_shake()
    
    def calculate_shake_intensity(self, abs_width):
        """Calculate how much the tower should shake based on instability"""
        # Base shake intensity on tower width deviation and height
        base_intensity = 0
        
        # Light shake: slightly off-center but stable
        if abs_width > 80:
            base_intensity = 1
        
        # Medium shake: moderately unstable
        if abs_width > 120:
            base_intensity = 2
            
        # Heavy shake: very unstable
        if abs_width > 160:
            base_intensity = 3
            
        # Extreme shake: about to collapse
        if abs_width > 200 or self.size >= 18:
            base_intensity = 4
        
        # Increase intensity with tower height
        height_multiplier = min(1.5, 1 + (self.size * 0.05))
        
        self.shake_intensity = int(base_intensity * height_multiplier)
    
    def update_shake(self):
        """Update the shake offset based on intensity"""
        if self.shake_intensity <= 0:
            self.shake_x = 0
            self.shake_y = 0
            return
            
        self.shake_timer += 1
        
        # Different shake patterns based on intensity
        if self.shake_intensity == 1:  # Light shake
            self.shake_x = random.randint(-1, 1)
            self.shake_y = random.randint(-1, 1) if self.shake_timer % 3 == 0 else 0
            
        elif self.shake_intensity == 2:  # Medium shake
            self.shake_x = random.randint(-2, 2)
            self.shake_y = random.randint(-1, 1)
            
        elif self.shake_intensity == 3:  # Heavy shake
            self.shake_x = random.randint(-4, 4)
            self.shake_y = random.randint(-2, 2)
            
        elif self.shake_intensity >= 4:  # Extreme shake
            self.shake_x = random.randint(-6, 6)
            self.shake_y = random.randint(-3, 3)
            # Add some extra violent movements
            if self.shake_timer % 5 == 0:
                self.shake_x += random.choice([-3, 3])
                self.shake_y += random.choice([-2, 2])

    def display(self):
        surf = self.draw()
        # Apply both wobble and shake effects
        final_x = self.x + self.change + self.shake_x
        final_y = self.y + self.shake_y
        screen.blit(surf, (final_x, final_y))

    def scroll(self):
        if self.y <= 440:
            self.y +=5
            self.scrolling = True
        else:
            self.height = 160
            self.scrolling = False
            self.onscreen = 3

    def reset(self):
        self.redraw = True
        if self.onscreen >=7:
            self.onscreen = 3
            self.y = 440
        
        # Reset shake effects when tower resets
        self.shake_x = 0
        self.shake_y = 0
        self.shake_intensity = 0
        self.shake_timer = 0

#START SCREEN
def start_screen():
    title = over_font.render("TOWER BROCKS", True, (0, 0, 0))
    button = mini_font.render("PRESS SPACEBAR TO START", True, (0,0,0))
    controls = mini_font.render("👁️ BLINK TO DROP BLOCKS", True, (0,0,0))
    blank_rect = button.get_rect()
    blank = pygame.Surface((blank_rect.size),pygame.SRCALPHA)
    blank.convert_alpha()
    instructions = [button,blank]
    index = 1
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    waiting = False
            if event.type == BLINK_EVENT:
                if index ==0:
                    index = 1
                else:
                    index = 0

        #starting background
        screen.blit(background, (0, 0))
        screen.blit(title, (150, 150))
        screen.blit(controls, (240, 250))
        screen.blit(instructions[index], (250, 450))
        pygame.display.update()
    return True

#GAME OVER SCREEN
def over_screen():
    over = over_font.render("GAME OVER", True, (0, 0, 0))
    high_score = score_font.render("SCORE: " + str(score_value), True, (0, 0, 0))
    button = mini_font.render("PRESS SPACEBAR TO RESTART", True, (0,0,0))
    blank_rect = button.get_rect()
    blank = pygame.Surface((blank_rect.size),pygame.SRCALPHA)
    blank.convert_alpha()
    instructions = [button,blank]
    index = 1
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    waiting = False
            if event.type == BLINK_EVENT:
                if index ==0:
                    index = 1
                else:
                    index = 0

        #starting background
        screen.blit(background, (0, 0))
        screen.blit(over, (200, 150))
        screen.blit(high_score, (320, 250))
        screen.blit(instructions[index], (250, 450))
        pygame.display.update()
    return True

# Initialize game objects
brock = Block()
tower = Tower()
gameover = False
running = True
clock = pygame.time.Clock()

# Create queues for thread communication
frame_queue = queue.Queue(maxsize=2)  # Small queue to keep latest frames
blink_queue = queue.Queue(maxsize=10)  # Queue for blink events

# Start camera thread
camera_thread = CameraThread(frame_queue, blink_queue)
camera_thread.start()

# Keep track of the last valid frame to prevent flashing
last_frame_surface = None

print("Starting threaded Tower Brocks game...")
print("👁️ Blink to drop blocks!")

# Show start screen
if not start_screen():
    running = False

# -------------------------------
# Main game loop
# -------------------------------
try:
    # --- NEW: Keep track of block's state to clear blinks on change
    previous_state = brock.get_state()
    
    while running:
        clock.tick(60)

        # --- NEW: State Change Detection ---
        # If the block's state has changed, clear any pending blinks
        # to prevent accidental drops in the new state.
        current_state = brock.get_state()
        if current_state != previous_state:
            print(f"State changed: {previous_state} -> {current_state}. Clearing blink queue.")
            while not blink_queue.empty():
                try:
                    blink_queue.get_nowait()
                except queue.Empty:
                    break
            previous_state = current_state

        # Get latest frame from camera thread (non-blocking)
        try:
            latest_frame = frame_queue.get_nowait()
            frame_surface = pygame.surfarray.make_surface(latest_frame)
            frame_surface = pygame.transform.scale(frame_surface, (800, 600))
            last_frame_surface = frame_surface  # Keep track of last valid frame
        except queue.Empty:
            frame_surface = last_frame_surface  # Use last known frame

        # Check for blink events
        blinked = False
        while not blink_queue.empty():
            try:
                blink_queue.get_nowait()  # Get blink event
                blinked = True
                print("👁️ Blink detected!")
            except queue.Empty:
                break  # No more blink events
        
        # Draw webcam feed only (no fallback to default background)
        if frame_surface:
            screen.blit(frame_surface, (0, 0))
        else:
            screen.fill((0, 0, 0))  # Black screen if no camera feed available yet

        # ---- Control system (blink only) ----
        if blinked and brock.get_state() == "ready":
            brock.drop(tower)

        # ---- Game logic (same as before) ----
        if gameover:
            gameover = False
            # NOTE: The blink queue is now cleared automatically by the state-change
            # detector when the state becomes "over" or "miss".
            if not over_screen():
                running = False
                break
            # Reset game objects
            brock = Block()
            tower = Tower()
            force = -0.001
            score_value = 0
            # After reset, state will change from 'over' to 'ready',
            # which will be caught by our detector in the next frame, clearing the queue.
        else:
            show_score(textX, textY)
            
            # --- MODIFIED: Show control mode indicator with hint for clearing blinks
            mode_text = "👁️ Blink Control (Press 'B' to clear blinks)"
            mode_color = (255, 255, 255)
            mode_surface = mini_font.render(mode_text, True, mode_color)
            screen.blit(mode_surface, (10, 550))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # --- NEW: Manual Blink Queue Clearing ---
            # Allow the user to press 'b' to clear any accidental blinks
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_b:
                    print("'b' key pressed. Clearing blink queue.")
                    # Empty the queue
                    while not blink_queue.empty():
                        try:
                            blink_queue.get_nowait()
                        except queue.Empty:
                            break

        if brock.get_state() == "ready":
            brock.swing(tower.size)
        if brock.get_state() == "dropped":
            brock.drop(tower)
        if brock.get_state() == "landed":
            if brock.to_build(tower):
                tower.build()
                if tower.is_golden():
                    gold_build_sound.play()
                    score_value += 2
                else:
                    build_sound.play()
                    score_value += 1
            if tower.size >= 2:
                brock.collapse(tower)
        if brock.get_state() == "over":
            tower.unbuild(brock)
            brock.to_fall(tower)
            fall_sound.play()
            over_music.play()
            gameover = True  # Trigger game over
        
        if brock.get_state() == "miss":
            fall_sound.play()
            over_music.play()
            gameover = True  # Trigger game over
            
        if brock.get_state() == "scroll" and not tower.is_scrolling():
            brock.respawn(tower)
            if tower.size >= 5:
                tower.reset()
        if tower.height >= 64*5 and tower.size >= 5:
            tower.scroll()

        # Display tower + block
        tower.wobble()
        if tower.get_display():
            tower.display()
        brock.display(tower)

        pygame.display.update()

except KeyboardInterrupt:
    print("Game interrupted by user")
    
finally:
    # Clean up
    print("Cleaning up...")
    running = False
    camera_thread.stop()
    camera_thread.join(timeout=2)  # Wait up to 2 seconds for thread to finish
    
    cv2.destroyAllWindows()
    pygame.quit()
    print("Cleanup complete")
