"""platform_compat · 훅 상태 수집이 지금 OS(특히 Windows)에서 제대로 도는지 확인한다."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import platform_compat as pc


class FontTest(unittest.TestCase):
    def test_fonts_exist_and_load(self):
        from PIL import ImageFont

        for kind in ("kr", "rounded"):
            for w in pc.WEIGHTS:
                path, index = pc.font_file(kind, w)
                self.assertTrue(os.path.exists(path), f"{kind}/{w}: {path}")
                ImageFont.truetype(path, 20, index=index)
        f = pc.truetype("kr", 24, "bold")
        self.assertGreater(f.getlength("한글"), 0)

    def test_emoji_font_renders_color(self):
        from PIL import Image, ImageDraw, ImageFont

        path, _ = pc.font_file("emoji")
        self.assertTrue(os.path.exists(path), path)
        img = Image.new("RGBA", (220, 220))
        ImageDraw.Draw(img).text((110, 110), "🐟", font=ImageFont.truetype(path, 160), embedded_color=True, anchor="mm")
        self.assertIsNotNone(img.getbbox(), "emoji drew nothing")

    @unittest.skipUnless(pc.IS_MAC, "macOS only")
    def test_mac_fonts_unchanged(self):
        self.assertEqual(pc.font_file("kr", "bold"), ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6))
        self.assertEqual(pc.font_file("rounded")[0], "/System/Library/Fonts/SFNSRounded.ttf")


class SystemTest(unittest.TestCase):
    def test_ui_language(self):
        code = pc.ui_language()
        self.assertTrue(code is None or (isinstance(code, str) and code))

    def test_python_cmd_runs(self):
        r = subprocess.run(pc.python_cmd() + ["-c", "print(1+1)"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), "2")
        if pc.IS_MAC:
            self.assertEqual(pc.python_cmd(), ["python3"])

    def test_pid_alive(self):
        self.assertTrue(pc.pid_alive(os.getpid()))
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        time.sleep(0.2)
        self.assertFalse(pc.pid_alive(p.pid))

    def test_local_machine_stats(self):
        d = pc.local_machine_stats()
        if pc.IS_MAC:
            self.assertIsNone(d)  # macOS 는 machines.py 의 원래 bash 스크립트
            return
        self.assertGreaterEqual(d["cpu"], 0)
        self.assertLessEqual(d["cpu"], 100)
        self.assertGreater(d["mem"], 0)
        self.assertGreater(d["disk_total_kb"], d["disk_avail_kb"])
        self.assertLess(d["boot"], time.time())
        import machines

        st = machines._probe("This PC", None)
        self.assertTrue(st.online)
        self.assertGreater(st.mem_gb, 0)


class HookScanTest(unittest.TestCase):
    """대시보드가 세션 상태를 읽을 때 살아 있는 세션 프로세스를 건드리지 않아야 한다.
    (Windows 에서 os.kill(pid, 0) 은 그 프로세스를 강제 종료한다)"""

    def test_scan_keeps_live_session_and_removes_dead(self):
        home = tempfile.mkdtemp()
        agents = Path(home) / ".cache" / "d200" / "agents"
        agents.mkdir(parents=True)
        live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(live.kill)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        now = time.time()
        for name, pid in (("live", live.pid), ("dead", dead.pid)):
            (agents / f"{name}.json").write_text(json.dumps(
                {"id": name, "pid": pid, "project": "p", "agent": "claude-code", "status": "working",
                 "updated": now, "started": now}))
        env = {"HOME": home, "USERPROFILE": home}
        with mock.patch.dict(os.environ, env):
            import hook_agents

            items = hook_agents._scan(None)
        self.assertEqual([d["id"] for d in items], ["live"])
        self.assertIsNone(live.poll(), "scan killed a live session process")
        self.assertFalse((agents / "dead.json").exists())


@unittest.skipUnless(pc.IS_WINDOWS, "Windows only")
class WindowsHookTest(unittest.TestCase):
    def test_lineage_skips_shells(self):
        """python → cmd → python(훅) 처럼 셸을 거쳐도 셸이 아닌 조상을 에이전트로 고른다."""
        script = Path(tempfile.mkdtemp()) / "lineage.py"
        script.write_text("import sys, json; sys.path.insert(0, r'%s'); import agent_hook; "
                          "print(json.dumps(agent_hook._win_lineage()))" % (ROOT / "hooks"), encoding="utf-8")
        # cmd /s /c ""exe" "file"" : 공백이 든 경로(C:\Users\User Name)도 그대로 넘긴다
        r = subprocess.run(f'cmd /s /c ""{sys.executable}" "{script}""', capture_output=True, text=True, timeout=30)
        pid, name, _app_pid, _app = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertNotIn(name, ("cmd.exe", "python.exe", "conhost.exe"))
        self.assertTrue(pc.pid_alive(pid))

    def test_hook_writes_windows_record(self):
        home = tempfile.mkdtemp()
        env = {**os.environ, "HOME": home, "USERPROFILE": home}
        payload = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "t1", "cwd": str(ROOT)})
        subprocess.run(pc.python_cmd() + [str(ROOT / "hooks" / "agent_hook.py"), "claude"], input=payload,
                       text=True, env=env, timeout=30)
        rec = json.loads((Path(home) / ".cache" / "d200" / "agents" / "claude-code-t1.json").read_text())
        self.assertEqual(rec["platform"], "win32")
        self.assertEqual(rec["status"], "working")
        self.assertEqual(rec["project"], ROOT.name)
        self.assertTrue(pc.pid_alive(rec["pid"]), "recorded pid must outlive the hook (not the shell)")

    def test_hook_records_ai_title_for_tab_matching(self):
        """transcript 의 마지막 ai-title 을 기록한다 (Windows Terminal 탭 이름과 같다)."""
        home = Path(tempfile.mkdtemp())
        transcript = home / "t.jsonl"
        lines = [{"type": "ai-title", "aiTitle": "옛 제목"}, {"type": "user", "message": "x" * 1000},
                 {"type": "ai-title", "aiTitle": "D200H 포팅"}, {"type": "assistant"}]
        transcript.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8")
        env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
        payload = json.dumps({"hook_event_name": "Stop", "session_id": "t2", "cwd": str(ROOT),
                              "transcript_path": str(transcript)})
        subprocess.run(pc.python_cmd() + [str(ROOT / "hooks" / "agent_hook.py"), "claude"], input=payload,
                       text=True, env=env, timeout=30, encoding="utf-8")
        rec = json.loads((home / ".cache" / "d200" / "agents" / "claude-code-t2.json").read_text())
        self.assertEqual(rec["title"], "D200H 포팅")
        self.assertEqual(rec["status"], "done")

    def test_hook_records_codex_thread_name(self):
        """Codex: notify 의 thread-id 로 session_index.jsonl 의 thread_name 을 찾아 기록한다."""
        home = Path(tempfile.mkdtemp())
        codex_home = home / ".codex"
        codex_home.mkdir()
        (codex_home / "session_index.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [
            {"id": "th-1", "thread_name": "옛 이름"}, {"id": "th-2", "thread_name": "다른 대화"},
            {"id": "th-1", "thread_name": "geon4 구현 및 검증 진행"}]), encoding="utf-8")
        day = codex_home / "sessions" / "2026" / "11" / "21"
        day.mkdir(parents=True)
        (day / "rollout-2026-11-21T23-19-50-th-1.jsonl").write_text("{}")  # th-1 만 기록이 있는 진짜 대화
        env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "CODEX_HOME": str(codex_home)}
        agents = home / ".cache" / "d200" / "agents"
        for tid in ("th-1", "th-aux"):  # th-aux: 기록 없는 내부 보조 대화
            payload = json.dumps({"type": "agent-turn-complete", "thread-id": tid, "cwd": str(ROOT)})
            subprocess.run(pc.python_cmd() + [str(ROOT / "hooks" / "agent_hook.py"), "codex", payload],
                           env=env, timeout=30)
        rec = json.loads((agents / "codex-th-1.json").read_text())
        self.assertEqual(rec["title"], "geon4 구현 및 검증 진행")
        self.assertEqual(rec["status"], "done")
        self.assertFalse((agents / "codex-th-aux.json").exists(), "aux thread without rollout must be skipped")

    def test_codex_title_resolved_at_press_time(self):
        """새 대화는 알림보다 제목이 늦게 기록된다 → 누를 때 dashboard 가 다시 찾는다."""
        import hook_agents

        codex_home = Path(tempfile.mkdtemp())
        (codex_home / "session_index.jsonl").write_text(
            json.dumps({"id": "th-9", "thread_name": "Calculate 1+1"}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
            self.assertEqual(hook_agents._codex_title("th-9"), "Calculate 1+1")
            self.assertEqual(hook_agents._codex_title("nope"), "")

    def test_tab_matches(self):
        self.assertTrue(pc.tab_matches("◐ jakeparkcolde-agentdeck D200H 포팅", "jakeparkcolde-agentdeck D200H 포팅"))
        self.assertTrue(pc.tab_matches("geon4 구현 및 검증 진행 | geon4", "geon4 구현 및 검증 진행"))  # Codex
        self.assertFalse(pc.tab_matches("geon4 구현", "geon4"))  # 앞부분만 같으면 다른 탭
        self.assertFalse(pc.tab_matches("PowerShell", ""))

    def test_seen_terms_picks_sessions_of_foreground_tab(self):
        """맨 앞 Windows Terminal 탭에서 도는 세션만 '본 것' 으로 고른다."""
        import hook_agents

        sessions = {
            "local:claude-code-a": {"platform": "win32", "agent": "claude-code", "title": "D200H 포팅", "_ssh": None},
            "local:claude-code-b": {"platform": "win32", "agent": "claude-code", "title": "다른 작업", "_ssh": None},
            "studio:claude-code-c": {"platform": "win32", "agent": "claude-code", "title": "D200H 포팅", "_ssh": "studio"},
        }
        with mock.patch.dict(hook_agents._sessions, sessions, clear=True), \
                mock.patch.object(pc, "foreground_terminal_tab", return_value="✳ D200H 포팅"):
            self.assertEqual(hook_agents.seen_terms(), ["local:claude-code-a"])
        with mock.patch.dict(hook_agents._sessions, sessions, clear=True), \
                mock.patch.object(pc, "foreground_terminal_tab", return_value=None):  # 맨 앞이 터미널이 아님
            self.assertEqual(hook_agents.seen_terms(), [])

    def test_foreground_tab_helper_is_reused(self):
        """맨 앞 탭 읽기: PowerShell 을 한 번 띄워 계속 쓴다 (두 번째부터 빠르다)."""
        first = pc.foreground_terminal_tab(timeout=20)
        proc = pc._fg_tab._proc
        t0 = time.perf_counter()
        second = pc.foreground_terminal_tab()
        self.assertIs(pc._fg_tab._proc, proc, "helper process must be reused")
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertEqual(type(first), type(second))

    def test_foreground_tab_helper_closes_when_idle(self):
        """한동안 묻지 않으면 PowerShell 도우미를 끄고(메모리), 다시 물으면 새로 띄운다."""
        helper = pc._ForegroundTab(idle_sec=1)
        self.addCleanup(helper.close)
        first = helper.query(timeout=20)
        self.assertTrue(helper.running)
        pid = helper._proc.pid
        time.sleep(3)
        self.assertFalse(helper.running, "helper should be closed after idle")
        self.assertFalse(pc.pid_alive(pid), "helper process should be gone")
        second = helper.query(timeout=20)  # 다시 물으면 새로 띄운다
        self.assertTrue(helper.running)
        self.assertEqual(type(first), type(second))

    def test_select_tab_no_match_returns_zero(self):
        self.assertEqual(pc.select_terminal_tab(0, "no such tab zzz-agentdeck"), 0)


if __name__ == "__main__":
    unittest.main()
