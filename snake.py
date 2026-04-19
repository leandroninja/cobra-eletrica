import pygame
import sys
import json
import os
import math
import array
from random import randint, uniform, choice
from dataclasses import dataclass
from collections import deque

SR = 44100

def _eletrica_zap(vol=0.38):
    """Sawtooth elétrico curto e agressivo."""
    dur = 0.07
    n   = int(SR * dur)
    buf = array.array('h', [0] * (n * 2))
    for i in range(n):
        t    = i / SR
        env  = (1.0 - i / n) ** 0.6
        freq = 520
        saw  = 2 * ((freq * t) % 1) - 1
        val  = int(32767 * vol * env * saw)
        buf[2*i] = val; buf[2*i+1] = val
    return pygame.mixer.Sound(buffer=buf)

def _eletrica_dourada(vol=0.4):
    """Sweep ascendente elétrico para maçã dourada."""
    dur = 0.18
    n   = int(SR * dur)
    buf = array.array('h', [0] * (n * 2))
    for i in range(n):
        t    = i / SR
        freq = 300 + 900 * (i / n)
        env  = 1.0 - (i / n) ** 0.8
        saw  = 2 * ((freq * t) % 1) - 1
        val  = int(32767 * vol * env * saw)
        buf[2*i] = val; buf[2*i+1] = val
    return pygame.mixer.Sound(buffer=buf)

def _eletrica_morte(vol=0.45):
    """Descarga elétrica decrescente — sawtooth + ruído."""
    dur = 0.55
    n   = int(SR * dur)
    buf = array.array('h', [0] * (n * 2))
    import random as _rnd
    for i in range(n):
        t    = i / SR
        freq = 350 * math.exp(-4 * t)
        env  = (1.0 - i / n) ** 0.5
        saw  = 2 * ((freq * t) % 1) - 1
        noise = _rnd.uniform(-0.3, 0.3)
        val  = int(32767 * vol * env * (saw * 0.7 + noise * 0.3))
        buf[2*i] = val; buf[2*i+1] = val
    return pygame.mixer.Sound(buffer=buf)

def _eletrica_musica(vol=0.18):
    """Melodia elétrica/energética em loop — sawtooth com ritmo acelerado."""
    bpm  = 145
    beat = 60 / bpm
    h    = beat / 2
    q    = beat / 4
    e    = beat / 8
    mel = [
        (880, q), (0, e), (880, e), (1047, q), (988, q),
        (880, h), (784, q), (0, q),
        (784, q), (0, e), (784, e), (880, q), (784, q),
        (659, h), (0, h),
        (988, q), (0, e), (988, e), (1175, q), (1047, q),
        (988, h), (880, q), (0, q),
        (784, q), (659, q), (784, q), (880, q),
        (784, beat), (0, beat),
    ]
    bass_notas = [110, 110, 131, 131, 98, 98, 131, 131,
                  110, 110, 131, 131, 98, 98, 110, 110]
    bass_dur   = h
    total_mel  = sum(d for _, d in mel)
    total_bass = bass_dur * len(bass_notas)
    total      = max(total_mel, total_bass)
    n          = int(total * SR)
    buf        = array.array('h', [0] * (n * 2))
    pos = 0
    for freq, dur in mel:
        samp = int(dur * SR)
        for i in range(samp):
            if freq > 0 and pos + i < n:
                t   = i / SR
                env = math.exp(-2.5 * t / dur)
                saw = 2 * ((freq * t) % 1) - 1
                v   = int(32767 * vol * 0.75 * env * saw)
                buf[2*(pos+i)]   = max(-32767, min(32767, buf[2*(pos+i)]   + v))
                buf[2*(pos+i)+1] = max(-32767, min(32767, buf[2*(pos+i)+1] + v))
        pos += samp
    pos = 0
    for freq in bass_notas:
        samp = int(bass_dur * SR)
        for i in range(samp):
            if pos + i < n:
                t   = i / SR
                env = 0.5 + 0.5 * math.exp(-5 * t / bass_dur)
                saw = 2 * ((freq * t) % 1) - 1
                v   = int(32767 * vol * 0.55 * env * saw)
                buf[2*(pos+i)]   = max(-32767, min(32767, buf[2*(pos+i)]   + v))
                buf[2*(pos+i)+1] = max(-32767, min(32767, buf[2*(pos+i)+1] + v))
        pos += samp
    return pygame.mixer.Sound(buffer=buf)


pygame.init()
pygame.mixer.init()

# ── Constantes ────────────────────────────────────────────────────────────────
CELL     = 20
COLS     = 30
ROWS     = 30
GRID_W   = COLS * CELL    # 600
GRID_H   = ROWS * CELL    # 600
PANEL_W  = 200
SCREEN_W = GRID_W + PANEL_W
SCREEN_H = GRID_H
FPS      = 60

HIGHSCORE_FILE = "highscore.json"

# Cores
BG       = ( 13,  13,  23)
GRID_C   = ( 22,  22,  38)
HEAD_C   = ( 60, 255, 110)
BODY_TOP = ( 45, 200,  80)
BODY_BOT = ( 18,  85,  38)
FOOD_C   = (255,  55,  60)
GOLD_C   = (255, 215,  45)
WHITE    = (255, 255, 255)
BLACK    = (  0,   0,   0)
YELLOW   = (255, 215,  45)
RED      = (220,  50,  50)
ORANGE   = (255, 150,   0)
GRAY     = (140, 140, 160)
PANEL_BG = ( 18,  18,  32)
GREEN    = ( 60, 210,  80)

# Direções
UP    = ( 0, -1)
DOWN  = ( 0,  1)
LEFT  = (-1,  0)
RIGHT = ( 1,  0)

SPEED_INIT   = 8    # moves/segundo no início
SPEED_MAX    = 22
SPEED_STEP   = 5    # pontos para subir nível
GOLDEN_EVERY = 7    # a cada N maçãs normais aparece uma dourada

# ── Highscore ─────────────────────────────────────────────────────────────────
def load_highscore():
    if os.path.exists(HIGHSCORE_FILE):
        try:
            with open(HIGHSCORE_FILE) as f:
                return json.load(f).get("highscore", 0)
        except Exception:
            pass
    return 0

def save_highscore(score):
    with open(HIGHSCORE_FILE, "w") as f:
        json.dump({"highscore": score}, f)

# ── Partícula ─────────────────────────────────────────────────────────────────
@dataclass
class Particle:
    x: float; y: float
    vx: float; vy: float
    life: int; max_life: int
    color: tuple; size: float

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.28
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        r = max(1, int(self.size * self.life / self.max_life))
        a = int(255 * self.life / self.max_life)
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (r, r), r)
        surf.blit(s, (int(self.x) - r, int(self.y) - r))

def spawn_particles(particles, gx, gy, color, count=22):
    cx = gx * CELL + CELL // 2
    cy = gy * CELL + CELL // 2
    for _ in range(count):
        spd = uniform(2.0, 7.5)
        life = randint(16, 38)
        particles.append(Particle(
            cx, cy,
            uniform(-spd, spd), uniform(-spd, 0.5),
            life, life, color, uniform(3, 7)
        ))

# ── Comida ────────────────────────────────────────────────────────────────────
class Food:
    def __init__(self, occupied, golden=False):
        self.golden = golden
        self.pos    = self._spawn(occupied)
        self.pulse  = uniform(0, math.pi * 2)

    def _spawn(self, occupied):
        while True:
            pos = (randint(0, COLS - 1), randint(0, ROWS - 1))
            if pos not in occupied:
                return pos

    def update(self):
        self.pulse = (self.pulse + 0.07) % (math.pi * 2)

    def draw(self, surf):
        gx, gy = self.pos
        cx = gx * CELL + CELL // 2
        cy = gy * CELL + CELL // 2
        color = GOLD_C if self.golden else FOOD_C
        radius = max(4, int(CELL // 2 - 2 + 2 * abs(math.sin(self.pulse))))

        # Brilho externo (glow)
        for dr in (13, 10, 7):
            a = 25 + (13 - dr) * 8
            gs = pygame.Surface((dr * 2, dr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*color, a), (dr, dr), dr)
            surf.blit(gs, (cx - dr, cy - dr))

        # Círculo principal
        pygame.draw.circle(surf, color, (cx, cy), radius)
        # Reflexo
        pygame.draw.circle(surf, WHITE, (cx - 3, cy - 3), 3)

        # Coroa para maçã dourada
        if self.golden:
            pygame.draw.circle(surf, WHITE, (cx, cy), radius + 2, 1)

# ── Cobra (desenho) ───────────────────────────────────────────────────────────
def draw_snake(surf, segments, direction):
    if not segments:
        return
    n = len(segments)
    for i, (gx, gy) in enumerate(segments):
        px = gx * CELL
        py = gy * CELL
        t = i / max(1, n - 1)
        r = int(BODY_TOP[0] + (BODY_BOT[0] - BODY_TOP[0]) * t)
        g = int(BODY_TOP[1] + (BODY_BOT[1] - BODY_TOP[1]) * t)
        b = int(BODY_TOP[2] + (BODY_BOT[2] - BODY_TOP[2]) * t)
        color  = HEAD_C if i == 0 else (r, g, b)
        margin = 1 if i == 0 else 2
        radius = 6 if i == 0 else 4
        rect   = pygame.Rect(px + margin, py + margin,
                             CELL - margin * 2, CELL - margin * 2)
        pygame.draw.rect(surf, color, rect, border_radius=radius)

        # Olhos na cabeça
        if i == 0:
            cx = px + CELL // 2
            cy = py + CELL // 2
            if   direction == RIGHT: e1, e2 = (cx + 5, cy - 4), (cx + 5, cy + 4)
            elif direction == LEFT:  e1, e2 = (cx - 5, cy - 4), (cx - 5, cy + 4)
            elif direction == UP:    e1, e2 = (cx - 4, cy - 5), (cx + 4, cy - 5)
            else:                    e1, e2 = (cx - 4, cy + 5), (cx + 4, cy + 5)
            for eye in (e1, e2):
                pygame.draw.circle(surf, WHITE, eye, 3)
                pygame.draw.circle(surf, BLACK, eye, 1)

# ── Texto com sombra ──────────────────────────────────────────────────────────
def draw_text(surf, text, font, color, x, y, center=False):
    shadow = font.render(text, True, BLACK)
    main   = font.render(text, True, color)
    rect   = main.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surf.blit(shadow, rect.move(2, 2))
    surf.blit(main,   rect)

# ── Painel lateral ────────────────────────────────────────────────────────────
def draw_panel(surf, fonts, score, highscore, level):
    px = GRID_W
    pygame.draw.rect(surf, PANEL_BG, (px, 0, PANEL_W, SCREEN_H))
    pygame.draw.line(surf, (40, 40, 65), (px, 0), (px, SCREEN_H), 2)

    f_xl, f_lg, f_md, f_sm = fonts
    mid = px + PANEL_W // 2

    draw_text(surf, "COBRA ELÉTRICA", f_lg, HEAD_C,  mid, 48,  center=True)
    pygame.draw.line(surf, (40, 40, 65), (px + 15, 75), (px + PANEL_W - 15, 75))

    draw_text(surf, "PONTOS",      f_sm, GRAY,    mid, 95,  center=True)
    draw_text(surf, str(score),    f_xl, WHITE,   mid, 130, center=True)
    pygame.draw.line(surf, (40, 40, 65), (px + 15, 170), (px + PANEL_W - 15, 170))

    draw_text(surf, "RECORDE",     f_sm, GRAY,    mid, 188, center=True)
    draw_text(surf, str(highscore),f_md, YELLOW,  mid, 215, center=True)
    pygame.draw.line(surf, (40, 40, 65), (px + 15, 248), (px + PANEL_W - 15, 248))

    draw_text(surf, "NIVEL",       f_sm, GRAY,    mid, 266, center=True)
    draw_text(surf, str(level),    f_md, ORANGE,  mid, 292, center=True)
    pygame.draw.line(surf, (40, 40, 65), (px + 15, 328), (px + PANEL_W - 15, 328))

    draw_text(surf, "Setas: mover", f_sm, GRAY, mid, 348, center=True)
    draw_text(surf, "ESC: pausar",  f_sm, GRAY, mid, 370, center=True)
    draw_text(surf, "Q: menu",      f_sm, GRAY, mid, 392, center=True)
    pygame.draw.line(surf, (40, 40, 65), (px + 15, 420), (px + PANEL_W - 15, 420))

    # Legenda maçã dourada
    pygame.draw.circle(surf, GOLD_C, (px + 28, 448), 8)
    pygame.draw.circle(surf, WHITE,  (px + 25, 445), 2)
    draw_text(surf, "= 3 pontos", f_sm, GOLD_C, px + 42, 441)

# ── Jogo ──────────────────────────────────────────────────────────────────────
class Game:
    MENU      = "menu"
    PLAYING   = "playing"
    PAUSED    = "paused"
    GAME_OVER = "over"

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Cobra Elétrica")
        self.clock  = pygame.time.Clock()
        self._load_assets()
        self.highscore = load_highscore()
        self.state     = self.MENU
        self._init_game()
        self._init_menu_snake()

    def _load_assets(self):
        try:
            pygame.mixer.init(frequency=SR, size=-16, channels=2, buffer=512)
            self.musica = _eletrica_musica()
            self.musica.play(-1)
        except Exception:
            pass
        try:
            pygame.mixer.init(frequency=SR, size=-16, channels=2, buffer=512)
            self.snd_eat    = _eletrica_zap(0.38)
            self.snd_dourado = _eletrica_dourada(0.4)
            self.snd_morte  = _eletrica_morte(0.45)
        except Exception:
            self.snd_eat = self.snd_dourado = self.snd_morte = None

        self.overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        self.fonts = (
            pygame.font.SysFont("Arial Black", 52, bold=True),
            pygame.font.SysFont("Arial Black", 32, bold=True),
            pygame.font.SysFont("Arial Black", 22, bold=True),
            pygame.font.SysFont("Arial",        15),
        )

        # Grid pré-renderizada (performance)
        self.bg_surf = pygame.Surface((GRID_W, GRID_H))
        self.bg_surf.fill(BG)
        for x in range(0, GRID_W + 1, CELL):
            pygame.draw.line(self.bg_surf, GRID_C, (x, 0), (x, GRID_H))
        for y in range(0, GRID_H + 1, CELL):
            pygame.draw.line(self.bg_surf, GRID_C, (0, y), (GRID_W, y))

    def _init_game(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake       = deque([(cx, cy), (cx - 1, cy), (cx - 2, cy)])
        self.direction   = RIGHT
        self.next_dir    = RIGHT
        self.score       = 0
        self.food_count  = 0
        self.particles   = []
        self.move_timer  = 0
        self.flash       = 0   # frames de flash vermelho no game over
        occupied = set(self.snake)
        self.food        = Food(occupied)
        self.golden_food = None

    def _init_menu_snake(self):
        path = []
        for x in range(0, COLS):         path.append((x, 1))
        for y in range(2, ROWS - 1):     path.append((COLS - 2, y))
        for x in range(COLS - 3, -1, -1): path.append((x, ROWS - 2))
        for y in range(ROWS - 3, 0, -1): path.append((0, y))
        self.menu_path  = path
        self.menu_idx   = 0
        self.menu_snake = deque(maxlen=18)
        self.menu_timer = 0

    @property
    def speed(self):
        return min(SPEED_INIT + (self.score // SPEED_STEP) * 2, SPEED_MAX)

    @property
    def level(self):
        return self.score // SPEED_STEP + 1

    # ── Loop ──────────────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            self._events()
            {
                self.MENU:      self._menu,
                self.PLAYING:   self._playing,
                self.PAUSED:    self._paused,
                self.GAME_OVER: self._game_over,
            }[self.state](dt)
            pygame.display.flip()

    # ── Eventos ───────────────────────────────────────────────────────────────
    def _events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type != pygame.KEYDOWN:
                continue
            k = ev.key

            if self.state == self.MENU:
                if k in (pygame.K_RETURN, pygame.K_SPACE):
                    self._init_game(); self.state = self.PLAYING

            elif self.state == self.PLAYING:
                if k == pygame.K_ESCAPE:                      self.state    = self.PAUSED
                if k == pygame.K_UP    and self.direction != DOWN:  self.next_dir = UP
                if k == pygame.K_DOWN  and self.direction != UP:    self.next_dir = DOWN
                if k == pygame.K_LEFT  and self.direction != RIGHT: self.next_dir = LEFT
                if k == pygame.K_RIGHT and self.direction != LEFT:  self.next_dir = RIGHT

            elif self.state == self.PAUSED:
                if k == pygame.K_ESCAPE: self.state = self.PLAYING
                if k == pygame.K_q:      self.state = self.MENU

            elif self.state == self.GAME_OVER:
                if k in (pygame.K_RETURN, pygame.K_SPACE):
                    self._init_game(); self.state = self.PLAYING
                if k == pygame.K_q:
                    self.state = self.MENU

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _menu(self, dt):
        self.screen.blit(self.bg_surf, (0, 0))

        # Cobra de borda animada
        self.menu_timer += dt
        if self.menu_timer >= 75:
            self.menu_timer = 0
            self.menu_idx   = (self.menu_idx + 1) % len(self.menu_path)
            self.menu_snake.appendleft(self.menu_path[self.menu_idx])

        n = len(self.menu_snake)
        for i, (gx, gy) in enumerate(self.menu_snake):
            t = i / max(1, n - 1)
            r = int(BODY_TOP[0] + (BODY_BOT[0] - BODY_TOP[0]) * t)
            g = int(BODY_TOP[1] + (BODY_BOT[1] - BODY_TOP[1]) * t)
            b = int(BODY_TOP[2] + (BODY_BOT[2] - BODY_TOP[2]) * t)
            color = HEAD_C if i == 0 else (r, g, b)
            pygame.draw.rect(self.screen, color,
                             (gx * CELL + 1, gy * CELL + 1, CELL - 2, CELL - 2),
                             border_radius=4)

        # Overlay escuro sobre a grade
        self.overlay.fill((0, 0, 0, 0))
        pygame.draw.rect(self.overlay, (0, 0, 0, 165), (0, 0, GRID_W, SCREEN_H))
        self.screen.blit(self.overlay, (0, 0))

        # Título pulsante
        t_ms  = pygame.time.get_ticks()
        pulse = abs((t_ms % 1800) / 900.0 - 1.0)
        tc    = (60, int(200 + 55 * pulse), int(80 + 30 * pulse))
        f_xl, f_lg, f_md, f_sm = self.fonts
        mid = GRID_W // 2
        draw_text(self.screen, "COBRA ELÉTRICA",     f_xl, tc,     mid, 175, center=True)
        draw_text(self.screen, "Desvie de voce mesmo!", f_md, WHITE, mid, 265, center=True)
        if (t_ms // 500) % 2 == 0:
            draw_text(self.screen, "ENTER para jogar", f_lg, GREEN, mid, 375, center=True)

        # Painel direito
        draw_panel(self.screen, self.fonts, 0, self.highscore, 1)

    # ── Jogando ───────────────────────────────────────────────────────────────
    def _playing(self, dt):
        self.move_timer += dt
        if self.move_timer >= 1000 // self.speed:
            self.move_timer = 0
            self.direction  = self.next_dir
            self._move()

        self.particles = [p for p in self.particles if p.update()]
        self.food.update()
        if self.golden_food:
            self.golden_food.update()

        self.screen.blit(self.bg_surf, (0, 0))
        if self.golden_food:
            self.golden_food.draw(self.screen)
        self.food.draw(self.screen)
        draw_snake(self.screen, self.snake, self.direction)
        for p in self.particles:
            p.draw(self.screen)
        draw_panel(self.screen, self.fonts, self.score, self.highscore, self.level)

    def _move(self):
        hx, hy     = self.snake[0]
        dx, dy     = self.direction
        nx, ny     = hx + dx, hy + dy

        # Colisão com parede
        if not (0 <= nx < COLS and 0 <= ny < ROWS):
            self._die(); return

        # Colisão com corpo
        if (nx, ny) in self.snake:
            self._die(); return

        self.snake.appendleft((nx, ny))
        grow = False

        if (nx, ny) == self.food.pos:
            grow = True
            self.score      += 1
            self.food_count += 1
            if self.snd_eat:
                self.snd_eat.play()
            spawn_particles(self.particles, nx, ny, FOOD_C)
            occupied = set(self.snake)
            if self.golden_food:
                occupied.add(self.golden_food.pos)
            self.food = Food(occupied)
            if self.food_count % GOLDEN_EVERY == 0:
                occ2 = set(self.snake) | {self.food.pos}
                self.golden_food = Food(occ2, golden=True)

        elif self.golden_food and (nx, ny) == self.golden_food.pos:
            grow = True
            self.score += 3
            if self.snd_dourado: self.snd_dourado.play()
            spawn_particles(self.particles, nx, ny, GOLD_C, 32)
            self.golden_food = None

        if not grow:
            self.snake.pop()

    def _die(self):
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.score)
        spawn_particles(self.particles, self.snake[0][0], self.snake[0][1],
                        (220, 50, 50), 40)
        self.flash = 18
        if self.snd_morte: self.snd_morte.play()
        self.state = self.GAME_OVER

    # ── Pausado ───────────────────────────────────────────────────────────────
    def _paused(self, dt):
        self.screen.blit(self.bg_surf, (0, 0))
        self.food.draw(self.screen)
        draw_snake(self.screen, self.snake, self.direction)
        draw_panel(self.screen, self.fonts, self.score, self.highscore, self.level)

        self.overlay.fill((0, 0, 0, 0))
        pygame.draw.rect(self.overlay, (0, 0, 0, 180), (0, 0, GRID_W, SCREEN_H))
        self.screen.blit(self.overlay, (0, 0))

        f_xl, f_lg, f_md, _ = self.fonts
        mid = GRID_W // 2
        draw_text(self.screen, "PAUSADO",         f_xl, YELLOW, mid, 225, center=True)
        draw_text(self.screen, "ESC - Continuar", f_md, WHITE,  mid, 330, center=True)
        draw_text(self.screen, "Q   - Menu",      f_md, GRAY,   mid, 375, center=True)

    # ── Game Over ─────────────────────────────────────────────────────────────
    def _game_over(self, dt):
        self.particles = [p for p in self.particles if p.update()]

        self.screen.blit(self.bg_surf, (0, 0))
        draw_snake(self.screen, self.snake, self.direction)
        for p in self.particles:
            p.draw(self.screen)
        draw_panel(self.screen, self.fonts, self.score, self.highscore, self.level)

        # Flash vermelho de entrada
        self.overlay.fill((0, 0, 0, 0))
        if self.flash > 0:
            self.flash -= 1
            fa = int(160 * self.flash / 18)
            pygame.draw.rect(self.overlay, (200, 0, 0, fa), (0, 0, GRID_W, SCREEN_H))
        else:
            pygame.draw.rect(self.overlay, (0, 0, 0, 185), (0, 0, GRID_W, SCREEN_H))
        self.screen.blit(self.overlay, (0, 0))

        f_xl, f_lg, f_md, _ = self.fonts
        mid = GRID_W // 2
        draw_text(self.screen, "GAME OVER",             f_xl, RED,    mid, 155, center=True)
        draw_text(self.screen, f"Pontos: {self.score}",  f_lg, WHITE,  mid, 258, center=True)

        if self.score > 0 and self.score >= self.highscore:
            draw_text(self.screen, "NOVO RECORDE!",               f_md, YELLOW, mid, 318, center=True)
        else:
            draw_text(self.screen, f"Recorde: {self.highscore}",  f_md, ORANGE, mid, 318, center=True)

        draw_text(self.screen, "ENTER - Jogar novamente", f_md, GREEN, mid, 408, center=True)
        draw_text(self.screen, "Q     - Menu principal",  f_md, GRAY,  mid, 453, center=True)


if __name__ == "__main__":
    Game().run()
