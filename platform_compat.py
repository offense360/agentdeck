"""운영체제마다 다른 일을 한곳에 모은다 (macOS · Windows · Linux).

macOS 에서는 원래 코드와 똑같이 동작하고, Windows · Linux 에서만 다른 방법을 쓴다.
프로젝트의 다른 모듈을 가져오지 않는다 (어디서 가져다 써도 순환 import 가 생기지 않게).

  font_file / truetype   글꼴 (한글 · 숫자용 둥근 글꼴 · 컬러 이모지)
  ui_language            시스템 표시 언어
  python_cmd             훅 · 상태 수집에 쓸 Python 실행 명령
  pid_alive              프로세스가 살아 있는지 (Windows 에서 os.kill(pid, 0) 은 그 프로세스를 죽인다!)
  open_target            주소 · 파일 · 앱 열기
  notify                 데스크톱 알림
  local_machine_stats    이 컴퓨터의 CPU · 메모리 · 디스크 (macOS 는 machines.py 의 bash 스크립트를 그대로 쓴다)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# ---------------------------------------------------------------- 글꼴
WEIGHTS = ("light", "regular", "medium", "semibold", "bold")

# macOS: Apple SD Gothic Neo 는 한 파일(.ttc) 안에 굵기별 글꼴이 들어 있다 (index)
_MAC_KR = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
_MAC_KR_INDEX = {"regular": 0, "medium": 2, "semibold": 4, "bold": 6, "light": 8}
_MAC_ROUNDED = "/System/Library/Fonts/SFNSRounded.ttf"  # 가변 글꼴: 굵기는 이름으로 고른다
_MAC_EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"

_WIN_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
# Windows: 맑은 고딕은 굵기마다 파일이 따로 있다 (보통 · 굵게 · 가늘게)
_WIN_KR = {"light": "malgunsl.ttf", "regular": "malgun.ttf", "medium": "malgun.ttf",
           "semibold": "malgunbd.ttf", "bold": "malgunbd.ttf"}
_WIN_ROUNDED = {"light": "segoeuil.ttf", "regular": "segoeui.ttf", "medium": "seguisb.ttf",
                "semibold": "seguisb.ttf", "bold": "segoeuib.ttf"}
_WIN_EMOJI = "seguiemj.ttf"

_LINUX_KR = ("/usr/share/fonts/opentype/noto/NotoSansCJK-{w}.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-{w}.ttc",
             "/usr/share/fonts/truetype/nanum/NanumGothic{w2}.ttf")
_LINUX_W = {"light": ("Light", ""), "regular": ("Regular", ""), "medium": ("Medium", ""),
            "semibold": ("Bold", "Bold"), "bold": ("Bold", "Bold")}
_LINUX_ROUNDED = ("/usr/share/fonts/truetype/dejavu/DejaVuSans{w}.ttf",)
_LINUX_EMOJI = ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", "/usr/share/fonts/noto/NotoColorEmoji.ttf")

_font_cache: dict[tuple[str, str], tuple[str, int]] = {}


def _first(paths) -> str | None:
    return next((p for p in paths if os.path.exists(p)), None)


def _fc_match(pattern: str) -> str | None:
    """Linux: fontconfig 로 글꼴 파일을 찾는다."""
    if not shutil.which("fc-match"):
        return None
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, timeout=3).stdout
        return out.strip() or None
    except Exception:
        return None


def font_file(kind: str, weight: str = "regular") -> tuple[str, int]:
    """(글꼴 파일, ttc 안 번호). kind: "kr"(한글) · "rounded"(큰 숫자) · "emoji"."""
    weight = weight if weight in WEIGHTS else "regular"
    key = (kind, weight)
    if key in _font_cache:
        return _font_cache[key]
    path, index = None, 0
    if IS_MAC:
        if kind == "kr":
            path, index = _MAC_KR, _MAC_KR_INDEX[weight]
        elif kind == "rounded":
            path = _MAC_ROUNDED
        elif kind == "emoji":
            path = _MAC_EMOJI
    elif IS_WINDOWS:
        name = {"kr": _WIN_KR.get(weight), "rounded": _WIN_ROUNDED.get(weight), "emoji": _WIN_EMOJI}.get(kind)
        path = _first([os.path.join(_WIN_FONTS, name)]) if name else None
        if not path and kind != "emoji":  # 굵기 파일이 없으면 보통 굵기로
            path = _first([os.path.join(_WIN_FONTS, f) for f in ("malgun.ttf", "segoeui.ttf", "arial.ttf")])
    else:
        w, w2 = _LINUX_W[weight]
        if kind == "kr":
            path = _first(p.format(w=w, w2=w2) for p in _LINUX_KR) or _fc_match(f"sans:lang=ko:weight={weight}")
        elif kind == "rounded":
            path = _first(p.format(w="-Bold" if w2 else "") for p in _LINUX_ROUNDED) or _fc_match("sans")
        elif kind == "emoji":
            path = _first(_LINUX_EMOJI) or _fc_match("emoji")
    if not path:  # 마지막 수단: 한글 글꼴
        path = _MAC_KR if IS_MAC else (_first([os.path.join(_WIN_FONTS, "malgun.ttf")]) or _fc_match("sans") or "")
    _font_cache[key] = (path, index)
    return path, index


def truetype(kind: str, size: int, weight: str = "regular"):
    """PIL 글꼴. macOS 둥근 글꼴(SF Rounded)은 가변 글꼴이라 굵기를 이름으로 고른다 (원래 clock.py 동작)."""
    from PIL import ImageFont

    path, index = font_file(kind, weight)
    f = ImageFont.truetype(path, size, index=index)
    if kind == "rounded" and IS_MAC:
        try:
            f.set_variation_by_name(weight.capitalize().encode())
        except Exception:
            pass
    return f


# ---------------------------------------------------------------- 언어
def ui_language() -> str | None:
    """시스템 표시 언어의 두 글자 코드 (예: "ko", "en"). 모르면 None."""
    try:
        if IS_MAC:
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True,
                                 text=True, timeout=3).stdout
            first = re.search(r'"?([A-Za-z]{2,3})[-_"\s]', out)
            return first[1].lower() if first else None
        if IS_WINDOWS:
            import ctypes

            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primary = langid & 0x3FF
            return {0x12: "ko", 0x09: "en", 0x11: "ja", 0x04: "zh"}.get(primary, "other")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- Python · 프로세스
def python_cmd() -> list[str]:
    """훅 · 상태 수집 스크립트를 돌릴 Python.

    macOS 는 원래대로 시스템 python3. Windows 의 python3 는 스토어 설치 안내만 띄우는 가짜 명령일 때가 많아서,
    지금 도는 Python(가상환경이면 그 바탕 Python)의 실제 경로를 쓴다. 훅은 표준 라이브러리만 쓴다.
    Git Bash 에서도 그대로 돌도록 경로는 / 로 적는다.
    """
    if IS_MAC:
        return ["python3"]
    exe = getattr(sys, "_base_executable", None) or sys.executable
    return [exe.replace("\\", "/") if IS_WINDOWS else exe]


def pid_alive(pid: int) -> bool:
    """프로세스가 살아 있는지. 확인할 수 없으면 False (원래 hook_agents 동작과 같게).

    macOS · Linux 는 원래대로 os.kill(pid, 0) (pid 0 은 자기 프로세스 그룹이라 True).
    """
    if IS_WINDOWS:
        if pid <= 0:
            return False
        import ctypes

        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def activate_pid(pid: int) -> bool:
    """Windows: 그 프로세스의 보이는 창을 맨 앞으로. 다른 OS 는 False."""
    if not IS_WINDOWS or pid <= 0:
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):  # GW_OWNER
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(each, 0)
    return activate_hwnd(found[0]) if found else False


def activate_hwnd(hwnd: int) -> bool:
    """Windows: 창 하나를 맨 앞으로 (최소화돼 있으면 복원)."""
    if not IS_WINDOWS or not hwnd:
        return False
    import ctypes

    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # 백그라운드 프로세스는 창을 앞으로 가져올 권한이 없어 작업 표시줄만 깜빡인다. Alt 키를 한 번 눌렀다 떼면 허용된다
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    return bool(user32.SetForegroundWindow(hwnd))


# Windows Terminal 탭 고르기: UI Automation 으로 탭 이름이 같은 탭을 선택하고 그 창 핸들을 출력한다.
# Claude Code 는 탭 제목 앞에 상태 기호(✳ ◑ ⠂ 등)를 붙이므로 글자·숫자가 나오기 전까지는 빼고 비교한다.
# Codex 는 '대화 제목 | 프로젝트' 로 붙이므로 '제목 | ' 로 시작해도 같은 탭으로 본다.
_WT_SELECT_TAB = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$strip = { param($s) ($s -replace '^[^\p{L}\p{N}]+', '').Trim() }
$want = & $strip $env:AGENTDECK_TAB_TITLE
$appPid = [int]$env:AGENTDECK_APP_PID
$A = [Windows.Automation.AutomationElement]
$winCond = New-Object Windows.Automation.PropertyCondition($A::ClassNameProperty, 'CASCADIA_HOSTING_WINDOW_CLASS')
$tabCond = New-Object Windows.Automation.PropertyCondition($A::ControlTypeProperty, [Windows.Automation.ControlType]::TabItem)
foreach ($w in $A::RootElement.FindAll([Windows.Automation.TreeScope]::Children, $winCond)) {
  if ($appPid -and $w.Current.ProcessId -ne $appPid) { continue }
  foreach ($t in $w.FindAll([Windows.Automation.TreeScope]::Descendants, $tabCond)) {
    $name = & $strip $t.Current.Name
    if ($name -eq $want -or $name.StartsWith($want + ' | ')) {
      if (-not $env:AGENTDECK_TAB_DRYRUN) { $t.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern).Select() }
      $w.Current.NativeWindowHandle
      exit 0
    }
  }
}
exit 1
'''


def select_terminal_tab(app_pid: int, title: str, dry_run: bool = False) -> int:
    """Windows Terminal 에서 제목이 같은 탭을 고른다. 성공하면 그 창 핸들, 못 찾으면 0.

    dry_run: 찾기만 하고 탭은 바꾸지 않는다 (시험용).
    """
    if not IS_WINDOWS or not title.strip():
        return 0
    env = {**os.environ, "AGENTDECK_TAB_TITLE": title, "AGENTDECK_APP_PID": str(app_pid or 0)}
    if dry_run:
        env["AGENTDECK_TAB_DRYRUN"] = "1"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _WT_SELECT_TAB],
                           capture_output=True, text=True, timeout=15, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return int(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else 0
    except Exception:
        return 0


# 맨 앞 창이 Windows Terminal 이면 선택된 탭 이름을 한 줄씩 답하는 PowerShell (한 번 띄워 계속 쓴다).
# 답: "-" = 맨 앞 창이 Windows Terminal 아님, "T:<탭 이름>" = 맨 앞 창의 선택된 탭
_WT_FG_LOOP = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type -Namespace AgentDeck -Name Fg -MemberDefinition '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();'
$A = [Windows.Automation.AutomationElement]
$tabCond = New-Object Windows.Automation.PropertyCondition($A::ControlTypeProperty, [Windows.Automation.ControlType]::TabItem)
while ($true) {
  $line = [Console]::In.ReadLine()
  if ($null -eq $line) { break }
  $out = '-'
  try {
    $w = $A::FromHandle([AgentDeck.Fg]::GetForegroundWindow())
    if ($w.Current.ClassName -eq 'CASCADIA_HOSTING_WINDOW_CLASS') {
      $out = 'T:'
      foreach ($t in $w.FindAll([Windows.Automation.TreeScope]::Descendants, $tabCond)) {
        if ($t.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected) { $out = 'T:' + $t.Current.Name; break }
      }
    }
  } catch { $out = '-' }
  [Console]::Out.WriteLine($out)
  [Console]::Out.Flush()
}
'''


class _ForegroundTab:
    """_WT_FG_LOOP 를 한 번 띄워 두고 묻는다. 프로세스를 매번 만들지 않아서 한 번 묻는 데 수십 ms.

    PowerShell 은 메모리를 80MB 넘게 쓰므로, idle_sec 동안 묻지 않으면(깜빡이는 칸이 없으면) 끄고
    다음에 물을 때 다시 띄운다 (다시 띄우는 데 0.4초쯤).
    """

    def __init__(self, idle_sec: float = 120) -> None:
        import queue
        import threading

        self._q: queue.Queue[str] = queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._threading = threading
        self.idle_sec = idle_sec
        self._last = 0.0
        self._idle_timer: threading.Timer | None = None

    def _arm_idle(self) -> None:
        """마지막으로 물은 뒤 idle_sec 가 지나면 끄도록 타이머를 다시 건다."""
        if self._idle_timer:
            self._idle_timer.cancel()
        self._idle_timer = self._threading.Timer(self.idle_sec + 1, self._close_if_idle)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _close_if_idle(self) -> None:
        with self._lock:
            if self._proc is not None and time.monotonic() - self._last >= self.idle_sec:
                self.close()

    def _start(self) -> None:
        self._proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _WT_FG_LOOP],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        proc, q = self._proc, self._q

        def reader() -> None:
            for line in proc.stdout:
                q.put(line.rstrip("\r\n"))

        self._threading.Thread(target=reader, daemon=True).start()

    def query(self, timeout: float) -> str | None:
        import queue

        with self._lock:
            try:
                if self._proc is None or self._proc.poll() is not None:
                    self._start()
                    timeout = max(timeout, 15)  # 처음 띄울 때는 UI Automation 을 읽어 들이느라 느리다
                while not self._q.empty():  # 시간 초과로 늦게 온 옛 답은 버린다
                    self._q.get_nowait()
                self._proc.stdin.write("q\n")
                self._proc.stdin.flush()
                ans = self._q.get(timeout=timeout)
            except (OSError, ValueError, queue.Empty):
                self.close()  # 멈췄거나 죽었다: 다음에 새로 띄운다
                return None
            finally:
                self._last = time.monotonic()
                self._arm_idle()
        return ans[2:] if ans.startswith("T:") else None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()  # stdout 이 닫히면서 읽기 스레드도 끝난다
                self._proc.wait(timeout=5)
            except Exception:
                pass
        self._proc = None


_fg_tab: _ForegroundTab | None = None


def foreground_terminal_tab(timeout: float = 3.0) -> str | None:
    """맨 앞 창이 Windows Terminal 이면 선택된 탭 이름(상태 기호 포함 그대로), 아니면 None. Windows 전용."""
    global _fg_tab
    if not IS_WINDOWS:
        return None
    if _fg_tab is None:
        _fg_tab = _ForegroundTab()
    return _fg_tab.query(timeout)


def tab_matches(tab_name: str, title: str) -> bool:
    """Windows Terminal 탭 이름이 세션 제목과 같은 탭인지 (_WT_SELECT_TAB 과 같은 규칙).

    앞의 상태 기호(✳ ◑ 등)는 빼고, Codex 처럼 '제목 | 프로젝트' 면 '제목 | ' 로 시작해도 같은 탭.
    """
    name = re.sub(r"^[\W_]+", "", tab_name or "").strip()  # 글자·숫자가 나오기 전까지 (PowerShell 쪽 [^\p{L}\p{N}] 과 같게)
    want = re.sub(r"^[\W_]+", "", title or "").strip()
    return bool(want) and (name == want or name.startswith(want + " | "))


def run_cli(name: str, *args: str) -> bool:
    """PATH 의 명령(code · cursor 등)을 실행한다. 없으면 False."""
    exe = shutil.which(name)
    if not exe:
        return False
    try:
        subprocess.Popen([exe, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 열기 · 알림
def open_target(target: str) -> bool:
    """주소 · 파일 · 앱을 연다 (macOS `open`)."""
    target = os.path.expanduser(target)
    try:
        if IS_MAC:
            return subprocess.run(["open", target], capture_output=True, timeout=10).returncode == 0
        if IS_WINDOWS:
            os.startfile(target)  # noqa: S606 - 설정 파일·코드에 적힌 대상만 연다
            return True
        return subprocess.run(["xdg-open", target], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


def notify(title: str, msg: str, sound: bool = True) -> None:
    """데스크톱 알림. 실패해도 조용히 넘어간다."""
    try:
        if IS_MAC:
            snd = ' sound name "Glass"' if sound else ""
            subprocess.Popen(["osascript", "-e", f'display notification "{msg}" with title "{title}"{snd}'])
            if sound:
                subprocess.Popen(["/bin/sh", "-c", "for i in 1 2 3; do afplay /System/Library/Sounds/Glass.aiff; done"])
        elif IS_WINDOWS:
            _windows_toast(title, msg)
            if sound:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        elif shutil.which("notify-send"):
            subprocess.Popen(["notify-send", title, msg])
    except Exception:
        pass


def _windows_toast(title: str, msg: str) -> None:
    """Windows 알림 센터 토스트 (PowerShell 로 WinRT API 호출, 추가 설치 없음)."""
    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;").replace("'", "''"))

    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$x.LoadXml('<toast><visual><binding template=\"ToastGeneric\"><text>{esc(title)}</text>"
        f"<text>{esc(msg)}</text></binding></visual></toast>');"
        # 앱 등록 없이 보이도록 PowerShell 의 앱 ID 로 띄운다
        "$id = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show("
        "[Windows.UI.Notifications.ToastNotification]::new($x))"
    )
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


# ---------------------------------------------------------------- 이 컴퓨터 상태
def local_machine_stats() -> dict | None:
    """machines.py PROBE 와 같은 모양의 dict. macOS 는 None (원래 bash 스크립트를 쓴다).

    {"ncpu", "cpu"(0~100), "mem"(바이트), "mem_free_pct", "disk_total_kb", "disk_avail_kb", "boot"(epoch), "volumes"}
    """
    if IS_MAC:
        return None
    if IS_WINDOWS:
        return _windows_stats()
    return _linux_stats()


def _windows_stats() -> dict:
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.windll.kernel32

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    mem = MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    k32.GlobalMemoryStatusEx(ctypes.byref(mem))

    def times() -> tuple[int, int]:
        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        val = lambda ft: (ft.dwHighDateTime << 32) | ft.dwLowDateTime  # noqa: E731
        return val(idle), val(kernel) + val(user)  # kernel 시간에 idle 이 포함된다

    i0, t0 = times()
    time.sleep(1)  # macOS 쪽도 top 으로 1초 표본을 잰다
    i1, t1 = times()
    cpu = (1 - (i1 - i0) / (t1 - t0)) * 100 if t1 > t0 else 0.0

    sysdrive = os.environ.get("SystemDrive", "C:") + "\\"
    du = shutil.disk_usage(sysdrive)
    k32.GetTickCount64.restype = ctypes.c_ulonglong
    boot = time.time() - k32.GetTickCount64() / 1000

    volumes = []  # 시스템 드라이브 말고 100GB 이상인 드라이브 (macOS 의 /Volumes 외장 볼륨에 해당)
    mask = k32.GetLogicalDrives()
    for i in range(26):
        if not mask & (1 << i):
            continue
        root = f"{chr(65 + i)}:\\"
        if root.upper() == sysdrive.upper() or k32.GetDriveTypeW(root) not in (2, 3):  # 이동식 · 고정
            continue
        try:
            u = shutil.disk_usage(root)
        except OSError:
            continue
        if u.total < 100 * 1024**3:
            continue
        label = ctypes.create_unicode_buffer(261)
        k32.GetVolumeInformationW(root, label, 261, None, None, None, None, 0)
        volumes.append({"name": label.value or root[:2], "total_kb": u.total // 1024, "avail_kb": u.free // 1024})

    return {"ncpu": os.cpu_count() or 1, "cpu": round(cpu, 1), "mem": mem.ullTotalPhys,
            "mem_free_pct": 100 - mem.dwMemoryLoad, "disk_total_kb": du.total // 1024,
            "disk_avail_kb": du.free // 1024, "boot": boot, "volumes": volumes}


def _linux_stats() -> dict:
    def cpu_times() -> tuple[int, int]:
        with open("/proc/stat") as fp:
            vals = [int(x) for x in fp.readline().split()[1:]]
        return vals[3] + vals[4], sum(vals)  # idle + iowait, 전체

    i0, t0 = cpu_times()
    time.sleep(1)
    i1, t1 = cpu_times()
    info = {}
    with open("/proc/meminfo") as fp:
        for line in fp:
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
    du = shutil.disk_usage("/")
    with open("/proc/uptime") as fp:
        boot = time.time() - float(fp.read().split()[0])
    total = info.get("MemTotal", 0)
    return {"ncpu": os.cpu_count() or 1, "cpu": round((1 - (i1 - i0) / (t1 - t0)) * 100, 1) if t1 > t0 else 0.0,
            "mem": total, "mem_free_pct": info.get("MemAvailable", 0) / total * 100 if total else None,
            "disk_total_kb": du.total // 1024, "disk_avail_kb": du.free // 1024, "boot": boot, "volumes": []}
