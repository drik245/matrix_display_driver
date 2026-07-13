# MicroPython 8x8 LED matrix driver - raw GPIO, no MUX chip
# Works on any MicroPython board (Pico, ESP32, RP2040, STM32, etc.)
# row_pins: 8 GPIO pins for rows (anodes on common-cathode, cathodes on common-anode)
# col_pins: 8 GPIO pins for columns (cathodes on CC, anodes on CA)
# Timer ISR scans rows at frame_rate * 8 * 16 Hz - brightness via tick counter PWM

import utime
from machine import Pin, Timer
from font5x7 import get_glyph

try:
    from micropython import const
except ImportError:
    def const(x): return x

_BL = const(16)  # brightness levels
_SZ = const(8)   # matrix size

# gamma 2.2 lookup: maps user brightness 0-15 to ISR tick count
_GAMMA = (0, 0, 0, 0, 1, 1, 2, 3, 4, 5, 6, 8, 9, 11, 13, 15)

# large digit font, 4 cols wide x 7 rows + 1 blank
# each byte uses top nibble only (bits 7-4 = cols 0-3)
# to place at x_offset: byte >> x_offset
_LARGE = (
    bytes([0x60,0x90,0x90,0x90,0x90,0x90,0x60,0x00]),  # 0
    bytes([0x20,0x60,0x20,0x20,0x20,0x20,0x70,0x00]),  # 1
    bytes([0x60,0x90,0x10,0x20,0x40,0x80,0xF0,0x00]),  # 2
    bytes([0xE0,0x10,0x10,0x60,0x10,0x10,0xE0,0x00]),  # 3
    bytes([0x90,0x90,0x90,0xF0,0x10,0x10,0x10,0x00]),  # 4
    bytes([0xF0,0x80,0xE0,0x10,0x10,0x10,0xE0,0x00]),  # 5
    bytes([0x60,0x80,0xE0,0x90,0x90,0x90,0x60,0x00]),  # 6
    bytes([0xF0,0x10,0x20,0x20,0x40,0x40,0x40,0x00]),  # 7
    bytes([0x60,0x90,0x90,0x60,0x90,0x90,0x60,0x00]),  # 8
    bytes([0x60,0x90,0x90,0x70,0x10,0x10,0x60,0x00]),  # 9
)


class Matrix8x8:
    """8x8 LED matrix driver. row_pins and col_pins are lists of 8 GPIO numbers."""

    def __init__(self, row_pins, col_pins,
                 common_anode=False, frame_rate=50, timer_id=0, gamma=True):
        if len(row_pins) != _SZ or len(col_pins) != _SZ:
            raise ValueError("need exactly 8 row and 8 col pins")

        self._rows = [Pin(p, Pin.OUT) for p in row_pins] \
                     if isinstance(row_pins[0], int) else list(row_pins)
        self._cols = [Pin(p, Pin.OUT) for p in col_pins] \
                     if isinstance(col_pins[0], int) else list(col_pins)

        self._row_on  = 0 if common_anode else 1
        self._row_off = 1 if common_anode else 0
        self._col_on  = 1 if common_anode else 0
        self._col_off = 0 if common_anode else 1

        # framebuffer: buf[row] byte, bit7=col0 ... bit0=col7
        self._buf = bytearray(_SZ)

        self._gamma      = gamma
        self._level      = _BL - 1
        self._brightness = _BL - 1  # ISR tick threshold

        # ISR counters - pre-allocated, no heap inside ISR
        self._cur_row = 0
        self._tick    = 0

        # async scroll state
        self._scroll_timer  = None
        self._scroll_frames = None
        self._scroll_pos    = 0
        self._scroll_total  = 0
        self._scroll_cb     = None

        self._all_off()
        self._timer = Timer(timer_id)
        self._timer.init(freq=frame_rate * _SZ * _BL,
                         mode=Timer.PERIODIC, callback=self._isr)

    def _all_off(self):
        for r in self._rows: r.value(self._row_off)
        for c in self._cols: c.value(self._col_off)

    def _isr(self, _t):
        # called at frame_rate * 8 * 16 Hz - keep this lean, no heap
        tick = self._tick

        if tick == 0:
            # deactivate previous row first (break-before-make avoids ghosting)
            self._rows[self._cur_row].value(self._row_off)
            for c in self._cols: c.value(self._col_off)

            self._cur_row = (self._cur_row + 1) & 0x07
            row_data = self._buf[self._cur_row]
            for bit in range(_SZ):
                pixel = (row_data >> (7 - bit)) & 1
                self._cols[bit].value(self._col_on if pixel else self._col_off)

        # PWM duty cycle
        if tick < self._brightness:
            self._rows[self._cur_row].value(self._row_on)
        else:
            self._rows[self._cur_row].value(self._row_off)

        self._tick = (tick + 1) & (_BL - 1)

    def _scroll_tick(self, _t):
        # scroll timer callback - just copies 8 bytes from pre-rendered frames
        pos = self._scroll_pos
        if pos >= self._scroll_total:
            self.stop_scroll()
            if self._scroll_cb:
                self._scroll_cb()
            return
        base = pos * _SZ
        frames = self._scroll_frames
        for i in range(_SZ):
            self._buf[i] = frames[base + i]
        self._scroll_pos = pos + 1

    # brightness

    def set_brightness(self, level):
        """0 = off, 15 = max."""
        level = max(0, min(_BL - 1, int(level)))
        self._level = level
        self._brightness = _GAMMA[level] if self._gamma else level

    def get_brightness(self):
        return self._level

    def fade_to_brightness(self, target, steps=8, delay_ms=30):
        """Smoothly ramp to target brightness."""
        start = self._level
        target = max(0, min(_BL - 1, int(target)))
        for i in range(1, steps + 1):
            self.set_brightness(start + (target - start) * i // steps)
            utime.sleep_ms(delay_ms)

    def blink(self, times=3, on_ms=400, off_ms=200):
        """Blink the display without touching the framebuffer."""
        saved = self._level
        for _ in range(times):
            self.set_brightness(saved)
            utime.sleep_ms(on_ms)
            self.set_brightness(0)
            utime.sleep_ms(off_ms)
        self.set_brightness(saved)

    # pixel ops

    def set_pixel(self, x, y, val=1):
        if 0 <= x < _SZ and 0 <= y < _SZ:
            if val: self._buf[y] |=  (1 << (7 - x))
            else:   self._buf[y] &= ~(1 << (7 - x))

    def get_pixel(self, x, y):
        if 0 <= x < _SZ and 0 <= y < _SZ:
            return (self._buf[y] >> (7 - x)) & 1
        return 0

    def set_row(self, y, data):
        """Write a full row as an 8-bit mask (bit7 = col0)."""
        if 0 <= y < _SZ:
            self._buf[y] = data & 0xFF

    def set_col(self, x, data):
        """Write a full column as an 8-bit mask (bit7 = row0)."""
        if 0 <= x < _SZ:
            mask = 1 << (7 - x)
            for row in range(_SZ):
                if (data >> (7 - row)) & 1: self._buf[row] |=  mask
                else:                        self._buf[row] &= ~mask

    def clear(self):
        for i in range(_SZ): self._buf[i] = 0x00

    def fill(self):
        for i in range(_SZ): self._buf[i] = 0xFF

    def invert(self):
        for i in range(_SZ): self._buf[i] ^= 0xFF

    def draw_bitmap(self, bitmap):
        """Load an 8-byte bitmap. MSB of each byte = col 0."""
        for i in range(_SZ): self._buf[i] = bitmap[i] & 0xFF

    # transforms

    def flip_h(self):
        """Mirror left-right."""
        for row in range(_SZ):
            b, rev = self._buf[row], 0
            for _ in range(8):
                rev = (rev << 1) | (b & 1)
                b >>= 1
            self._buf[row] = rev

    def flip_v(self):
        """Mirror top-bottom."""
        for i in range(_SZ // 2):
            self._buf[i], self._buf[_SZ - 1 - i] = \
                self._buf[_SZ - 1 - i], self._buf[i]

    def rotate_90(self, clockwise=True):
        """Rotate 90 degrees CW or CCW."""
        new_buf = bytearray(_SZ)
        for y in range(_SZ):
            for x in range(_SZ):
                sx, sy = (y, _SZ-1-x) if clockwise else (_SZ-1-y, x)
                if (self._buf[sy] >> (7 - sx)) & 1:
                    new_buf[y] |= (1 << (7 - x))
        for i in range(_SZ): self._buf[i] = new_buf[i]

    # shapes

    def draw_line(self, x0, y0, x1, y1):
        """Bresenham line."""
        dx, dy = abs(x1-x0), abs(y1-y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.set_pixel(x0, y0)
            if x0 == x1 and y0 == y1: break
            e2 = err * 2
            if e2 > -dy: err -= dy; x0 += sx
            if e2 <  dx: err += dx; y0 += sy

    def draw_rect(self, x, y, w, h, fill=False):
        if fill:
            for row in range(y, y+h):
                for col in range(x, x+w): self.set_pixel(col, row)
        else:
            for col in range(x, x+w):
                self.set_pixel(col, y); self.set_pixel(col, y+h-1)
            for row in range(y, y+h):
                self.set_pixel(x, row); self.set_pixel(x+w-1, row)

    def draw_circle(self, cx, cy, r, fill=False):
        """Midpoint circle algorithm."""
        x, y, d = 0, r, 1 - r

        def _sym(px, py):
            if fill:
                self.draw_line(cx-px, cy+py, cx+px, cy+py)
                self.draw_line(cx-px, cy-py, cx+px, cy-py)
                self.draw_line(cx-py, cy+px, cx+py, cy+px)
                self.draw_line(cx-py, cy-px, cx+py, cy-px)
            else:
                for p, q in ((px,py),(-px,py),(px,-py),(-px,-py),
                             (py,px),(-py,px),(py,-px),(-py,-px)):
                    self.set_pixel(cx+p, cy+q)

        _sym(x, y)
        while x < y:
            x += 1
            d += (2*x+1) if d < 0 else (2*(x-y)+1)
            if d >= 0: y -= 1
            _sym(x, y)

    def draw_triangle(self, x0, y0, x1, y1, x2, y2, fill=False):
        if not fill:
            self.draw_line(x0,y0,x1,y1)
            self.draw_line(x1,y1,x2,y2)
            self.draw_line(x2,y2,x0,y0)
        else:
            verts = sorted([(y0,x0),(y1,x1),(y2,x2)])
            (ya,xa),(yb,xb),(yc,xc) = verts

            def _interp(y, ay, ax, by, bx):
                if by == ay: return ax
                return ax + (bx-ax)*(y-ay)//(by-ay)

            for row in range(ya, yc+1):
                lx = _interp(row,ya,xa,yb,xb) if row < yb else _interp(row,yb,xb,yc,xc)
                rx = _interp(row,ya,xa,yc,xc)
                if lx > rx: lx, rx = rx, lx
                for col in range(lx, rx+1): self.set_pixel(col, row)

    def draw_progress_bar(self, value, max_val=100, row=6, height=2, filled=True):
        """Horizontal progress bar. row = top row of bar."""
        n = int(value * _SZ / max(1, max_val))
        n = max(0, min(_SZ, n))
        for r in range(row, min(row+height, _SZ)):
            for col in range(_SZ):
                if filled:
                    self.set_pixel(col, r, 1 if col < n else 0)
                else:
                    on = col == 0 or col == _SZ-1 or r == row or r == row+height-1 or col < n
                    self.set_pixel(col, r, 1 if on else 0)

    # text

    def _build_columns(self, text, spacing=1):
        cols = []
        for i, ch in enumerate(text):
            cols.extend(get_glyph(ch))
            if i < len(text) - 1:
                cols.extend([0x00] * spacing)
        return cols

    def draw_char(self, char, x_offset=0):
        """Draw one character at x_offset (can be negative)."""
        self.clear()
        for ci, cd in enumerate(get_glyph(char)):
            sx = x_offset + ci
            if 0 <= sx < _SZ:
                for row in range(_SZ):
                    self.set_pixel(sx, row, (cd >> (7-row)) & 1)

    def center_char(self, char):
        """Draw character centred on the display."""
        self.draw_char(char, x_offset=1)  # 5-wide glyph, (8-5)//2 = 1

    def scroll_text(self, text, speed_ms=80, repeat=False, padding=True, spacing=1):
        """Scroll text blocking."""
        cols = self._build_columns(text, spacing)
        if padding:
            cols = [0x00]*_SZ + cols + [0x00]*_SZ
        total = len(cols)

        def _once():
            for start in range(max(0, total-_SZ+1)):
                for col in range(_SZ):
                    cd = cols[start+col] if start+col < total else 0
                    for row in range(_SZ):
                        self.set_pixel(col, row, (cd >> (7-row)) & 1)
                utime.sleep_ms(speed_ms)

        if repeat:
            while True: _once()
        else:
            _once()

    def scroll_text_async(self, text, speed_ms=80, on_done=None,
                          padding=True, spacing=1, timer_id=1):
        """Non-blocking scroll. Pre-renders all frames, callback just copies 8 bytes."""
        self.stop_scroll()
        cols = self._build_columns(text, spacing)
        if padding:
            cols = [0x00]*_SZ + cols + [0x00]*_SZ
        total = len(cols)
        n_frames = max(0, total-_SZ+1)

        # pre-render every frame into a flat bytearray
        frames = bytearray(n_frames * _SZ)
        for f in range(n_frames):
            for col in range(_SZ):
                cd = cols[f+col] if f+col < total else 0
                for row in range(_SZ):
                    if (cd >> (7-row)) & 1:
                        frames[f*_SZ + row] |= (1 << (7-col))

        self._scroll_frames = frames
        self._scroll_pos    = 0
        self._scroll_total  = n_frames
        self._scroll_cb     = on_done

        self._scroll_timer = Timer(timer_id)
        self._scroll_timer.init(period=max(10, speed_ms),
                                mode=Timer.PERIODIC, callback=self._scroll_tick)

    def stop_scroll(self):
        if self._scroll_timer is not None:
            self._scroll_timer.deinit()
            self._scroll_timer = None

    def show_text(self, text, hold_ms=800):
        """Show each character in turn then clear."""
        for ch in text:
            self.center_char(ch)
            utime.sleep_ms(hold_ms)
        self.clear()

    # large digit clock font

    def _draw_large_digit_at(self, digit, x_offset):
        glyph = _LARGE[digit % 10]
        for row, byte in enumerate(glyph):
            self._buf[row] |= (byte >> x_offset) & 0xFF

    def draw_large_digit(self, digit, x_offset=2):
        """Single large digit, centred by default."""
        self.clear()
        self._draw_large_digit_at(digit, x_offset)

    def draw_large_number(self, n):
        """Show 0-99 as two large digits filling the display."""
        n = max(0, min(99, int(n)))
        self.clear()
        self._draw_large_digit_at(n // 10, 0)  # left half
        self._draw_large_digit_at(n % 10,  4)  # right half

    def draw_large_time(self, hours, minutes):
        """Alternate hours and minutes with a centre-pixel colon blink."""
        self.draw_large_number(hours % 24)
        utime.sleep_ms(900)
        self._buf[2] |= 0x18  # colon dots
        self._buf[4] |= 0x18
        utime.sleep_ms(100)
        self.draw_large_number(minutes % 60)
        utime.sleep_ms(900)
        self.draw_large_number(hours % 24)

    # animation

    def play_animation(self, frames, fps=5, repeat=False, loop_count=1):
        """Play a list of 8-byte bitmaps at fps. Blocking."""
        delay_ms = max(1, 1000 // fps)
        def _once():
            for frame in frames:
                self.draw_bitmap(frame)
                utime.sleep_ms(delay_ms)
        if repeat:
            while True: _once()
        else:
            for _ in range(loop_count): _once()

    # cleanup

    def stop(self):
        """Stop timers and blank the display."""
        self.stop_scroll()
        self._timer.deinit()
        self._all_off()

    def __del__(self):
        try: self.stop()
        except: pass

    def __repr__(self):
        lines = ["┌────────┐"]
        for row in range(_SZ):
            line = "│"
            for col in range(_SZ):
                line += "█" if self.get_pixel(col, row) else "·"
            lines.append(line + "│")
        lines.append("└────────┘")
        return "\n".join(lines)
