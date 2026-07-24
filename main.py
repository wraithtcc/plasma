import math
import os
import shutil
import sys
import time

WINDOWS = os.name == "nt"

if WINDOWS:
    import msvcrt
else:
    import termios
    import tty
    import select

HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR = "\x1b[2J"
HOME = "\x1b[H"
RESET = "\x1b[0m"


def bg(v):
    return f"\x1b[48;2;{v};{v};{v}m"


def fg(v):
    return f"\x1b[38;2;{v};{v};{v}m"


CHARSET = " .:-=+*#%@"


def shade(v):
    return int(max(0, min(255, v * 255)))


def anim_plasma(x, y, t, w, h):
    v = 0.0
    v += math.sin(x * 0.10 + t)
    v += math.sin(y * 0.12 - t * 0.9)
    v += math.sin((x + y) * 0.08 + t * 1.3)
    cx = x + 20 * math.sin(t * 0.4)
    cy = y + 15 * math.cos(t * 0.35)
    v += math.sin(math.sqrt(cx * cx + cy * cy) * 0.15 - t * 1.5)
    return (v + 4) / 8.0


def anim_ripple(x, y, t, w, h):
    cx, cy = w * 0.25, h * 0.5
    d = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    v = math.sin(d * 0.3 - t * 3)
    return (v + 1) / 2


def anim_tunnel(x, y, t, w, h):
    cx, cy = w * 0.5, h * 0.5
    dx, dy = x - cx, y - cy
    dist = math.sqrt(dx * dx + dy * dy) + 0.001
    angle = math.atan2(dy, dx)
    v = math.sin(10 / (dist * 0.2 + 1) - t * 2 + angle * 3)
    return (v + 1) / 2


def anim_waves(x, y, t, w, h):
    v = math.sin(x * 0.15 + t * 2) * math.cos(y * 0.2 - t * 1.5)
    v += math.sin((x - y) * 0.1 + t)
    return (v + 2) / 4


def anim_noise_drift(x, y, t, w, h):
    v = math.sin(x * 0.3 + math.sin(t + y * 0.1) * 3)
    v += math.cos(y * 0.25 + math.cos(t * 0.7 + x * 0.08) * 3)
    return (v + 2) / 4


ANIMATIONS = [anim_plasma, anim_ripple, anim_tunnel, anim_waves, anim_noise_drift]


def render_frame(width, height, t, anim_fn, ascii_mode):
    out = [HOME]
    prev_color = None
    for row in range(height):
        y = row
        parts = []
        for col in range(width):
            x = col * 0.5
            val = anim_fn(x, y, t, width, height)
            val = max(0.0, min(1.0, val))
            v = shade(val)
            if ascii_mode:
                idx = int(val * (len(CHARSET) - 1))
                ch = CHARSET[idx]
                color = fg(v)
                if color != prev_color:
                    parts.append(color)
                    prev_color = color
                parts.append(ch)
            else:
                color = bg(v)
                if color != prev_color:
                    parts.append(color)
                    prev_color = color
                parts.append(" ")
        parts.append(RESET)
        prev_color = None
        out.append("".join(parts))
    return "\n".join(out)


def enable_windows_ansi():
    if not WINDOWS:
        return
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)


class RawInput:
    def __enter__(self):
        if not WINDOWS:
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *args):
        if not WINDOWS:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def get_key(self, timeout=0.0):
        if WINDOWS:
            end = time.time() + timeout
            while time.time() < end:
                if msvcrt.kbhit():
                    return msvcrt.getwch()
                time.sleep(0.005)
            return None
        else:
            r, _, _ = select.select([sys.stdin], [], [], timeout)
            if r:
                return sys.stdin.read(1)
            return None


def main():
    enable_windows_ansi()
    anim_idx = 0
    ascii_mode = True
    t = 0.0
    speed = 0.08
    paused = False
    switch_interval = 12.0
    last_switch = time.time()

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.write(CLEAR)
    try:
        with RawInput() as ri:
            while True:
                cols, rows = shutil.get_terminal_size(fallback=(80, 24))
                width = cols
                height = max(1, rows - 1)

                if not paused:
                    frame = render_frame(width, height, t, ANIMATIONS[anim_idx], ascii_mode)
                    sys.stdout.write(frame)
                    status = f"\n{RESET}\x1b[K"
                    sys.stdout.write(status)
                    sys.stdout.flush()
                    t += speed

                    if time.time() - last_switch > switch_interval:
                        anim_idx = (anim_idx + 1) % len(ANIMATIONS)
                        last_switch = time.time()
                        t = 0.0

                key = ri.get_key(timeout=0.03)
                if key:
                    if key == "q" or key == "\x03":
                        break
                    elif key == "n":
                        anim_idx = (anim_idx + 1) % len(ANIMATIONS)
                        t = 0.0
                        last_switch = time.time()
                    elif key == "a":
                        ascii_mode = not ascii_mode
                    elif key == " ":
                        paused = not paused
                    elif key == "+":
                        speed *= 1.3
                    elif key == "-":
                        speed /= 1.3
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.write(RESET + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.exit(1)
    try:
        main()
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR + RESET + "\n")
