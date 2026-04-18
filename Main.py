import pygame
import sys
import random
import threading
import queue
import re
import Levenshtein
import webbrowser
from PIL import Image, ImageSequence
from openai import OpenAI
import time
"""
------------------------
这是一个学习游戏程序
作者:KeFeng
QQ号:2877654604
B站账号:h2y9
------------------------
此程序基于KimiAI大模型。如需要换模型你们可以使用AI帮你们修改
"""
# ==================== 游戏配置 ====================
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# ==================== 颜色定义 ====================
BACKGROUND = (25, 25, 40)
WHITE = (255, 255, 255)
PLAYER_COLOR = (30, 144, 255)
WALL_COLOR = (139, 69, 19)
GROUND_COLOR = (46, 139, 87)
MONSTER_COLOR = (178, 34, 34)
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER = (100, 149, 237)
TEXT_COLOR = (240, 248, 255)
BLACK = (0, 0, 0)
RED = (220, 20, 60)
GREEN = (34, 139, 34)
LEVEL_COLORS = [(65, 105, 225), (50, 205, 50), (220, 20, 60)]
UI_BUTTON_COLOR = (80, 80, 120, 180)
UI_BUTTON_ACTIVE = (120, 120, 180, 220)

score = 5

# ==================== AI 剧情生成器 ====================
class StoryGenerator:
    def __init__(self, subject, grade, unit):
        self.subject = subject
        self.grade = grade
        self.unit = unit
        self.cache = {}  # 缓存剧情 {key: text}

    def _call_kimi(self, prompt):
        client = OpenAI(
            api_key="sk-你的kimiAI模型密钥",
            base_url="https://api.moonshot.cn/v1",
        )
        completion = client.chat.completions.create(
            model="kimi-k2-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )
        return completion.choices[0].message.content

    def get_story(self, story_type, level=None):
        """story_type: 'opening', 'level_start', 'death', 'level_complete', 'idle_hint'"""
        key = f"{story_type}_{level}" if level else story_type
        if key in self.cache:
            return self.cache[key]

        if story_type == 'opening':
            prompt = f"请为一位学习{self.subject}的学生写一段简短的游戏开场剧情（100字以内），背景是知识大陆，需要提到{self.grade}{self.unit}的知识点。风格励志。"
        elif story_type == 'level_start':
            prompt = f"请为{self.subject}第{level}关写一段简短的游戏剧情（50字以内），鼓励玩家挑战{self.grade}{self.unit}的题目。"
        elif story_type == 'death':
            prompt = f"玩家在{self.subject}闯关中失败了，请写一句简短的鼓励话语（30字以内），包含{self.grade}{self.unit}的知识点。"
        elif story_type == 'level_complete':
            prompt = f"玩家成功完成了{self.subject}第{level}关，请写一句祝贺语（30字以内），提到{self.unit}的知识掌握。"
        elif story_type == 'idle_hint':
            prompt = f"玩家在{self.subject}学习游戏中停留了较久，请写一句提示（30字以内），引导他移动或答题。"
        else:
            return ""

        try:
            text = self._call_kimi(prompt)
            self.cache[key] = text
            return text
        except:
            return "努力学习，勇往直前！"

# ==================== 底部剧情栏 ====================
class StoryBar:
    def __init__(self, font, small_font):
        self.font = font
        self.small_font = small_font
        self.text = ""
        self.lines = []          # 完整分行（每行不超过 max_chars）
        self.display_lines = []  # 当前显示的行（最多 max_display_lines 行）
        self.scroll_offset = 0   # 滚动偏移（行数）
        self.char_index = 0
        self.line_index = 0
        self.timer = 0
        self.typing_speed = 0.03
        self.last_update = time.time()
        self.active = False
        self.duration = 8
        self.start_time = 0

        self.bar_height = 150            # 增高，便于显示更多行
        self.max_display_lines = 5       # 最多同时显示5行
        self.max_chars_per_line = 45     # 根据屏幕宽度调整（1200px / 字体大小）
        self.bar_rect = pygame.Rect(0, SCREEN_HEIGHT - self.bar_height, SCREEN_WIDTH, self.bar_height)

    def _wrap_text(self, text):
        """按最大字符数强制换行，不再依赖标点"""
        lines = []
        while len(text) > self.max_chars_per_line:
            # 寻找最近的空格或标点，避免截断单词（中文可直接截断）
            split_pos = self.max_chars_per_line
            # 向后微调至非汉字中间（可选）
            lines.append(text[:split_pos])
            text = text[split_pos:]
        if text:
            lines.append(text)
        return lines

    def show(self, text):
        self.text = text
        self.lines = self._wrap_text(text)
        self.display_lines = []          # 清空显示行
        self.scroll_offset = 0
        self.line_index = 0
        self.char_index = 0
        self.active = True
        self.start_time = time.time()
        self.last_update = time.time()
        self._update_display_line()

    def _update_display_line(self):
        """逐字打印当前行，并管理显示缓冲区"""
        if not self.active:
            return
        # 如果当前行已经完整显示，准备下一行
        if self.line_index < len(self.lines):
            line = self.lines[self.line_index]
            if self.char_index < len(line):
                # 逐字增加
                self.char_index += 1
                # 更新显示行（始终显示已打印的部分）
                if self.line_index < len(self.display_lines):
                    self.display_lines[self.line_index] = line[:self.char_index]
                else:
                    self.display_lines.append(line[:self.char_index])
                # 如果这一行还没打完，直接返回
                return
            else:
                # 当前行已打完，移动到下一行
                self.line_index += 1
                self.char_index = 0
                # 如果还有下一行，继续添加（但尚未打印字符）
                if self.line_index < len(self.lines):
                    # 在 display_lines 中预留位置（空字符串）
                    self.display_lines.append("")
                    # 立即开始打印下一行的第一个字符（递归调用一次）
                    self._update_display_line()
                else:
                    # 所有行已打印完毕
                    pass
        # 控制滚动：保持最底行可见
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """自动滚动，使最新行显示在底部"""
        if len(self.display_lines) > self.max_display_lines:
            # 只保留最后 max_display_lines 行
            excess = len(self.display_lines) - self.max_display_lines
            self.display_lines = self.display_lines[excess:]
            # 注意：line_index 和 char_index 是相对于原始 lines 的，需要相应调整偏移
            # 但因为我们只关心显示，且显示行已裁剪，所以无需调整 line_index

    def update(self):
        if not self.active:
            return
        now = time.time()
        if now - self.last_update > self.typing_speed:
            self.last_update = now
            self._update_display_line()
        # 超时自动关闭（所有行已显示完且超过 duration 秒）
        if (self.line_index >= len(self.lines) and 
            time.time() - self.start_time > self.duration):
            self.active = False

    def handle_click(self):
        """点击直接显示全文并关闭（或继续等待关闭）"""
        if not self.active:
            return
        # 直接显示所有行全文
        self.display_lines = self.lines.copy()
        self.line_index = len(self.lines)
        self.char_index = 0
        # 裁剪到最大显示行数
        if len(self.display_lines) > self.max_display_lines:
            self.display_lines = self.display_lines[-self.max_display_lines:]

    def draw(self, screen):
        if not self.active:
            return
        # 半透明背景
        s = pygame.Surface((self.bar_rect.width, self.bar_rect.height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        screen.blit(s, self.bar_rect)
        pygame.draw.rect(screen, WHITE, self.bar_rect, 2, border_radius=10)

        # 绘制当前显示的行（最多 max_display_lines 行）
        y_offset = SCREEN_HEIGHT - self.bar_height + 15
        for i, line in enumerate(self.display_lines):
            # 只显示最后 max_display_lines 行（已在 _scroll_to_bottom 中裁剪）
            text_surf = self.small_font.render(line, True, WHITE)
            screen.blit(text_surf, (20, y_offset + i * 25))  # 行高25像素

        # 提示继续（全文显示后显示箭头）
        if self.line_index >= len(self.lines):
            tip = self.small_font.render("▼", True, (200,200,200))
            screen.blit(tip, (SCREEN_WIDTH - 30, SCREEN_HEIGHT - 30))

# ==================== GIF 加载工具 ====================
def load_gif_frames(filename, target_width=None, target_height=None):
    try:
        pil_image = Image.open(filename)
        frames = []
        for frame in ImageSequence.Iterator(pil_image):
            frame_rgba = frame.convert("RGBA")
            size = frame_rgba.size
            data = frame_rgba.tobytes()
            surface = pygame.image.fromstring(data, size, "RGBA")
            if target_width and target_height:
                surface = pygame.transform.scale(surface, (target_width, target_height))
            frames.append(surface)
        return frames
    except Exception as e:
        print(f"加载 GIF 失败 {filename}: {e}")
        return None

# ==================== 玩家类（不变） ====================
class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 40, 60)
        self.color = PLAYER_COLOR
        self.speed = 5
        self.jump_power = -18
        self.velocity_y = 0
        self.on_ground = False
        self.lives = 3

        self.skills = {
            'high_jump': {'cooldown': 0, 'max_cooldown': 60, 'active': False}
        }

        self.jump_buffer = 0
        self.coyote_time = 0
        self.jump_pressed_prev = False
        self.facing_right = True

        self.ground_frames = load_gif_frames("player_idle.gif", 40, 60)
        self.jump_frames = load_gif_frames("player_jump.gif", 40, 60)
        self.current_frames = self.ground_frames if self.ground_frames else None
        self.frame_index = 0
        self.animation_speed = 0.15
        self.animation_timer = 0.0

        if self.ground_frames and not self.jump_frames:
            self.jump_frames = self.ground_frames

    def update(self, keys, ground, walls, left_pressed, right_pressed, jump_pressed):
        global score
        if self.jump_buffer > 0:
            self.jump_buffer -= 1

        if self.on_ground:
            self.coyote_time = 10
        elif self.coyote_time > 0:
            self.coyote_time -= 1

        if keys[pygame.K_LEFT] or left_pressed:
            self.rect.x -= self.speed
            self.facing_right = False
        if keys[pygame.K_RIGHT] or right_pressed:
            self.rect.x += self.speed
            self.facing_right = True

        self.velocity_y += 1.2
        self.rect.y += self.velocity_y

        self.on_ground = False
        if self.rect.bottom >= ground.rect.top:
            self.rect.bottom = ground.rect.top
            self.velocity_y = 0
            self.on_ground = True

        for wall in walls:
            if self.rect.colliderect(wall.rect):
                overlap_left = self.rect.right - wall.rect.left
                overlap_right = wall.rect.right - self.rect.left
                overlap_top = self.rect.bottom - wall.rect.top
                overlap_bottom = wall.rect.bottom - self.rect.top

                min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)

                if min_overlap == overlap_top and self.velocity_y >= 0:
                    self.rect.bottom = wall.rect.top
                    self.velocity_y = 0
                    self.on_ground = True
                elif min_overlap == overlap_bottom and self.velocity_y < 0:
                    self.rect.top = wall.rect.bottom
                    self.velocity_y = 0
                elif min_overlap == overlap_left:
                    self.rect.right = wall.rect.left
                elif min_overlap == overlap_right:
                    self.rect.left = wall.rect.right

        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH

        jump_key_current = keys[pygame.K_SPACE] or keys[pygame.K_UP] or jump_pressed
        if jump_key_current and not self.jump_pressed_prev:
            self.jump_buffer = 5
        self.jump_pressed_prev = jump_key_current

        if self.jump_buffer > 0 and (self.on_ground or self.coyote_time > 0):
            if self.skills['high_jump']['active']:
                self.velocity_y = self.jump_power * 1.5
                self.skills['high_jump']['active'] = False
                score = score - 5
            else:
                self.velocity_y = self.jump_power
            self.on_ground = False
            self.coyote_time = 0
            self.jump_buffer = 0

        if self.on_ground:
            self.current_frames = self.ground_frames
        else:
            self.current_frames = self.jump_frames

        if self.current_frames:
            self.animation_timer += 1 / FPS
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0.0
                self.frame_index = (self.frame_index + 1) % len(self.current_frames)

    def draw(self, screen, font):
        if self.current_frames:
            frame = self.current_frames[self.frame_index]
            if not self.facing_right:
                frame = pygame.transform.flip(frame, True, False)
            screen.blit(frame, self.rect)
        else:
            pygame.draw.rect(screen, self.color, self.rect, border_radius=8)
            pygame.draw.rect(screen, BLACK, self.rect, 2, border_radius=8)

# ==================== 地面、墙壁、怪物、按钮等类（与原相同，省略） ====================
# 为了节省篇幅，这里只保留类名，实际使用时请复制原文件中的这些类定义
# 注意：Ground, Wall, Monster, Button, UIButton, InputBox, SubjectSelector, QuizManager 均保持不变
# 但为了完整性，下面会给出必要的类定义（从原文件复制）

class Ground:
    def __init__(self, y, width, height):
        self.rect = pygame.Rect(0, y, width, height)
        self.color = GROUND_COLOR
        self.tile_image = None
        try:
            img = pygame.image.load("ground.png").convert_alpha()
            self.tile_image = pygame.transform.scale(img, (40, 40))
        except:
            pass
    def draw(self, screen):
        if self.tile_image:
            tile_w = self.tile_image.get_width()
            tile_h = self.tile_image.get_height()
            for x in range(0, self.rect.width, tile_w):
                for y in range(0, self.rect.height, tile_h):
                    screen.blit(self.tile_image, (self.rect.x + x, self.rect.y + y))
        else:
            pygame.draw.rect(screen, self.color, self.rect)
            for i in range(0, SCREEN_WIDTH, 20):
                pygame.draw.line(screen, (34, 177, 76), (i, self.rect.top), (i + 10, self.rect.top - 10), 3)

class Wall:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = WALL_COLOR
        self.tile_image = None
        try:
            img = pygame.image.load("wall.png").convert_alpha()
            self.tile_image = pygame.transform.scale(img, (40, 40))
        except:
            pass
    def draw(self, screen):
        if self.tile_image:
            tile_w = self.tile_image.get_width()
            tile_h = self.tile_image.get_height()
            old_clip = screen.get_clip()
            screen.set_clip(self.rect)
            for x in range(self.rect.left, self.rect.right, tile_w):
                for y in range(self.rect.top, self.rect.bottom, tile_h):
                    screen.blit(self.tile_image, (x, y))
            screen.set_clip(old_clip)
        else:
            pygame.draw.rect(screen, self.color, self.rect)
            pygame.draw.rect(screen, (101, 67, 33), self.rect, 2)
            for i in range(0, self.rect.height, 10):
                pygame.draw.line(screen, (101, 67, 33), (self.rect.left, self.rect.top + i), (self.rect.right, self.rect.top + i), 1)

class Monster:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 40, 40)
        self.color = MONSTER_COLOR
        self.speed = 2
        self.direction = 1
        self.move_area = {'left': 200, 'right': 600}
        self.frames = load_gif_frames("monster.gif", 40, 40)
        self.frame_index = 0
        self.animation_speed = 0.2
        self.animation_timer = 0.0
    def update(self):
        self.rect.x += self.speed * self.direction
        if self.rect.left <= self.move_area['left'] or self.rect.right >= self.move_area['right']:
            self.direction *= -1
        if self.frames:
            self.animation_timer += 1 / FPS
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0.0
                self.frame_index = (self.frame_index + 1) % len(self.frames)
    def draw(self, screen):
        if self.frames:
            frame = self.frames[self.frame_index]
            if self.direction == -1:
                frame = pygame.transform.flip(frame, True, False)
            screen.blit(frame, self.rect)
        else:
            pygame.draw.rect(screen, self.color, self.rect, border_radius=10)
            pygame.draw.rect(screen, (139, 0, 0), self.rect, 2, border_radius=10)
            eye_x = self.rect.left + 10 if self.direction == 1 else self.rect.right - 15
            pygame.draw.circle(screen, WHITE, (eye_x, self.rect.top + 15), 6)
            pygame.draw.circle(screen, BLACK, (eye_x, self.rect.top + 15), 3)

class Button:
    def __init__(self, x, y, width, height, text, action=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = BUTTON_COLOR
        self.text = text
        self.action = action
        self.hovered = False
    def draw(self, screen, font):
        color = BUTTON_HOVER if self.hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=10)
        pygame.draw.rect(screen, (30, 70, 120), self.rect, 2, border_radius=10)
        text_surf = font.render(self.text, True, TEXT_COLOR)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)
    def check_hover(self, pos):
        self.hovered = self.rect.collidepoint(pos)
        return self.hovered
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered and self.action:
                self.action()
                return True
        return False

class UIButton:
    def __init__(self, x, y, width, height, button_type):
        self.rect = pygame.Rect(x, y, width, height)
        self.button_type = button_type
        self.pressed = False
        self.radius = min(width, height) // 2
    def draw(self, screen):
        surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        color = UI_BUTTON_ACTIVE if self.pressed else UI_BUTTON_COLOR
        pygame.draw.circle(surface, color, (self.radius, self.radius), self.radius)
        if self.button_type == 'left':
            pygame.draw.polygon(surface, WHITE, [(self.radius + 10, self.radius - 8), (self.radius - 10, self.radius), (self.radius + 10, self.radius + 8)])
        elif self.button_type == 'right':
            pygame.draw.polygon(surface, WHITE, [(self.radius - 10, self.radius - 8), (self.radius + 10, self.radius), (self.radius - 10, self.radius + 8)])
        elif self.button_type == 'jump':
            pygame.draw.polygon(surface, WHITE, [(self.radius, self.radius - 10), (self.radius - 8, self.radius + 5), (self.radius + 8, self.radius + 5)])
        screen.blit(surface, self.rect)

class InputBox:
    def __init__(self, x, y, width, height, font, text=''):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = BUTTON_COLOR
        self.text = text
        self.font = font
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            was_active = self.active
            self.active = self.rect.collidepoint(event.pos)
            if self.active and not was_active:
                pygame.key.start_text_input()
                pygame.key.set_text_input_rect(self.rect)
            elif not self.active and was_active:
                pygame.key.stop_text_input()
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
                pygame.key.stop_text_input()
        if event.type == pygame.TEXTINPUT and self.active:
            self.text += event.text
    def update(self):
        self.cursor_timer += 1
        if self.cursor_timer >= 30:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=5)
        border_color = WHITE if self.active else TEXT_COLOR
        pygame.draw.rect(screen, border_color, self.rect, 2, border_radius=5)
        txt_surface = self.font.render(self.text, True, WHITE)
        screen.blit(txt_surface, (self.rect.x + 10, self.rect.y + (self.rect.height - txt_surface.get_height()) // 2))
        if self.active and self.cursor_visible:
            cursor_x = self.rect.x + 10 + txt_surface.get_width() + 2
            pygame.draw.line(screen, WHITE, (cursor_x, self.rect.y + 5), (cursor_x, self.rect.y + self.rect.height - 5), 2)

class SubjectSelector:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("选择学习科目")
        self.clock = pygame.time.Clock()
        self.running = True
        try:
            self.font = pygame.font.Font("simhei.ttf", 30)
            self.small_font = pygame.font.Font("simhei.ttf", 24)
        except:
            self.font = pygame.font.SysFont("simsun", 30)
            self.small_font = pygame.font.SysFont("simsun", 24)
        self.subjects = ["语文", "数学", "英语", "物理", "化学", "生物", "道法", "历史", "地理"]
        self.subject_buttons = []
        self.create_subject_buttons()
        self.selected_subject_index = 0
        self.grade_input = InputBox(300, 460, 200, 40, self.small_font, "八年级上册")
        self.unit_input = InputBox(300, 530, 200, 40, self.small_font, "第一单元")
        self.start_button = Button(300, 600, 200, 50, "开始游戏", self.start_game_action)
        self.result = None
    def create_subject_buttons(self):
        btn_width = 100; btn_height = 50; start_x = 100; start_y = 150; cols = 3
        for i, name in enumerate(self.subjects):
            row = i // cols; col = i % cols
            x = start_x + col * (btn_width + 20); y = start_y + row * (btn_height + 20)
            btn = Button(x, y, btn_width, btn_height, name, action=lambda idx=i: self.select_subject(idx))
            self.subject_buttons.append(btn)
    def select_subject(self, index):
        self.selected_subject_index = index
    def start_game_action(self):
        self.result = (self.subjects[self.selected_subject_index], self.grade_input.text, self.unit_input.text)
        self.running = False
    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False; self.result = None
                for btn in self.subject_buttons:
                    btn.check_hover(pygame.mouse.get_pos()); btn.handle_event(event)
                self.start_button.check_hover(pygame.mouse.get_pos()); self.start_button.handle_event(event)
                self.grade_input.handle_event(event); self.unit_input.handle_event(event)
            self.grade_input.update(); self.unit_input.update()
            self.draw(); self.clock.tick(FPS)
        return self.result
    def draw(self):
        self.screen.fill(BACKGROUND)
        title = self.font.render("选择你要学习的科目", True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 50))
        for i, btn in enumerate(self.subject_buttons):
            btn.color = (100,200,100) if i == self.selected_subject_index else BUTTON_COLOR
            btn.draw(self.screen, self.small_font)
        selected_text = self.small_font.render(f"当前选择: {self.subjects[self.selected_subject_index]}", True, (255,255,100))
        self.screen.blit(selected_text, (SCREEN_WIDTH // 2 - selected_text.get_width() // 2, 390))
        grade_label = self.small_font.render("年级上下册:", True, WHITE); self.screen.blit(grade_label, (150, 470))
        self.grade_input.draw(self.screen)
        unit_label = self.small_font.render("单元:", True, WHITE); self.screen.blit(unit_label, (230, 540))
        self.unit_input.draw(self.screen)
        self.start_button.draw(self.screen, self.font)
        pygame.display.flip()

class QuizManager:
    def __init__(self, subject, grade, unit):
        self.subject = subject; self.grade = grade; self.unit = unit
        self.queue = queue.Queue(); self.messages = []; self._init_conversation(); self._prefetch()
    def _init_conversation(self):
        system_prompt = (f"你是 Kimi，一位专业的{self.subject}教师。你正在为{self.grade}的学生出{self.unit}的单项选择题。"
                         "请严格遵循以下规则：\n1. 每次只出一道题，题目清晰，有四个选项（A/B/C/D）。\n"
                         "2. 输出格式必须为：题目内容|A. xxx|B. xxx|C. xxx|D. xxx|正确答案字母\n"
                         "3. 四个选项必须具有明显差异性。\n4. 不要重复之前出过的题目。\n"
                         "5. 当学生回答后，你需要判断对错并给予简短反馈，然后继续出下一题。")
        self.messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": "请出第一道题。"}]
    def _call_kimi(self):
        client = OpenAI(api_key="sk-你的kimi模型密钥", base_url="https://api.moonshot.cn/v1")
        completion = client.chat.completions.create(model="kimi-k2-turbo-preview", messages=self.messages, temperature=0.8)
        return completion.choices[0].message.content
    def _parse_question(self, text):
        if not text: return None
        text = text.strip()
        parts = text.split('|')
        if len(parts) >= 6:
            question = parts[0].strip(); options = [p.strip() for p in parts[1:5]]; answer = parts[5].strip().upper()
            if not question and options and options[0].startswith(('A.', 'A、')): question = "请选择正确答案"
            return (question, options, answer)
        pattern = r'^(.*?)\s*A[\.、]\s*(.+?)\s*B[\.、]\s*(.+?)\s*C[\.、]\s*(.+?)\s*D[\.、]\s*(.+?)\s*答案[：:]\s*([A-D])'
        match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
        if match:
            question = match.group(1).strip()
            options = [f"A. {match.group(2).strip()}", f"B. {match.group(3).strip()}", f"C. {match.group(4).strip()}", f"D. {match.group(5).strip()}"]
            answer = match.group(6).strip().upper()
            if not question: question = "请选择正确答案"
            return (question, options, answer)
        option_pattern = r'A[\.、]\s*(.+?)\s*B[\.、]\s*(.+?)\s*C[\.、]\s*(.+?)\s*D[\.、]\s*(.+?)(?:\s*答案[：:]\s*([A-D]))?'
        opt_match = re.search(option_pattern, text, re.DOTALL)
        if opt_match:
            question = "请选择正确答案"
            options = [f"A. {opt_match.group(1).strip()}", f"B. {opt_match.group(2).strip()}", f"C. {opt_match.group(3).strip()}", f"D. {opt_match.group(4).strip()}"]
            answer = opt_match.group(5).strip().upper() if opt_match.group(5) else 'A'
            return (question, options, answer)
        return None
    def _is_valid_question(self, parsed):
        if parsed is None: return False
        _, options, _ = parsed
        if len(options) >= 2:
            texts = [opt[3:] for opt in options]
            distances = []
            for i in range(len(texts)):
                for j in range(i+1, len(texts)):
                    distances.append(Levenshtein.distance(texts[i], texts[j]))
            avg_dist = sum(distances) / len(distances) if distances else 0
            if avg_dist < 3: return False
        return True
    def _prefetch(self):
        def fetch():
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self._call_kimi()
                    self.messages.append({"role": "assistant", "content": response})
                    parsed = self._parse_question(response)
                    if self._is_valid_question(parsed):
                        self.queue.put(parsed); return
                    else:
                        self.messages.append({"role": "user", "content": "题目无效，请重新出一道符合格式的题目。"})
                except Exception as e:
                    print(f"出题失败 (尝试 {attempt+1}): {e}")
            default = ("AI出题暂时不可用", ["A. 重试", "B. 跳过", "C. 等待", "D. 退出"], "A")
            self.queue.put(default)
        threading.Thread(target=fetch, daemon=True).start()
    def get_question(self, timeout=10):
        try:
            data = self.queue.get(timeout=timeout)
            self.messages.append({"role": "user", "content": "请出下一道题。"})
            self._prefetch()
            return data
        except queue.Empty: return None
    def submit_answer(self, is_correct):
        feedback = "我答对了。" if is_correct else "我答错了。"
        self.messages.append({"role": "user", "content": feedback})

# ==================== 主游戏类（整合新剧情栏和停留提示） ====================
class Game:
    def __init__(self, quiz_manager=None, story_gen=None):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("平台跳跃 - 答题闯关")
        self.clock = pygame.time.Clock()
        self.running = True

        try:
            self.font = pygame.font.Font("simhei.ttf", 36)
            self.small_font = pygame.font.Font("simhei.ttf", 24)
        except:
            self.font = pygame.font.SysFont("simsun", 36)
            self.small_font = pygame.font.SysFont("simsun", 24)

        self.quiz_manager = quiz_manager
        self.story_gen = story_gen
        self.story_bar = StoryBar(self.font, self.small_font)

        self.game_state = "playing"  # playing, game_over, next_level, settings
        self.level = 1
        self.ground = None
        self.player = None
        self.monsters = []
        self.walls = []

        # 答题状态
        self.quiz_active = False
        self.quiz_data = None
        self.quiz_option_rects = []
        self.quiz_callback = None
        self.quiz_fetching = False
        self.quiz_result_text = ""
        self.quiz_result_timer = 0

        # UI 按钮
        self.left_button = None
        self.right_button = None
        self.jump_button = None
        self.button_states = {'left': False, 'right': False, 'jump': False}

        # 菜单按钮
        self.game_over_buttons = []
        self.next_level_buttons = []
        self.settings_buttons = []
        self.settings_button = None

        # 停留提示计时器
        self.last_player_pos = None
        self.idle_start_time = None
        self.idle_hint_shown = False

        self.init_game_objects()
        self.create_ui_buttons()
        self.create_menu_buttons()
        self.create_settings_button()

        # 开场剧情
        if self.story_gen:
            story_text = self.story_gen.get_story('opening')
            self.story_bar.show(story_text)

    def init_game_objects(self):
        self.ground = Ground(500, SCREEN_WIDTH, 100)
        self.player = Player(100, 350)
        self.generate_monsters(self.level)
        self.generate_level_walls(self.level)

    def create_ui_buttons(self):
        btn_size = 70; margin = 20; y = SCREEN_HEIGHT - btn_size - margin
        self.left_button = UIButton(margin, y, btn_size, btn_size, 'left')
        self.right_button = UIButton(margin + btn_size + 20, y, btn_size, btn_size, 'right')
        self.jump_button = UIButton(SCREEN_WIDTH - btn_size - margin, y, btn_size, btn_size, 'jump')

    def create_menu_buttons(self):
        self.game_over_buttons = [
            Button(SCREEN_WIDTH//2-100, 300, 200, 50, "重新开始", self.reset_game),
            Button(SCREEN_WIDTH//2-100, 370, 200, 50, "退出游戏", self.quit_game)
        ]
        self.next_level_buttons = [
            Button(SCREEN_WIDTH//2-100, 300, 200, 50, "下一关", self.next_level),
            Button(SCREEN_WIDTH//2-100, 370, 200, 50, "退出游戏", self.quit_game)
        ]
        self.settings_buttons = [
            Button(SCREEN_WIDTH//2-100, 250, 200, 50, "重新开始", self.reset_game),
            Button(SCREEN_WIDTH//2-100, 320, 200, 50, "退出游戏", self.quit_game),
            Button(SCREEN_WIDTH//2-100, 390, 200, 50, "联系开发者", self.contact_developer)
        ]

    def create_settings_button(self):
        self.settings_button = Button(SCREEN_WIDTH - 120, 20, 100, 40, "设置", self.open_settings)

    def open_settings(self):
        if self.game_state == "playing":
            self.game_state = "settings"

    def contact_developer(self):
        webbrowser.open("https://space.bilibili.com/3494362218498847")

    def generate_monsters(self, level):
        self.monsters = []
        target_num = 2 + level
        forbidden_rects = [self.player.rect.inflate(80, 80)]
        for i in range(target_num):
            placed = False
            for _ in range(200):
                x = random.randint(200, 600); y = random.randint(100, 460)
                new_monster = Monster(x, y)
                if any(new_monster.rect.colliderect(f) for f in forbidden_rects): continue
                self.monsters.append(new_monster); forbidden_rects.append(new_monster.rect.inflate(30,30)); placed = True; break
            if not placed:
                default_x = 400 + i*40; monster = Monster(default_x, 400)
                while any(monster.rect.colliderect(f) for f in forbidden_rects): default_x += 20; monster.rect.x = default_x
                self.monsters.append(monster); forbidden_rects.append(monster.rect.inflate(30,30))

    def generate_level_walls(self, level):
        self.walls = []
        target_num = 5 + level*2
        forbidden_rects = [self.player.rect.inflate(60,60)] + [m.rect.inflate(40,40) for m in self.monsters]
        for i in range(target_num):
            placed = False
            for _ in range(500):
                w = random.randint(60,150); h = random.randint(20,150); x = random.randint(0, SCREEN_WIDTH-w); y = random.randint(10,450)
                new_rect = pygame.Rect(x, y, w, h)
                if any(new_rect.colliderect(f) for f in forbidden_rects): continue
                self.walls.append(Wall(x, y, w, h)); placed = True; break
            if not placed:
                default_x = 300 + i*30; default_y = 350; default_w = 80; default_h = 80
                default_rect = pygame.Rect(default_x, default_y, default_w, default_h)
                while any(default_rect.colliderect(f) for f in forbidden_rects): default_x += 20; default_rect.x = default_x
                self.walls.append(Wall(default_x, default_y, default_w, default_h))

    def next_level(self):
        global score
        self.level += 1
        score += 10
        self.player = Player(100, 350)
        self.generate_monsters(self.level)
        self.generate_level_walls(self.level)
        # 显示关卡开始剧情
        if self.story_gen:
            story = self.story_gen.get_story('level_start', self.level)
            self.story_bar.show(story)
        self.game_state = "playing"
        # 重置停留计时
        self.last_player_pos = None
        self.idle_start_time = None
        self.idle_hint_shown = False

    def reset_game(self):
        global score
        self.level = 1
        score = 5
        self.player = Player(100, 350)
        self.generate_monsters(self.level)
        self.generate_level_walls(self.level)
        if self.story_gen:
            story = self.story_gen.get_story('opening')
            self.story_bar.show(story)
        self.game_state = "playing"
        self.last_player_pos = None
        self.idle_start_time = None
        self.idle_hint_shown = False

    def quit_game(self):
        self.running = False

    # ---------- 答题相关 ----------
    def start_quiz(self, callback):
        if self.quiz_manager is None:
            callback(True); return
        self.quiz_active = True
        self.quiz_callback = callback
        self.quiz_data = None
        self.quiz_fetching = True
        self.quiz_result_text = ""
        def fetch():
            data = self.quiz_manager.get_question(timeout=30)
            self.quiz_data = data
            self.quiz_fetching = False
        threading.Thread(target=fetch, daemon=True).start()

    def handle_quiz_event(self, event):
        if not self.quiz_active or self.quiz_fetching: return
        if self.quiz_data is None:
            self.quiz_active = False
            if self.quiz_callback: self.quiz_callback(True); return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            for i, rect in enumerate(self.quiz_option_rects):
                if rect.collidepoint(pos):
                    selected = chr(ord('A') + i)
                    correct = self.quiz_data[2]
                    is_correct = (selected == correct)
                    self.quiz_result_text = "回答正确！" if is_correct else "回答错误！"
                    self.quiz_result_timer = FPS
                    self.quiz_active = False
                    if self.quiz_callback:
                        self.quiz_callback(is_correct)
                    break

    def draw_quiz(self, screen):
        if not self.quiz_active and self.quiz_result_timer <= 0: return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,200))
        screen.blit(overlay, (0,0))
        if self.quiz_fetching:
            text = self.font.render("AI 正在出题，请稍候...", True, WHITE)
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2)); return
        if self.quiz_data is None:
            text = self.font.render("出题失败，按任意键继续", True, RED)
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2)); return
        question, options, _ = self.quiz_data
        y_offset = 200
        q_surf = self.small_font.render(question, True, WHITE)
        screen.blit(q_surf, (50, y_offset)); y_offset += 60
        self.quiz_option_rects = []
        for i, opt in enumerate(options):
            btn_rect = pygame.Rect(100, y_offset + i*60, 600, 50)
            self.quiz_option_rects.append(btn_rect)
            pygame.draw.rect(screen, BUTTON_COLOR, btn_rect, border_radius=8)
            opt_surf = self.small_font.render(opt, True, WHITE)
            screen.blit(opt_surf, (btn_rect.x+20, btn_rect.y+10))
        if self.quiz_result_timer > 0:
            result_color = GREEN if "正确" in self.quiz_result_text else RED
            result_surf = self.font.render(self.quiz_result_text, True, result_color)
            screen.blit(result_surf, (SCREEN_WIDTH//2 - result_surf.get_width()//2, 100))
            self.quiz_result_timer -= 1

    # ---------- 停留提示 ----------
    def update_idle_hint(self):
        if self.game_state != "playing": return
        if self.quiz_active or self.story_bar.active: return
        current_pos = (self.player.rect.x, self.player.rect.y)
        if self.last_player_pos is None:
            self.last_player_pos = current_pos
            self.idle_start_time = time.time()
            return
        # 检测是否移动（位置变化超过5像素）
        moved = (abs(current_pos[0] - self.last_player_pos[0]) > 5 or abs(current_pos[1] - self.last_player_pos[1]) > 5)
        if moved:
            self.last_player_pos = current_pos
            self.idle_start_time = time.time()
            self.idle_hint_shown = False
        else:
            if not self.idle_hint_shown and time.time() - self.idle_start_time > 10:
                # 显示停留提示
                if self.story_gen:
                    hint = self.story_gen.get_story('idle_hint')
                    self.story_bar.show(hint)
                else:
                    self.story_bar.show("动一动！去触碰怪物回答问题吧！")
                self.idle_hint_shown = True

    # ---------- 事件处理 ----------
    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # 剧情栏点击跳过/关闭
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.story_bar.active:
                    self.story_bar.handle_click()
                    continue

            if self.quiz_active or self.quiz_result_timer > 0:
                self.handle_quiz_event(event); continue

            if self.settings_button:
                self.settings_button.check_hover(mouse_pos); self.settings_button.handle_event(event)

            if self.game_state == "game_over":
                for btn in self.game_over_buttons:
                    btn.check_hover(mouse_pos); btn.handle_event(event)
            elif self.game_state == "next_level":
                for btn in self.next_level_buttons:
                    btn.check_hover(mouse_pos); btn.handle_event(event)
            elif self.game_state == "settings":
                for btn in self.settings_buttons:
                    btn.check_hover(mouse_pos); btn.handle_event(event)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.game_state = "playing"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    clicked = any(btn.rect.collidepoint(event.pos) for btn in self.settings_buttons)
                    if not clicked and self.settings_button and not self.settings_button.rect.collidepoint(event.pos):
                        self.game_state = "playing"
            elif self.game_state == "playing":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.left_button.rect.collidepoint(event.pos): self.button_states['left'] = True
                    elif self.right_button.rect.collidepoint(event.pos): self.button_states['right'] = True
                    elif self.jump_button.rect.collidepoint(event.pos): self.button_states['jump'] = True
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.button_states = {'left': False, 'right': False, 'jump': False}
                if event.type == pygame.KEYDOWN and event.key == pygame.K_1 and self.player.skills['high_jump']['cooldown'] == 0:
                    if score >= 5:
                        self.player.skills['high_jump']['active'] = True
                        self.player.skills['high_jump']['cooldown'] = self.player.skills['high_jump']['max_cooldown']
                    else:
                        print("积分不足")

    # ---------- 更新逻辑 ----------
    def update(self):
        self.story_bar.update()
        if self.quiz_active or self.quiz_result_timer > 0:
            return
        if self.game_state != "playing":
            return

        self.update_idle_hint()

        mouse_pressed = pygame.mouse.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        if mouse_pressed[0]:
            self.button_states['left'] = self.left_button.rect.collidepoint(mouse_pos)
            self.button_states['right'] = self.right_button.rect.collidepoint(mouse_pos)
            self.button_states['jump'] = self.jump_button.rect.collidepoint(mouse_pos)
        else:
            self.button_states = {'left': False, 'right': False, 'jump': False}

        self.left_button.pressed = self.button_states['left']
        self.right_button.pressed = self.button_states['right']
        self.jump_button.pressed = self.button_states['jump']

        keys = pygame.key.get_pressed()
        self.player.update(keys, self.ground, self.walls,
                           self.button_states['left'],
                           self.button_states['right'],
                           self.button_states['jump'])

        for monster in self.monsters:
            monster.update()

        if self.player.skills['high_jump']['cooldown'] > 0:
            self.player.skills['high_jump']['cooldown'] -= 1

        # 碰撞怪物
        for monster in self.monsters:
            if self.player.rect.colliderect(monster.rect):
                self.start_quiz(lambda correct, m=monster: self.on_hurt_quiz_result(correct, m))
                return
        # 过关
        if self.player.rect.x >= SCREEN_WIDTH - 50:
            self.start_quiz(lambda correct: self.on_level_complete_quiz_result(correct))
            return

    def on_hurt_quiz_result(self, correct, monster):
        if correct:
            self.player.rect.x = max(0, self.player.rect.x - 50)
        else:
            self.player.lives -= 2
            if self.player.lives <= 0:
                self.start_quiz(lambda corr: self.on_death_quiz_result(corr))
            else:
                self.player.rect.x, self.player.rect.y = 100, 300
                self.player.velocity_y = 0
                # 死亡后显示鼓励剧情
                if self.story_gen:
                    story = self.story_gen.get_story('death')
                    self.story_bar.show(story)

    def on_level_complete_quiz_result(self, correct):
        if correct:
            if self.story_gen:
                story = self.story_gen.get_story('level_complete', self.level)
                self.story_bar.show(story)
            self.next_level()
        else:
            self.player.rect.x, self.player.rect.y = 100, 300
            self.player.velocity_y = 0
            self.game_state = "playing"

    def on_death_quiz_result(self, correct):
        if correct:
            self.player.lives = 1
            self.player.rect.x, self.player.rect.y = 100, 300
            self.player.velocity_y = 0
            self.game_state = "playing"
        else:
            self.game_state = "game_over"

    # ---------- 绘制 ----------
    def draw(self):
        self.screen.fill(BACKGROUND)
        for pos in [(100,80),(400,120),(650,60)]:
            pygame.draw.ellipse(self.screen, (200,220,240), (pos[0],pos[1],80,40))
            pygame.draw.ellipse(self.screen, (200,220,240), (pos[0]+20,pos[1]-20,70,40))
            pygame.draw.ellipse(self.screen, (200,220,240), (pos[0]+40,pos[1]+10,60,30))
        self.ground.draw(self.screen)
        for wall in self.walls: wall.draw(self.screen)
        for monster in self.monsters: monster.draw(self.screen)
        self.player.draw(self.screen, self.small_font)
        pygame.draw.rect(self.screen, RED, (SCREEN_WIDTH-60,300,10,200))
        pygame.draw.polygon(self.screen, (30,200,30), [(SCREEN_WIDTH-60,300),(SCREEN_WIDTH-60,340),(SCREEN_WIDTH-20,320)])
        lives_text = self.font.render(f"生命: {self.player.lives}", True, TEXT_COLOR)
        level_text = self.font.render(f"关卡: {self.level}", True, LEVEL_COLORS[(self.level-1)%len(LEVEL_COLORS)])
        score_text = self.font.render(f"积分: {score}", True, TEXT_COLOR)
        self.screen.blit(lives_text, (20,20)); self.screen.blit(level_text, (20,60)); self.screen.blit(score_text, (20,100))
        cd = self.player.skills['high_jump']['cooldown']
        cd_text = self.small_font.render(f"高跳冷却: {cd//10}" if cd>0 else "按 1 键高跳(花费5积分)", True, (255,200,0) if cd>0 else (100,255,100))
        self.screen.blit(cd_text, (20,140))
        tip = self.small_font.render("←→/AD 移动 | 空格/↑ 跳跃", True, (200,200,100))
        self.screen.blit(tip, (20,320))
        self.left_button.draw(self.screen); self.right_button.draw(self.screen); self.jump_button.draw(self.screen)
        if self.settings_button: self.settings_button.draw(self.screen, self.small_font)
        self.draw_quiz(self.screen)
        self.story_bar.draw(self.screen)  # 绘制底部剧情栏

        if self.game_state == "game_over":
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA); overlay.fill((0,0,0,180)); self.screen.blit(overlay, (0,0))
            title = self.font.render("游戏结束", True, RED); self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 150))
            for btn in self.game_over_buttons: btn.draw(self.screen, self.font)
        elif self.game_state == "next_level":
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA); overlay.fill((0,0,0,180)); self.screen.blit(overlay, (0,0))
            title = self.font.render(f"第 {self.level} 关完成！", True, GREEN); self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 150))
            for btn in self.next_level_buttons: btn.draw(self.screen, self.font)
        elif self.game_state == "settings":
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA); overlay.fill((0,0,0,180)); self.screen.blit(overlay, (0,0))
            title = self.font.render("设置", True, WHITE); self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 150))
            for btn in self.settings_buttons: btn.draw(self.screen, self.font)
            tip2 = self.small_font.render("按 ESC 或点击空白区域关闭", True, (200,200,200)); self.screen.blit(tip2, (SCREEN_WIDTH//2 - tip2.get_width()//2, 480))

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()

# ==================== 启动入口 ====================
if __name__ == "__main__":
    selector = SubjectSelector()
    result = selector.run()
    if result is None:
        print("未选择科目，退出程序。"); sys.exit(0)
    subject, grade, unit = result
    print(f"科目: {subject}, 年级: {grade}, 单元: {unit}")
    story_gen = StoryGenerator(subject, grade, unit)
    quiz_mgr = QuizManager(subject, grade, unit)
    game = Game(quiz_mgr, story_gen)
    game.run()
