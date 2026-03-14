"""
Traffic Chaos Manager
A dynamic traffic simulation game built with Python and Pygame.
Author: Chandana
"""

import pygame
import random
import math
import sys

# ── Init ──────────────────────────────────────────────────────────────────────
pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 900, 700
FPS = 60

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG        = (30,  34,  45)
C_ROAD      = (55,  60,  75)
C_LANE      = (220, 220, 100)
C_SIDEWALK  = (80,  85, 100)
C_WHITE     = (255, 255, 255)
C_RED       = (220,  60,  60)
C_GREEN     = (60,  200,  90)
C_YELLOW    = (240, 200,  40)
C_BLUE      = (60,  140, 220)
C_ORANGE    = (240, 140,  40)
C_CYAN      = (60,  220, 200)
C_PURPLE    = (160,  60, 220)
C_DARK      = (20,  24,  35)
C_PANEL     = (22,  26,  38, 200)
C_RAIN      = (150, 180, 255, 120)

LANE_CENTERS = [220, 330, 440, 550, 660]   # 5 vertical lanes
CAR_COLORS   = [C_RED, C_BLUE, C_ORANGE, C_CYAN, C_PURPLE,
                (200, 80, 120), (80, 200, 120), (200, 160, 60)]

# ── Helpers ───────────────────────────────────────────────────────────────────
def draw_rounded_rect(surf, color, rect, r=10, alpha=None):
    if alpha is not None:
        s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        pygame.draw.rect(s, (*color[:3], alpha), (0, 0, rect[2], rect[3]), border_radius=r)
        surf.blit(s, (rect[0], rect[1]))
    else:
        pygame.draw.rect(surf, color, rect, border_radius=r)

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

# ── Rain System ───────────────────────────────────────────────────────────────
class RainDrop:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(-HEIGHT, 0)
        self.speed = random.uniform(8, 16)
        self.length = random.randint(10, 22)
        self.alpha = random.randint(60, 160)

    def update(self):
        self.y += self.speed
        self.x += 1.5                       # slight diagonal
        if self.y > HEIGHT:
            self.reset()

    def draw(self, surf):
        s = pygame.Surface((4, self.length), pygame.SRCALPHA)
        pygame.draw.line(s, (*C_RAIN[:3], self.alpha), (0, 0), (2, self.length), 1)
        surf.blit(s, (int(self.x), int(self.y)))

# ── Traffic Light ─────────────────────────────────────────────────────────────
class TrafficLight:
    CYCLE = [("red", C_RED, 180), ("green", C_GREEN, 160), ("yellow", C_YELLOW, 50)]

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.state_idx = 0
        self.timer = 0
        self.state, self.color, self.duration = self.CYCLE[0]

    def update(self):
        self.timer += 1
        if self.timer >= self.duration:
            self.timer = 0
            self.state_idx = (self.state_idx + 1) % len(self.CYCLE)
            self.state, self.color, self.duration = self.CYCLE[self.state_idx]

    def draw(self, surf):
        bx, by = self.x - 14, self.y - 40
        pygame.draw.rect(surf, (40, 42, 55), (bx, by, 28, 70), border_radius=6)
        for i, (_, col, _) in enumerate(self.CYCLE):
            active = (i == self.state_idx)
            c = col if active else tuple(max(0, v-130) for v in col)
            pygame.draw.circle(surf, c, (self.x, by + 14 + i*22), 8)
        # post
        pygame.draw.rect(surf, (70, 72, 85), (self.x-3, by+70, 6, 30))

    @property
    def is_red(self):
        return self.state == "red"

# ── Vehicle ───────────────────────────────────────────────────────────────────
class Vehicle:
    def __init__(self, lane_idx, going_down=True, speed=None, player=False):
        self.lane_idx = lane_idx
        self.x = LANE_CENTERS[lane_idx]
        self.going_down = going_down
        self.player = player
        self.color = C_GREEN if player else random.choice(CAR_COLORS)
        self.width = 36
        self.height = 60
        self.base_speed = speed or random.uniform(2.5, 5.0)
        self.speed = self.base_speed
        self.y = HEIGHT // 2 if player else (-self.height - random.randint(0, 300)
                                              if going_down else HEIGHT + random.randint(0, 300))
        self.alive = True
        self.brake = False
        self.honk_timer = 0
        self.score_given = False
        # visual
        self.wheel_rot = 0
        self.damage = 0             # 0-100

    @property
    def rect(self):
        return pygame.Rect(self.x - self.width//2, self.y - self.height//2,
                           self.width, self.height)

    def update(self, traffic_light, all_vehicles, weather_slow, difficulty):
        if self.player:
            return

        effective_speed = self.base_speed * difficulty * (0.6 if weather_slow else 1.0)

        # brake near red light (only down-going cars in top half)
        stop_y = traffic_light.y + 60
        near_light = self.going_down and self.y < stop_y and self.y > stop_y - 180

        if near_light and traffic_light.is_red:
            # decelerate
            self.speed = max(0, self.speed - 0.15)
        else:
            self.speed = min(effective_speed, self.speed + 0.1)

        # basic follow logic – slow if vehicle ahead is close
        for v in all_vehicles:
            if v is self or not v.alive:
                continue
            if v.lane_idx == self.lane_idx and v.going_down == self.going_down:
                gap = (v.y - self.y) if self.going_down else (self.y - v.y)
                if 0 < gap < self.height + 30:
                    self.speed = max(0, min(self.speed, v.speed - 0.1))

        move = self.speed if self.going_down else -self.speed
        self.y += move
        self.wheel_rot = (self.wheel_rot + self.speed * 3) % 360

        # out of screen
        if self.going_down and self.y > HEIGHT + self.height + 10:
            self.alive = False
        if not self.going_down and self.y < -self.height - 10:
            self.alive = False

    def draw(self, surf):
        x, y = self.x, self.y
        w, h = self.width, self.height
        col = self.color

        # body shadow
        s = pygame.Surface((w+6, h+6), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, 60), (0, 0, w+6, h+6), border_radius=10)
        surf.blit(s, (x - w//2 - 2, y - h//2 + 4))

        # body
        pygame.draw.rect(surf, col, (x-w//2, y-h//2, w, h), border_radius=9)

        # roof
        roof_col = lerp_color(col, (255,255,255), 0.2)
        pygame.draw.rect(surf, roof_col, (x-w//2+5, y-h//2+12, w-10, h-28), border_radius=6)

        # windshield
        wshield = (0, 100, 200, 140) if not self.player else (100, 220, 255, 160)
        ws = pygame.Surface((w-14, 16), pygame.SRCALPHA)
        pygame.draw.rect(ws, wshield, (0, 0, w-14, 16), border_radius=4)
        surf.blit(ws, (x-w//2+7, y-h//2+14 if self.going_down else y+h//2-30))

        # headlights / taillights
        light_y = y - h//2 + 5 if self.going_down else y + h//2 - 10
        light_col = (255, 255, 180) if self.going_down else (200, 40, 40)
        pygame.draw.circle(surf, light_col, (x-w//2+6, light_y), 5)
        pygame.draw.circle(surf, light_col, (x+w//2-6, light_y), 5)

        # wheels
        for wx_off, wy_off in [(-w//2-2, -h//2+10), (w//2+2, -h//2+10),
                                (-w//2-2,  h//2-10), (w//2+2,  h//2-10)]:
            pygame.draw.ellipse(surf, (25, 25, 30), (x+wx_off-5, y+wy_off-6, 10, 12))
            pygame.draw.circle(surf, (80, 80, 90), (x+wx_off, y+wy_off), 4)

        # player glow
        if self.player:
            glow = pygame.Surface((w+20, h+20), pygame.SRCALPHA)
            pygame.draw.rect(glow, (60, 255, 120, 30), (0, 0, w+20, h+20), border_radius=14)
            surf.blit(glow, (x-w//2-10, y-h//2-10))

        # damage tint
        if self.damage > 0:
            dmg_s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(dmg_s, (255, 60, 60, min(200, self.damage*2)),
                             (0, 0, w, h), border_radius=9)
            surf.blit(dmg_s, (x-w//2, y-h//2))

# ── Obstacle ──────────────────────────────────────────────────────────────────
class Obstacle:
    TYPES = ["cone", "pothole", "barrier"]

    def __init__(self):
        self.type = random.choice(self.TYPES)
        self.lane = random.randint(0, len(LANE_CENTERS)-1)
        self.x = LANE_CENTERS[self.lane]
        self.y = random.randint(80, HEIGHT - 100)
        self.alive = True
        self.pulse = 0

    def update(self):
        self.pulse = (self.pulse + 3) % 360

    def draw(self, surf):
        x, y = self.x, self.y
        glow = abs(math.sin(math.radians(self.pulse))) * 0.5 + 0.5

        if self.type == "cone":
            # orange traffic cone
            pts = [(x, y-18), (x-10, y+12), (x+10, y+12)]
            pygame.draw.polygon(surf, C_ORANGE, pts)
            pygame.draw.line(surf, C_WHITE, (x-7, y+2), (x+7, y+2), 2)
            pygame.draw.line(surf, C_WHITE, (x-4, y-8), (x+4, y-8), 2)
        elif self.type == "pothole":
            col = lerp_color((60,55,70), (100,90,110), glow)
            pygame.draw.ellipse(surf, col, (x-16, y-10, 32, 20))
            pygame.draw.ellipse(surf, (40,38,50), (x-12, y-7, 24, 14))
        elif self.type == "barrier":
            c = lerp_color(C_RED, C_YELLOW, glow)
            pygame.draw.rect(surf, c, (x-22, y-8, 44, 16), border_radius=4)
            pygame.draw.rect(surf, C_WHITE, (x-6, y-8, 12, 16))

    @property
    def rect(self):
        return pygame.Rect(self.x-16, self.y-16, 32, 32)

# ── Particle ──────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.color = color
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-6, 1)
        self.life = random.randint(20, 45)
        self.max_life = self.life
        self.size = random.randint(3, 8)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.2
        self.life -= 1

    def draw(self, surf):
        alpha = int(255 * self.life / self.max_life)
        s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.size, self.size), self.size)
        surf.blit(s, (int(self.x)-self.size, int(self.y)-self.size))

# ── HUD ───────────────────────────────────────────────────────────────────────
def draw_hud(surf, score, lives, level, weather_on, combo, player):
    font_big   = pygame.font.SysFont("consolas", 28, bold=True)
    font_med   = pygame.font.SysFont("consolas", 20, bold=True)
    font_small = pygame.font.SysFont("consolas", 15)

    # Left panel
    draw_rounded_rect(surf, C_PANEL[:3], (10, 10, 200, 150), r=12, alpha=180)
    surf.blit(font_big.render(f"SCORE", True, C_CYAN), (22, 18))
    surf.blit(font_big.render(f"{score:06d}", True, C_WHITE), (22, 44))
    surf.blit(font_med.render(f"LEVEL {level}", True, C_YELLOW), (22, 80))
    hearts = "♥ " * lives + "♡ " * (3 - lives)
    surf.blit(font_med.render(hearts, True, C_RED), (22, 108))
    if combo > 1:
        surf.blit(font_med.render(f"x{combo} COMBO!", True, C_ORANGE), (22, 134))

    # Weather badge
    if weather_on:
        draw_rounded_rect(surf, (30, 60, 120), (WIDTH-130, 10, 120, 40), r=8, alpha=200)
        surf.blit(font_med.render("🌧 RAIN", True, C_RAIN[:3]), (WIDTH-122, 18))

    # Speed bar
    spd = int(player.speed * 18)
    pygame.draw.rect(surf, (40, 44, 60), (WIDTH-130, 60, 120, 14), border_radius=7)
    bar_col = lerp_color(C_GREEN, C_RED, min(1, player.speed / 12))
    pygame.draw.rect(surf, bar_col, (WIDTH-130, 60, min(120, spd), 14), border_radius=7)
    surf.blit(font_small.render("SPEED", True, (160, 160, 180)), (WIDTH-130, 78))

    # Controls hint (bottom)
    hint = "ARROWS/WASD: Move   R: Restart   Q: Quit"
    surf.blit(font_small.render(hint, True, (100, 105, 130)), (WIDTH//2 - 170, HEIGHT - 24))

# ── Road Drawing ──────────────────────────────────────────────────────────────
def draw_road(surf, tick):
    surf.fill(C_BG)

    # Sidewalks
    pygame.draw.rect(surf, C_SIDEWALK, (0, 0, 160, HEIGHT))
    pygame.draw.rect(surf, C_SIDEWALK, (WIDTH-160, 0, 160, HEIGHT))

    # Road surface
    pygame.draw.rect(surf, C_ROAD, (160, 0, WIDTH-320, HEIGHT))

    # Lane dividers (dashed, animated)
    dash_h = 40
    gap = 30
    total = dash_h + gap
    for lane in range(1, len(LANE_CENTERS)):
        lx = (LANE_CENTERS[lane-1] + LANE_CENTERS[lane]) // 2
        offset = tick % total
        y = -total + offset
        while y < HEIGHT:
            pygame.draw.rect(surf, C_LANE, (lx-2, y, 4, dash_h), border_radius=2)
            y += total

    # Edge lines
    pygame.draw.rect(surf, C_WHITE, (160, 0, 4, HEIGHT))
    pygame.draw.rect(surf, C_WHITE, (WIDTH-164, 0, 4, HEIGHT))

    # Center double yellow
    cx = WIDTH // 2
    pygame.draw.rect(surf, C_YELLOW, (cx-6, 0, 3, HEIGHT))
    pygame.draw.rect(surf, C_YELLOW, (cx+3, 0, 3, HEIGHT))

# ── Screens ───────────────────────────────────────────────────────────────────
def draw_start_screen(surf):
    font_title = pygame.font.SysFont("consolas", 54, bold=True)
    font_sub   = pygame.font.SysFont("consolas", 22)
    font_small = pygame.font.SysFont("consolas", 17)

    surf.fill(C_DARK)
    # animated road stripes
    t = pygame.time.get_ticks() // 20
    for i in range(0, HEIGHT, 60):
        y = (i + t) % HEIGHT
        pygame.draw.rect(surf, (45, 48, 62), (WIDTH//2-4, y, 8, 35), border_radius=3)

    draw_rounded_rect(surf, (25, 28, 42), (WIDTH//2-280, HEIGHT//2-170, 560, 340), r=20, alpha=230)

    # Title
    title = font_title.render("TRAFFIC CHAOS", True, C_CYAN)
    manager = font_title.render("MANAGER", True, C_YELLOW)
    surf.blit(title, title.get_rect(center=(WIDTH//2, HEIGHT//2-110)))
    surf.blit(manager, manager.get_rect(center=(WIDTH//2, HEIGHT//2-55)))

    lines = [
        ("Navigate through 5 lanes of chaos!", C_WHITE),
        ("Avoid vehicles & obstacles.", (180, 180, 200)),
        ("Survive rain, speed & rising difficulty.", (180, 180, 200)),
        ("", None),
        ("Press  SPACE  to Start", C_GREEN),
        ("Q to Quit", (140, 140, 160)),
    ]
    y0 = HEIGHT//2
    for txt, col in lines:
        if col:
            s = font_sub.render(txt, True, col)
            surf.blit(s, s.get_rect(center=(WIDTH//2, y0)))
        y0 += 32

def draw_game_over(surf, score, level):
    font_big   = pygame.font.SysFont("consolas", 52, bold=True)
    font_med   = pygame.font.SysFont("consolas", 26)
    font_small = pygame.font.SysFont("consolas", 20)

    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ov.fill((10, 12, 22, 200))
    surf.blit(ov, (0, 0))

    draw_rounded_rect(surf, (30, 34, 50), (WIDTH//2-220, HEIGHT//2-160, 440, 320), r=18, alpha=240)

    surf.blit(font_big.render("GAME OVER", True, C_RED),
              font_big.render("GAME OVER", True, C_RED).get_rect(center=(WIDTH//2, HEIGHT//2-110)))
    surf.blit(font_med.render(f"Score: {score:06d}", True, C_WHITE),
              font_med.render(f"Score: {score:06d}", True, C_WHITE).get_rect(center=(WIDTH//2, HEIGHT//2-50)))
    surf.blit(font_med.render(f"Level Reached: {level}", True, C_YELLOW),
              font_med.render(f"Level Reached: {level}", True, C_YELLOW).get_rect(center=(WIDTH//2, HEIGHT//2)))
    surf.blit(font_small.render("Press R to Restart  |  Q to Quit", True, (160, 165, 185)),
              font_small.render("Press R to Restart  |  Q to Quit", True, (160, 165, 185)).get_rect(center=(WIDTH//2, HEIGHT//2+80)))

# ── Main Game ─────────────────────────────────────────────────────────────────
def run_game():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Traffic Chaos Manager")
    clock = pygame.time.Clock()

    # ── State ──
    STATE_START    = 0
    STATE_PLAYING  = 1
    STATE_GAMEOVER = 2
    state = STATE_START

    def init_game():
        nonlocal player, vehicles, obstacles, particles, raindrops
        nonlocal score, lives, level, tick, difficulty, weather_on
        nonlocal spawn_timer, obstacle_timer, weather_timer, level_timer
        nonlocal combo, last_pass_y

        player = Vehicle(lane_idx=2, going_down=False, player=True)
        player.speed = 0
        player.y = HEIGHT - 100
        vehicles = []
        obstacles = []
        particles = []
        raindrops = [RainDrop() for _ in range(220)]

        score = 0
        lives = 3
        level = 1
        tick = 0
        difficulty = 1.0
        weather_on = False
        spawn_timer = 0
        obstacle_timer = 0
        weather_timer = random.randint(600, 1200)
        level_timer = 0
        combo = 0
        last_pass_y = {}    # lane_idx -> last y that passed player

    player = vehicles = obstacles = particles = raindrops = None
    score = lives = level = tick = difficulty = 0
    weather_on = False
    spawn_timer = obstacle_timer = weather_timer = level_timer = combo = 0
    last_pass_y = {}

    init_game()

    traffic_light = TrafficLight(WIDTH // 2, HEIGHT // 2 - 80)

    # ── Main Loop ──────────────────────────────────────────────────────────────
    running = True
    while running:
        dt = clock.tick(FPS)

        # ── Events ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                if state == STATE_START and event.key == pygame.K_SPACE:
                    state = STATE_PLAYING
                if state == STATE_GAMEOVER and event.key == pygame.K_r:
                    init_game()
                    state = STATE_PLAYING
                if state == STATE_PLAYING and event.key == pygame.K_r:
                    init_game()

        # ── Start Screen ──
        if state == STATE_START:
            draw_start_screen(screen)
            pygame.display.flip()
            continue

        # ── Game Over Screen ──
        if state == STATE_GAMEOVER:
            draw_road(screen, tick)
            draw_game_over(screen, score, level)
            pygame.display.flip()
            continue

        # ─────────────────────────────────────────────────────────────────────
        # ── PLAYING ──────────────────────────────────────────────────────────
        tick += 1

        # Player movement
        keys = pygame.key.get_pressed()
        move_speed = 5.0 * (0.7 if weather_on else 1.0)

        if keys[pygame.K_LEFT]  or keys[pygame.K_a]:
            player.x = max(LANE_CENTERS[0] - 20, player.x - move_speed)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            player.x = min(LANE_CENTERS[-1] + 20, player.x + move_speed)
        if keys[pygame.K_UP]    or keys[pygame.K_w]:
            player.y = max(80, player.y - move_speed)
            player.speed = move_speed
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]:
            player.y = min(HEIGHT - 60, player.y + move_speed)
            player.speed = max(0, move_speed * 0.5)

        # snap to nearest lane gradually
        nearest_lane = min(LANE_CENTERS, key=lambda lx: abs(lx - player.x))
        if not (keys[pygame.K_LEFT] or keys[pygame.K_a] or
                keys[pygame.K_RIGHT] or keys[pygame.K_d]):
            player.x += (nearest_lane - player.x) * 0.15

        # ── Level progression ──
        level_timer += 1
        if level_timer > 1800:          # every 30s
            level_timer = 0
            level += 1
            difficulty = 1.0 + (level-1) * 0.18
            # bonus
            score += 500 * level
            for _ in range(20):
                particles.append(Particle(player.x, player.y, C_YELLOW))

        # ── Weather toggle ──
        weather_timer -= 1
        if weather_timer <= 0:
            weather_on = not weather_on
            weather_timer = random.randint(400, 900)

        # ── Traffic light ──
        traffic_light.update()

        # ── Spawn vehicles ──
        spawn_timer += 1
        spawn_interval = max(25, int(70 / difficulty))
        if spawn_timer >= spawn_interval:
            spawn_timer = 0
            lane = random.randint(0, len(LANE_CENTERS)-1)
            going_down = random.random() < 0.6
            spd = random.uniform(2.0, 4.5) * difficulty * (0.65 if weather_on else 1.0)
            vehicles.append(Vehicle(lane, going_down, spd))

        # ── Spawn obstacles ──
        obstacle_timer += 1
        obs_interval = max(120, int(300 - level*15))
        if obstacle_timer >= obs_interval:
            obstacle_timer = 0
            if len(obstacles) < 8:
                obstacles.append(Obstacle())

        # ── Update vehicles ──
        for v in vehicles[:]:
            v.update(traffic_light, vehicles, weather_on, difficulty)
            if not v.alive:
                vehicles.remove(v)
                if not v.score_given:
                    score += 10

        # ── Score: vehicles player dodges ──
        for v in vehicles:
            if v.going_down and not v.player:
                if v.y > player.y and not v.score_given:
                    v.score_given = True
                    score += 50 * level
                    combo += 1
                    for _ in range(8):
                        particles.append(Particle(player.x, player.y-30, C_GREEN))

        # ── Collision: player vs vehicles ──
        pr = player.rect
        for v in vehicles:
            if not v.player and v.rect.colliderect(pr):
                lives -= 1
                player.damage = min(100, player.damage + 40)
                combo = 0
                for _ in range(25):
                    particles.append(Particle(player.x, player.y, C_RED))
                # push vehicles apart briefly
                v.y += 40 if v.going_down else -40
                if lives <= 0:
                    state = STATE_GAMEOVER

        # ── Collision: player vs obstacles ──
        for obs in obstacles[:]:
            if obs.rect.colliderect(pr):
                lives -= 1
                combo = 0
                obs.alive = False
                for _ in range(20):
                    particles.append(Particle(obs.x, obs.y, C_ORANGE))
                if lives <= 0:
                    state = STATE_GAMEOVER

        obstacles = [o for o in obstacles if o.alive]

        # ── Update obstacles & particles ──
        for obs in obstacles:
            obs.update()
        for p in particles[:]:
            p.update()
            if p.life <= 0:
                particles.remove(p)

        # Recover damage slowly
        if player.damage > 0:
            player.damage = max(0, player.damage - 0.3)

        # Passive score
        score += 1

        # ─────────────────────────────────────────────────────────────────────
        # ── Draw ─────────────────────────────────────────────────────────────
        draw_road(screen, tick)

        # Obstacles (behind vehicles)
        for obs in obstacles:
            obs.draw(screen)

        # Vehicles
        for v in sorted(vehicles, key=lambda v: v.y):
            v.draw(screen)

        # Player
        player.draw(screen)

        # Particles
        for p in particles:
            p.draw(screen)

        # Rain overlay
        if weather_on:
            for rd in raindrops:
                rd.update()
                rd.draw(screen)

        # Traffic light
        traffic_light.draw(screen)

        # HUD
        draw_hud(screen, score, lives, level, weather_on, combo, player)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    run_game()