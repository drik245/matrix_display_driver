# 8×8 LED Matrix Display Driver for MicroPython

A lightweight, pure-GPIO driver for raw 8×8 LED matrix displays — no MUX chip required.
Works on **any MicroPython board**: Raspberry Pi Pico, ESP32, RP2040, STM32, and more.

---

## Features

| Feature | Details |
|---|---|
| **Raw GPIO scanning** | 8 row + 8 col pins, no shift register or dedicated IC |
| **Gamma-corrected brightness** | 16 levels (0–15), gamma-2.2 mapping for perceptual linearity |
| **Smooth fade / blink** | `fade_to_brightness()` and `blink()` helpers |
| **Scrolling text — blocking** | Pixel-column scroll with configurable speed |
| **Scrolling text — async** | Non-blocking scroll via pre-rendered frames + Timer |
| **Character display** | Full ASCII 32–127, auto-centred with `center_char()` |
| **Large-digit clock font** | 4×7 digits for `draw_large_number(n)` / `draw_large_time()` |
| **Shapes** | Line, rectangle, circle, triangle — outline or filled |
| **Progress bar** | Horizontal bar with fill level |
| **Framebuffer transforms** | `flip_h()`, `flip_v()`, `rotate_90()` |
| **Animation player** | `play_animation(frames, fps)` — blocking frame sequence |
| **Icon library** | 30 pre-built 8×8 bitmaps in `icons.py` |
| **Row/column write** | `set_row(y, mask)`, `set_col(x, mask)` for fast bulk ops |
| **Custom bitmaps** | Load any raw 8-byte pattern instantly |
| **REPL preview** | `print(matrix)` shows ASCII art of the framebuffer |
| **Universal** | Only `machine.Pin` + `machine.Timer` — standard MicroPython |
| **Common-anode/cathode** | Single `common_anode` flag switches polarity |

---

## File Layout

```
matrix_display_driver/
├── matrix.py       ← Main driver class          (copy to board)
├── font5x7.py      ← 5×7 ASCII font table       (copy to board)
├── icons.py        ← 30 pre-built 8×8 bitmaps   (copy to board)
└── example.py      ← Full feature demo           (optional)
```

---

## Quick Start

### 1 — Copy files to your board

Copy `matrix.py`, `font5x7.py`, and `icons.py` to the root of your MicroPython
board (e.g. via Thonny, mpremote, or rshell).

### 2 — Wire the matrix

```
Matrix pin   →  Board GPIO
──────────────────────────────────────────
ROW 1        →  GPIO 0   ← add 100–220 Ω resistors here
ROW 2        →  GPIO 1
...
ROW 8        →  GPIO 7
COL 1        →  GPIO 8
...
COL 8        →  GPIO 15
```

> **Common-cathode** (most bare modules): rows = anodes, columns = cathodes.
> **Common-anode**: pass `common_anode=True` to the constructor.

### 3 — Minimal usage

```python
from matrix import Matrix8x8
from icons import get_icon

ROW_PINS = [0, 1, 2, 3, 4, 5, 6, 7]   # ← edit these
COL_PINS = [8, 9, 10, 11, 12, 13, 14, 15]

m = Matrix8x8(ROW_PINS, COL_PINS)          # gamma=True by default

# Display an icon
m.draw_bitmap(get_icon('heart'))

# Scroll text (blocking)
m.scroll_text("Hello!", speed_ms=80)

# Async scroll — code keeps running
m.scroll_text_async("MicroPython rocks!  ", speed_ms=70)

# Large clock digits
m.draw_large_number(42)          # shows "42" in big font
m.draw_large_digit(7)            # shows "7" centred

# Shapes
m.draw_circle(3, 3, 3, fill=True)
m.draw_progress_bar(75)          # 75% full bar at bottom

# Brightness
m.fade_to_brightness(5)          # smooth ramp down
m.blink(times=2)                 # blink current image
```

---

## API Reference

### Constructor

```python
Matrix8x8(row_pins, col_pins,
          common_anode=False, frame_rate=50, timer_id=0, gamma=True)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `row_pins` | `list[int\|Pin]` | — | 8 GPIO pin numbers or Pin objects for rows |
| `col_pins` | `list[int\|Pin]` | — | 8 GPIO pin numbers or Pin objects for columns |
| `common_anode` | `bool` | `False` | True for common-anode matrices |
| `frame_rate` | `int` | `50` | Display refresh rate in Hz |
| `timer_id` | `int` | `0` | `machine.Timer` ID for scan timer |
| `gamma` | `bool` | `True` | Apply gamma-2.2 correction to brightness |

---

### Brightness

```python
m.set_brightness(level)              # 0=off, 15=max
m.get_brightness()                   # returns current level
m.fade_to_brightness(target,         # smooth ramp
                     steps=8,
                     delay_ms=30)
m.blink(times=3, on_ms=400,          # blink without clearing content
        off_ms=200)
```

**Gamma correction** maps the 16 perceptual levels through a γ=2.2 curve
so equal `set_brightness` steps look equally bright to the eye.

---

### Pixel Operations

```python
m.set_pixel(x, y, val=1)    # x=col 0-7, y=row 0-7
m.get_pixel(x, y)            # → 0 or 1
m.set_row(y, mask)           # write full row as 8-bit mask (bit7=col0)
m.set_col(x, mask)           # write full column as 8-bit mask (bit7=row0)
m.clear()                    # all off
m.fill()                     # all on
m.invert()                   # flip every pixel
m.draw_bitmap(bitmap)        # load 8-byte raw bitmap
```

---

### Transforms

```python
m.flip_h()                   # mirror left ↔ right
m.flip_v()                   # mirror top ↔ bottom
m.rotate_90(clockwise=True)  # rotate 90° CW or CCW
```

---

### Text

```python
# Single character — optionally auto-centred
m.draw_char('A', x_offset=0)
m.center_char('A')           # auto-centres a 5-wide glyph on 8 cols

# Blocking scroll
m.scroll_text("Hello!", speed_ms=80, repeat=False, padding=True, spacing=1)

# Non-blocking scroll (uses Timer timer_id, default 1)
m.scroll_text_async("Hello!", speed_ms=80, on_done=callback, timer_id=1)
m.stop_scroll()              # stop async scroll at any time

# Character slideshow
m.show_text("Hi", hold_ms=800)   # show each char, then clear
```

---

### Shapes

```python
m.draw_line(x0, y0, x1, y1)                         # Bresenham
m.draw_rect(x, y, w, h, fill=False)                 # rectangle
m.draw_circle(cx, cy, r, fill=False)                # midpoint circle
m.draw_triangle(x0,y0, x1,y1, x2,y2, fill=False)   # filled / outline
m.draw_progress_bar(value, max_val=100,              # horizontal bar
                    row=6, height=2, filled=True)
```

---

### Large Digits (clock font)

4-wide × 7-tall digits, two per screen.

```python
m.draw_large_digit(7)            # single digit, centred (x_offset=2)
m.draw_large_digit(3, x_offset=0)  # left-aligned
m.draw_large_number(42)          # "42" — uses full 8-col display
m.draw_large_time(12, 30)        # alternates "12" / "30" with colon blink
```

---

### Animation

```python
frames = [bitmap0, bitmap1, bitmap2, ...]   # list of 8-byte bitmaps
m.play_animation(frames, fps=5, repeat=False, loop_count=1)
```

---

### Icons

```python
from icons import get_icon, list_icons, ICONS

m.draw_bitmap(get_icon('heart'))
list_icons()     # print all 30 available names
```

**Available icons (30):**

| Group | Icons |
|---|---|
| Faces | `smiley` `sad` `neutral` `surprised` `wink` |
| Symbols | `heart` `broken_heart` `star` `diamond` `check` `cross` `exclaim` `question` |
| Arrows | `arrow_up` `arrow_down` `arrow_left` `arrow_right` |
| UI / Tech | `music` `bell` `lock` `wifi` `battery_full` `battery_half` `battery_low` `lightning` `clock` |
| Misc | `skull` `house` `power` `snowflake` `sun` `moon` `pac` `ghost` `plant` |

---

### Cleanup

```python
m.stop()     # deinit timers, blank display
```

---

## How Brightness Works

```
Timer ISR frequency = frame_rate × 8 rows × 16 steps
                    = 50 × 8 × 16 = 6 400 Hz  (156 µs period)

ISR logic per call  (integer only, no heap):
  if tick == 0 → switch to next row, set columns  (~8 pin writes)
  if tick < brightness → row ON   else row OFF     (1 pin write)
  tick = (tick + 1) & 15
```

**Gamma mapping** (γ = 2.2, 16 levels):

| Level | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ISR ticks | 0 | 0 | 0 | 0 | 1 | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 9 | 11 | 13 | 15 |

---

## Async Scroll Architecture

`scroll_text_async()` pre-renders every scroll frame into a flat `bytearray`
(8 bytes × N frames) so the Timer callback only performs **8 byte copies** per tick —
no string parsing, no font lookup, no heap allocation at call time.

```
Pre-render phase (on call):
  text → column list → N×8 byte frame array  (one-off cost)

Timer callback (every speed_ms ms):
  copy frame[pos * 8 : pos*8+8] → _buf       (8 byte writes)
  pos += 1
```

---

## Timing Budget

| Parameter | Value |
|---|---|
| Frame rate | 50 Hz |
| ISR frequency | 6 400 Hz |
| ISR period | 156 µs |
| Work per ISR | ≤ 9 pin.value() calls, O(1) |
| Async scroll callback | 8 byte copies, O(1) |
