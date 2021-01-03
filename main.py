import pygame
from pygame import mixer
from math import sin, cos

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
        # ready, dropped , landed, scroll ,over
        self.state = "ready"
        self.angle = 45
        #screen.blit(self.image, (self.x, self.y))

    def swing(self):
        self.x = 370 + rope_length * sin(self.angle)
        self.y = 20 + rope_length * cos(self.angle)
        self.angle += self.speed
        self.acceleration = sin(self.angle) * force
        self.speed += self.acceleration
        #print(self.speed)

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

    #positive if towards right, negative if towards left
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
        if ((width > 100 or width <-100) and tower.size>=5) or tower.size >=20:
            self.wobbling = True

        if self.wobbling:
            self.change += self.speed

        if self.change > 20:
            self.speed = -0.4

        elif self.change < -20:
            self.speed = 0.4


    def display(self):
        surf = self.draw()
        screen.blit(surf, (self.x+self.change, self.y))


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


# combo, combo bar , perfect


def over_screen():
    over = over_font.render("GAME OVER", True, (0, 0, 0))
    high_score = score_font.render("SCORE: " + str(tower.size), True, (0, 0, 0))
    button = mini_font.render("PRESS ANY BUTTON TO RESTART", True, (0,0,0))
    blank_rect = button.get_rect()
    blank = pygame.Surface((blank_rect.size),pygame.SRCALPHA)
    blank.convert_alpha()
    instructions = [button,blank]
    index = 1
    waiting = True
    while waiting:
        #clock.tick
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
            if event.type == pygame.KEYUP:
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
        screen.blit(instructions[index], (270, 450))
        pygame.display.update()



brock = Block()
tower = Tower()

gameover = False
running = True

while running:
    clock.tick(120)
    screen.fill((255, 255, 255))

    #background loop
    if screenY < 1200:
        screen.blit(background2, (screenX,screenY-600))
        screen.blit(background,(screenX,screenY))
        screen.blit(background2, (screenX, screenY - 1200))
    else:
        screen.blit(background2, (screenX, screenY - 1800))
        screen.blit(background2,(screenX,screenY-1200))
        if screenY % 600 == 0:
            screenY = 1200

    if gameover:
        gameover = False
        over_screen()
        brock = Block()
        tower = Tower()
        screenY = 0
        force = -0.001
        score_value = 0
    else:
        # score
        show_score(textX, textY)


    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if brock.get_state() == "ready":
                    brock.drop(tower)


    if brock.get_state() == "ready":
        brock.swing()

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

        if tower.size >=2:
            brock.collapse(tower)

    if brock.get_state() == "over":
        tower.unbuild(brock)
        brock.to_fall(tower)
        fall_sound.play()
        over_music.play()

    if brock.get_state() == "scroll" and not tower.is_scrolling():
        brock.respawn(tower)
        if tower.size >=5:
            tower.reset()

    if tower.height >= 64*5 and tower.size >=5:
        tower.scroll()
        screenY +=5


    #standard display
    tower.wobble()
    if tower.get_display() == True:
        tower.display()
    brock.display(tower)

    #game over sequence
    if tower.get_width()<-140:
        tower.collapse("l")
        over_music.play()

    elif tower.get_width()>140:
        tower.collapse("r")
        over_music.play()

    #after tower collapse, block dont respawn
    if tower.y >600:
        brock.x = 2000
        tower.size -= 1
        gameover = True
    #after block collapse, tower dissapear
    elif brock.get_state() == "over" and brock.y > 600:
        tower.y = 2000
        tower.size -= 1
        gameover = True

    elif brock.get_state() == "miss":
        over_music.play()
        tower.y = 2000
        gameover = True


    pygame.display.update()

