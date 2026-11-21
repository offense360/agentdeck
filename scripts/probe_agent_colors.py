"""작업 현황 칸의 Claude / Codex 구분 방식 후보를 덱에 직접 띄운다 (모니터와 덱 LCD 색이 달라서).

  윗줄 = Claude, 가운데 줄 = Codex, 열(1~5) = 후보. 마음에 드는 열 번호를 고른다.
  대시보드를 끄고 실행한다 (장치를 같이 쓰면 화면이 섞인다).

  python scripts/probe_agent_colors.py [초=60]
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d200 import D200, SMALL_BACKGROUND, Button

BG, BLUE = "#1a1b26", "#7aa2f7"  # 작업 중 상태: 파란 테두리


def tile(name: str, agent: str, variant: int) -> Button:
    claude = agent == "C"
    b = Button(header=name, raw_header=True, title="작업 1", sub="C1 · 실행 1" if claude else "X1 · 실행 1",
               bg=BG, accent=BLUE, border=BLUE, name_first=True)
    if variant == 1:  # 이름 글씨 색: 주황 / 하늘
        b.header_fg = "#ff9933" if claude else "#5cc8ff"
    elif variant == 2:  # 이름 글씨 색: 주황 / 보라
        b.header_fg = "#ff9933" if claude else "#c08cff"
    elif variant == 3:  # 칸 배경 전체: 따뜻한 갈색 / 차가운 남색
        b.bg = "#4a2a12" if claude else "#0e2f4a"
    elif variant == 4:  # 이름 띠: 주황 띠 / 흰 띠 (글씨는 어둡게)
        b.header_bg, b.header_fg = ("#ff9933", "#16161e") if claude else ("#e6e9f5", "#16161e")
    elif variant == 5:  # 아래 줄에 이름 그대로 + 띠
        b.sub = "Claude · 실행 1" if claude else "Codex · 실행 1"
        b.header_bg, b.header_fg = ("#d9773f", "#16161e") if claude else ("#3a8fd9", "#16161e")
    return b


def main() -> None:
    sec = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    deck = D200()
    deck.start()
    deck.set_brightness(80)
    deck.set_small_window(SMALL_BACKGROUND)
    buttons = {}
    for col in range(5):
        buttons[col] = tile("jakeparkcolde-agentdeck", "C", col + 1)
        buttons[5 + col] = tile("puritysb-AgentDeck", "X", col + 1)
    deck.set_buttons(buttons)
    print(f"showing 5 candidates for {sec:.0f}s: top row = Claude, middle row = Codex, column = candidate 1..5", flush=True)
    try:
        time.sleep(sec)
    finally:
        deck.close()


if __name__ == "__main__":
    main()
