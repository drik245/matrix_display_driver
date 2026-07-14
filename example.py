# full feature demo for the 8x8 matrix driver
# edit ROW_PINS and COL_PINS to match your board before running

from matrix import Matrix8x8
from icons import ICONS, get_icon, list_icons
import utime

ROW_PINS     = [0, 1, 2, 3, 4, 5, 6, 7]    # change these
COL_PINS     = [8, 9, 10, 11, 12, 13, 14, 15]
COMMON_ANODE = False   # True if your module has a common anode
FRAME_RATE   = 50

m = Matrix8x8(ROW_PINS, COL_PINS, common_anode=COMMON_ANODE,
              frame_rate=FRAME_RATE, gamma=True)

def pause(ms): utime.sleep_ms(ms)

list_icons()

# 1. gamma brightness fade
m.fill()
m.fade_to_brightness(0, steps=15, delay_ms=40)
m.fade_to_brightness(15, steps=15, delay_ms=40)
m.set_brightness(12)
m.clear(); pause(300)

# 2. blink
m.fill()
m.blink(times=3, on_ms=300, off_ms=150)
m.clear(); pause(300)

# 3. icon slideshow
for name in ['smiley','heart','star','music','lightning','clock','wifi',
             'battery_full','skull','ghost','arrow_up','arrow_right',
             'arrow_down','arrow_left','sun','moon','snowflake','pac',
             'check','cross']:
    m.draw_bitmap(get_icon(name))
    pause(500)
m.clear(); pause(300)

# 4. transforms
m.draw_bitmap(ICONS['arrow_up'])
for _ in range(4):
    pause(700)
    m.rotate_90(clockwise=True)
pause(300)

m.draw_bitmap(ICONS['smiley'])
pause(600); m.flip_h(); pause(600)
m.flip_v(); pause(600)
m.flip_v(); m.flip_h()  # restore
m.clear(); pause(300)

# 5. animation - bouncing ball
def ball_frames():
    frames = []
    for row in list(range(8)) + list(range(6, -1, -1)):
        f = bytearray(8)
        f[row] = 0x18
        frames.append(bytes(f))
    return frames

m.play_animation(ball_frames(), fps=8, loop_count=3)

# heart pulse
big   = ICONS['heart']
small = bytes([0,0x24,0x7E,0x7E,0x3C,0x18,0,0])
m.play_animation([big, small] * 4, fps=4)
m.clear(); pause(300)

# 6. blocking scroll
m.scroll_text("Hello, World!  ", speed_ms=70)
m.clear(); pause(200)

# 7. async scroll - other work runs while text scrolls
done = [False]
def on_done(): done[0] = True

m.scroll_text_async("Async scroll!  MicroPython 8x8  ",
                    speed_ms=65, on_done=on_done, timer_id=-1)

ticks = 0
while not done[0]:
    ticks += 1
    utime.sleep_ms(10)
print("scroll done, ticks:", ticks)
m.clear(); pause(300)

# 8. centred characters
for ch in "AbCd0123456789":
    m.center_char(ch)
    pause(300)
m.clear(); pause(200)

# 9. large digit clock font
for d in range(10):
    m.draw_large_digit(d)
    pause(400)

for n in range(0, 100, 7):
    m.draw_large_number(n)
    pause(350)
m.clear(); pause(300)

# 10. progress bar
for pct in range(0, 101, 5):
    m.clear()
    m.draw_char('P', x_offset=2)
    m.draw_progress_bar(pct, max_val=100, row=6, height=2, filled=True)
    pause(60)
pause(500)

# 11. shapes - outline
m.clear(); m.draw_line(0,0,7,7); m.draw_line(0,7,7,0); pause(800)
m.clear(); m.draw_rect(1,1,6,6); pause(800)
m.clear(); m.draw_circle(3,3,3); pause(800)
m.clear(); m.draw_triangle(3,0,7,7,0,7); pause(800)

# shapes - filled
m.clear(); m.draw_rect(1,1,6,6,fill=True); pause(800)
m.clear(); m.draw_circle(3,3,3,fill=True); pause(800)
m.clear(); m.draw_triangle(3,0,7,7,0,7,fill=True); pause(800)

# 12. set_row / set_col
m.clear()
for r in range(8): m.set_row(r, 0xFF); pause(80)
for r in range(8): m.set_row(r, 0x00); pause(80)
for c in range(8): m.set_col(c, 0xFF); pause(80)
for c in range(8): m.set_col(c, 0x00); pause(80)

# 13. invert + REPL preview
m.draw_bitmap(ICONS['smiley'])
print(m)
pause(600)
m.invert()
print(m)
pause(600)

# 14. goodbye
m.scroll_text("  Bye!  MicroPython  8x8  ", speed_ms=60)
m.clear()
m.stop()
