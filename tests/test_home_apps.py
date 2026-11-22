"""홈 앱 바로가기 (config home_apps): 첫 화면 배치 · OS 별 대상 · 넓은 칸 시계/업데이트 전환."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import dashboard

TERM = {"name": "터미널", "sub": "WT", "icon": "terminal",
        "open": {"windows": "wt.exe", "mac": "/System/Applications/Utilities/Terminal.app"}, "focus": "WindowsTerminal.exe"}


def items(apps, more=False):
    with patch.object(dashboard, "HOME_APPS", apps):
        return dashboard.Dashboard.home_items(SimpleNamespace(home_extra=[], home_more=more))


class HomeAppsTest(unittest.TestCase):
    def test_target_per_os(self):
        with patch.object(dashboard.platform_compat, "IS_WINDOWS", True), \
                patch.object(dashboard.platform_compat, "IS_MAC", False):
            self.assertEqual(dashboard.app_target(TERM), "wt.exe")
        with patch.object(dashboard.platform_compat, "IS_WINDOWS", False), \
                patch.object(dashboard.platform_compat, "IS_MAC", True):
            self.assertTrue(dashboard.app_target(TERM).endswith("Terminal.app"))
        self.assertEqual(dashboard.app_target({"open": "https://x"}), "https://x")
        with patch.object(dashboard.platform_compat, "IS_WINDOWS", True), \
                patch.object(dashboard.platform_compat, "IS_MAC", False):
            self.assertEqual(dashboard.app_target({"open": {"mac": "x"}}), "")  # 이 OS 대상이 없으면 빈 칸
        self.assertEqual(dashboard.app_target(None), "")

    def test_first_screen_layout(self):
        with patch.object(dashboard, "app_target", side_effect=lambda a: "x" if a else ""):
            first = items([TERM])
        self.assertEqual([p for p, *_ in first[:5]], [1, 2, 3, 4, 5])
        self.assertEqual(first[5][0], dashboard.APP_BASE)
        self.assertEqual([p for p, *_ in first[6:9]], [dashboard.EMPTY_SLOT] * 3)
        self.assertEqual(first[9][0], -1)  # 더보기
        self.assertEqual(len(first), 10)

    def test_more_screen_has_moved_pages(self):
        rest = items([TERM], more=True)
        pages = [p for p, *_ in rest]
        for pg in (6, dashboard.GAME_PAGE, dashboard.AQUA_PAGE, dashboard.PRES_PAGE):
            self.assertIn(pg, pages)
        self.assertEqual(pages[-1], -2)  # 처음으로

    def test_without_config_keeps_original_home(self):
        self.assertNotIn(dashboard.APP_BASE, [p for p, *_ in items(None)])
        self.assertIn(6, [p for p, *_ in items(None)])


class HomeNotePagesTest(unittest.TestCase):
    def test_pages_of_four(self):
        with patch.object(dashboard.updater, "status", return_value={"behind": 0}):
            for n, want in ((0, 1), (3, 1), (4, 1), (6, 2), (9, 3)):
                me = SimpleNamespace(home_notes=[f"n{i}" for i in range(n)])
                self.assertEqual(dashboard.Dashboard.home_note_pages(me), want)


if __name__ == "__main__":
    unittest.main()
