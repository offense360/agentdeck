"""요약(1페이지) 리셋 칸: 누를 때마다 다른 서비스·창의 리셋을 차례로 보여 준다."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pages
from pages import LLM, Limit

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


def llms(claude_week=0.98, codex_week=1.0):
    return [
        LLM("CLAUDE", "#d97757", five=Limit(None, None, 5 * H), week=Limit(claude_week, NOW + 87 * H, 168 * H)),
        LLM("CODEX", "#10a37f", week=Limit(codex_week, NOW + 146 * H, 168 * H)),
    ]


class ResetTileTest(unittest.TestCase):
    def test_default_is_next_used_reset(self):
        b = pages.reset_tile(llms(), NOW, 0)
        self.assertEqual(b.header, "다음 리셋")
        self.assertEqual(b.sub, "CLAUDE 주간")

    def test_press_shows_other_services_then_wraps(self):
        b1 = pages.reset_tile(llms(), NOW, 1)
        self.assertEqual(b1.header, "리셋 2/2")
        self.assertEqual(b1.sub, "CODEX 주간 · 안 씀")  # 아직 안 쓴 창도 보여 준다
        self.assertEqual(pages.reset_tile(llms(), NOW, 2).header, "다음 리셋")  # 한 바퀴 돌면 처음으로

    def test_nothing_used_keeps_blank_until_pressed(self):
        data = llms(claude_week=1.0, codex_week=1.0)
        self.assertIsNone(pages.reset_tile(data, NOW, 0).header or None)  # 원래처럼 빈 칸
        self.assertEqual(pages.reset_tile(data, NOW, 1).header, "리셋 1/2")
        self.assertEqual(pages.reset_tile(data, NOW, 3).header, "")  # 다시 빈 칸 (한 바퀴)

    def test_soonest_used_first_then_time_order(self):
        data = llms(claude_week=1.0, codex_week=0.5)  # Codex 만 씀 → 다음 리셋은 Codex
        items = pages.reset_list(data, NOW)
        self.assertEqual([(n, l) for n, l, *_ in items], [("CODEX", "주간"), ("CLAUDE", "주간")])

    def test_summary_page_uses_pick(self):
        p = pages.page_summary(llms(), pages.StudioState(False, []), NOW, reset_pick=1)
        self.assertEqual(p[4].header, "리셋 2/2")


if __name__ == "__main__":
    unittest.main()
