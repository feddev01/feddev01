"""Build the animated tmux-style profile card (dark_mode.svg / light_mode.svg).

Edit PROFILE below, then run: python3 scripts/build.py
The face comes from face.light.txt / face.dark.txt (see scripts/make_ascii.py).
GitHub stats come from stats.json, if present (see scripts/stats.py).
"""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent

USER = "mohan"
HOST = "feddev01"

# Each entry is one command typed in the right-hand pane, followed by its output.
# Output lines are (key, value) pairs, or plain strings.
PROFILE = [
    ("whoami", ["Mohan"]),
    ("cat about.yml", [
        ("role", "Frontend Developer"),
        ("location", "Nepal"),
        ("learning", "Next.js, TypeScript, Vercel"),
        ("exploring", "Linux, AI tools"),
        ("hobbies", "Photography, Hiking, Riding"),
    ]),
    ("ls stack/", ["html/  css/  javascript/  react/  php/  liquid/",
                   "shopify/  magento2/  wordpress/  git/"]),
    ("cat contact.txt", [
        ("github", "github.com/feddev01"),
        ("email", "feddev01@gmail.com"),
        ("codepen", "https://codepen.io/khadkamhn"),
    ]),
]

THEMES = {
    "dark": dict(bg="#0d1117", bar="#161b22", border="#30363d", fg="#c9d1d9", dim="#8b949e",
                 prompt="#7ee787", path="#79c0ff", key="#ffa657", value="#a5d6ff",
                 status_bg="#3fb950", status_fg="#0d1117", face="#c9d1d9"),
    "light": dict(bg="#ffffff", bar="#f6f8fa", border="#d0d7de", fg="#24292f", dim="#6e7781",
                  prompt="#1a7f37", path="#0969da", key="#bc4c00", value="#0a3069",
                  status_bg="#1a7f37", status_fg="#ffffff", face="#24292f"),
}

FS = 14            # font size
LH = 18            # line height
CW = FS * 0.6      # monospace character width
W = 1000
TITLE_H = 34
STATUS_H = 24
SPLIT = 510        # x of the pane divider
PAD = 14

TYPE_SPEED = 0.06  # seconds per typed character
LINE_SPEED = 0.05  # seconds between revealed output lines
FACE_FS = 8        # the face uses a smaller font so it can have more detail
FACE_LH = 9        # FACE_LH / (FACE_FS * 0.6) must match CHAR_ASPECT in make_ascii.py
FACE_SPEED = 0.03  # seconds between revealed face lines


class Card:
    def __init__(self, t):
        self.t = t
        self.body = []

    def show(self, x, y, inner, delay, cls=""):
        """A line that appears at `delay` seconds."""
        self.body.append(
            f'<text x="{x}" y="{y}" class="l {cls}" style="animation-delay:{delay:.2f}s">{inner}</text>')

    def prompt(self, x, y, cmd, delay):
        """A shell prompt where `cmd` types itself out; returns the time typing ends."""
        t = self.t
        prompt = (f'<tspan fill="{t["prompt"]}">{USER}@{HOST}</tspan>'
                  f'<tspan fill="{t["fg"]}">:</tspan><tspan fill="{t["path"]}">~</tspan>'
                  f'<tspan fill="{t["fg"]}">$ </tspan>')
        self.show(x, y, prompt + f'<tspan fill="{t["fg"]}">{escape(cmd)}</tspan>', delay)
        start = x + len(f"{USER}@{HOST}:~$ ") * CW
        width = len(cmd) * CW
        typing = len(cmd) * TYPE_SPEED
        begin = delay + 0.4
        # A background-coloured cover with a cursor on its left edge slides right in steps.
        self.body.append(
            f'<g class="type" style="--w:{width:.1f}px;animation:type {typing:.2f}s steps({len(cmd)}) '
            f'{begin:.2f}s forwards">'
            f'<rect x="{start:.1f}" y="{y - FS + 1}" width="{width + CW + 2:.1f}" height="{LH}" fill="{t["bg"]}"/>'
            f'<rect x="{start:.1f}" y="{y - FS + 1}" width="{CW:.1f}" height="{LH - 2}" fill="{t["fg"]}" '
            f'class="cur" style="animation-delay:{delay:.2f}s;animation-duration:{begin + typing - delay:.2f}s"/></g>')
        return begin + typing + 0.25

    def kv(self, key, value):
        t = self.t
        return (f'<tspan fill="{t["key"]}">{escape(key)}</tspan><tspan fill="{t["dim"]}">: </tspan>'
                f'<tspan fill="{t["value"]}">{escape(value)}</tspan>')


def stats_command():
    """The `gh stats` command, from stats.json; None when there are no stats yet."""
    path = ROOT / "stats.json"
    if not path.exists():
        return None
    s = json.loads(path.read_text())
    if "error" in s:
        return ("gh stats", [
            ("uptime", f"{s['uptime']} on GitHub"),
            ("PRs", "404 · stats not found"),
            ("repos", "404 · try again tomorrow"),
            ("status", f"error {s['error']}"),
        ])
    return ("gh stats", [
        ("uptime", f"{s['uptime']} on GitHub"),
        ("PRs", f"{s['prs']:,} opened · {s['merged']:,} merged"),
        ("repos", f"{s['contributed']} contributed to · {s['owned']} owned"),
        ("status", f"200 OK · updated {s['updated']}"),
    ])


def build(theme):
    t = THEMES[theme]
    face = (ROOT / f"face.{theme}.txt").read_text().rstrip("\n").split("\n")
    top = TITLE_H + PAD + FS
    face_top = top + LH // 2
    H = face_top + len(face) * FACE_LH + PAD + STATUS_H
    c = Card(t)

    # Left pane: print the face.
    clock = c.prompt(PAD, top, "cat face.txt", 0.2)
    face_x = (SPLIT - max(map(len, face)) * FACE_FS * 0.6) / 2
    for i, row in enumerate(face):
        c.show(f"{face_x:.1f}", face_top + (i + 1) * FACE_LH, escape(row), clock + i * FACE_SPEED, "face")
    clock += len(face) * FACE_SPEED + 0.3

    # Right pane: the profile commands.
    x, y = SPLIT + PAD, top
    for cmd, output in PROFILE + [cmd for cmd in [stats_command()] if cmd]:
        clock = c.prompt(x, y, cmd, clock)
        for line in output:
            y += LH
            inner = c.kv(*line) if isinstance(line, tuple) else f'<tspan fill="{t["fg"]}">{escape(line)}</tspan>'
            c.show(x, y, inner, clock)
            clock += LINE_SPEED
        y += LH * 2
        clock += 0.3

    # Final idle prompt with a blinking cursor.
    c.show(x, y, f'<tspan fill="{t["prompt"]}">{USER}@{HOST}</tspan><tspan fill="{t["fg"]}">:</tspan>'
                 f'<tspan fill="{t["path"]}">~</tspan><tspan fill="{t["fg"]}">$ </tspan>', clock)
    cx = x + len(f"{USER}@{HOST}:~$ ") * CW
    c.body.append(f'<rect x="{cx:.1f}" y="{y - FS + 1}" width="{CW:.1f}" height="{LH - 2}" fill="{t["fg"]}" '
                  f'class="l blink" style="animation-delay:{clock:.2f}s,{clock:.2f}s"/>')

    status_y = H - STATUS_H
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace" font-size="{FS}px">
<style>
text {{ white-space: pre; }}
.l {{ opacity: 0; animation: show 0s forwards; }}
.face {{ fill: {t["face"]}; font-size: {FACE_FS}px; }}
.cur {{ opacity: 0; animation-name: cur; }}
.blink {{ animation: show 0s forwards, blink 1s step-end infinite; }}
@keyframes show {{ to {{ opacity: 1; }} }}
@keyframes cur {{ from, to {{ opacity: 1; }} }}
@keyframes type {{ to {{ transform: translateX(var(--w)); }} }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
@media (prefers-reduced-motion: reduce) {{
  .l, .blink {{ opacity: 1; animation: none; }}
  .cur {{ animation: none; }}
  .type {{ display: none; }}
}}
</style>
<rect width="{W}" height="{H}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>
<path d="M0 12 a12 12 0 0 1 12 -12 h{W - 24} a12 12 0 0 1 12 12 v{TITLE_H - 12} h-{W} z" fill="{t["bar"]}"/>
<line x1="0" y1="{TITLE_H}" x2="{W}" y2="{TITLE_H}" stroke="{t["border"]}"/>
<circle cx="20" cy="17" r="6" fill="#ff5f57"/><circle cx="40" cy="17" r="6" fill="#febc2e"/><circle cx="60" cy="17" r="6" fill="#28c840"/>
<text x="{W / 2}" y="22" text-anchor="middle" fill="{t["dim"]}">{USER}@{HOST}: ~ — tmux</text>
<line x1="{SPLIT}" y1="{TITLE_H}" x2="{SPLIT}" y2="{status_y}" stroke="{t["border"]}"/>
{chr(10).join(c.body)}
<path d="M0 {status_y} h{W} v{STATUS_H - 12} a12 12 0 0 1 -12 12 h-{W - 24} a12 12 0 0 1 -12 -12 z" fill="{t["status_bg"]}"/>
<text x="{PAD}" y="{status_y + 16}" fill="{t["status_fg"]}">[{HOST}] 0:face  1:profile*</text>
<text x="{W - PAD}" y="{status_y + 16}" text-anchor="end" fill="{t["status_fg"]}">github.com/{HOST}</text>
</svg>
'''


if __name__ == "__main__":
    if "--help" in sys.argv[1:]:
        print(__doc__.strip())
        sys.exit(0)
    for theme in THEMES:
        out = ROOT / f"{theme}_mode.svg"
        out.write_text(build(theme))
        print(f"wrote {out.name}")
