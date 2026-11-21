"""비멍 배경 사진 만들기: 원본 사진에서 영역을 잘라 덱 전체 크기(980x588, 5:3)로 고품질 축소해 저장한다.

  python scripts/make_rain_photo.py <원본 사진> [x0,y0,x1,y1] [아이콘 x0,y0,x1,y1]

저장 위치: ~/.cache/d200/rain_photo.png (git 밖). 이 파일이 있으면 비멍이 사진 배경 + 빗줄기로 바뀌고,
지우면 원래 도트 비멍으로 돌아간다. 영역을 안 주면 가운데에서 5:3 으로 가장 크게 자른다.
아이콘 영역을 주면 그 부분을 둥근 정사각형 아이콘으로 ~/.cache/d200/icons/rain.png 에 저장한다
(홈 → 어항 고르기 화면의 비멍 칸 아이콘이 이걸로 바뀐다).
사진은 저장소에 넣지 않는다 (남의 사진을 공개 저장소에 올리면 재배포가 된다).
"""

from __future__ import annotations

import os
import sys

from PIL import Image

OUT = os.path.expanduser("~/.cache/d200/rain_photo.png")
ICON_OUT = os.path.expanduser("~/.cache/d200/icons/rain.png")
SIZE = (980, 588)  # 5칸 x 3칸 (196px)
ICON = 256  # 아이콘 원본 크기 (화면에서는 98px 로 줄여 쓴다)


def make_icon(img: Image.Image, box: tuple[int, ...]) -> None:
    from PIL import ImageDraw

    icon = img.crop(box).resize((ICON, ICON), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (ICON, ICON), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, ICON - 1, ICON - 1), ICON // 5, fill=255)
    icon.putalpha(mask)
    os.makedirs(os.path.dirname(ICON_OUT), exist_ok=True)
    icon.save(ICON_OUT)
    print(f"saved {ICON_OUT} from box {box}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    img = Image.open(sys.argv[1]).convert("RGB")
    if len(sys.argv) > 2:
        box = tuple(int(v) for v in sys.argv[2].split(","))
    else:  # 가운데 5:3
        w, h = img.size
        cw, ch = (w, w * 3 // 5) if w * 3 // 5 <= h else (h * 5 // 3, h)
        box = ((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.crop(box).resize(SIZE, Image.LANCZOS).save(OUT)
    print(f"saved {OUT} from box {box}")
    if len(sys.argv) > 3:
        make_icon(img, tuple(int(v) for v in sys.argv[3].split(",")))


if __name__ == "__main__":
    main()
