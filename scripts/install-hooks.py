#!/usr/bin/env python3
"""에이전트 상태 훅 설치/제거 (훅 방식: VS Code·Cursor·터미널 등 어디서 돌든 상태 수집).

  python3 scripts/install-hooks.py            # Claude Code 훅 설치
  python3 scripts/install-hooks.py --codex    # + Codex notify 연결 (기존 notify 는 이어서 실행되도록 감쌈)
  python3 scripts/install-hooks.py --uninstall
  python3 scripts/install-hooks.py --settings /tmp/x.json   # 다른 설정 파일에 (시험용)

기존 훅은 건드리지 않고 우리 항목만 추가/제거한다. 바꾸기 전에 .bak-agentdeck 백업을 만든다.

Windows: Claude Code 는 Git Bash 가 있으면 bash 로, 없으면 PowerShell 로 훅 명령을 실행한다.
셸마다 따옴표 해석이 달라 `"python.exe" "hook.py" claude` 같은 한 줄 명령은 PowerShell 에서 깨진다(구문 오류 →
모든 도구 실행이 막힘). 그래서 Windows 에선 셸을 거치지 않는 command(프로그램) + args(인자) 형식으로 적는다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import platform_compat  # noqa: E402
from i18n import t  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "agent_hook.py")
if platform_compat.IS_WINDOWS:  # Claude Code 는 Windows 에서 훅을 Git Bash 로 실행한다: 경로는 / 로
    HOOK = HOOK.replace("\\", "/")
PY = platform_compat.python_cmd()  # macOS: python3 / Windows: 실제 Python 경로
CLAUDE_CMD = f'python3 "{HOOK}" claude' if PY == ["python3"] else f'"{PY[0]}" "{HOOK}" claude'
CLAUDE_SETTINGS = os.path.expanduser("~/.claude/settings.json")
if "--settings" in sys.argv:
    CLAUDE_SETTINGS = os.path.abspath(sys.argv[sys.argv.index("--settings") + 1])


def hook_command() -> dict:
    """훅 한 개. macOS · Linux 는 원래 한 줄 명령, Windows 는 셸을 거치지 않는 프로그램 + 인자."""
    if platform_compat.IS_WINDOWS:
        return {"type": "command", "command": PY[0], "args": [HOOK, "claude"], "timeout": 5}
    return {"type": "command", "command": CLAUDE_CMD, "timeout": 5}
CODEX_CONFIG = os.path.expanduser("~/.codex/config.toml")
EVENTS = {  # 이벤트 → matcher (도구 이벤트만 "*")
    "SessionStart": None, "UserPromptSubmit": None, "PreToolUse": "*", "PostToolUse": "*",
    "PermissionRequest": "*", "Notification": None, "Stop": None, "StopFailure": None, "SessionEnd": None,
}


def backup(path: str) -> None:
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak-agentdeck")


def is_ours(entry: dict) -> bool:
    return any("agent_hook.py" in " ".join([h.get("command") or "", *map(str, h.get("args") or [])])
               for h in entry.get("hooks", []))


def claude(install: bool) -> None:
    data = json.load(open(CLAUDE_SETTINGS, encoding="utf-8")) if os.path.exists(CLAUDE_SETTINGS) else {}
    hooks = data.setdefault("hooks", {})
    for ev, matcher in EVENTS.items():
        arr = [e for e in hooks.get(ev, []) if not is_ours(e)]  # 우리 것 제거 (재설치 시 중복 방지)
        if install:
            entry = {"hooks": [hook_command()]}
            if matcher:
                entry = {"matcher": matcher, **entry}
            arr.append(entry)
        if arr:
            hooks[ev] = arr
        else:
            hooks.pop(ev, None)
    backup(CLAUDE_SETTINGS)
    os.makedirs(os.path.dirname(CLAUDE_SETTINGS), exist_ok=True)
    with open(CLAUDE_SETTINGS, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)
    print(t("설치" if install else "제거", "Installed" if install else "Removed"), t("Claude Code 훅:", "Claude Code hooks:"), CLAUDE_SETTINGS)


def codex(install: bool) -> None:
    if not os.path.exists(CODEX_CONFIG):
        print(t("Codex 설정 없음:", "No Codex config:"), CODEX_CONFIG)
        return
    text = open(CODEX_CONFIG).read()
    m = re.search(r"^notify\s*=\s*(\[.*?\])\s*$", text, re.M | re.S)
    current = json.loads(m.group(1)) if m else None
    ours = [*PY, HOOK, "codex", "--"]
    if current and len(current) >= 4 and current[1].endswith("agent_hook.py"):
        original = current[4:]  # 이미 우리 래퍼: 원래 명령만 꺼냄
    else:
        original = current or []
    new = (ours + original) if install else original
    if new == (current or []):  # 바뀔 게 없으면 파일을 다시 쓰지 않는다 (서식이 바뀌지 않게)
        print(t("변경 없음", "No change"), "Codex notify:", CODEX_CONFIG)
        return
    line = "notify = " + json.dumps(new, ensure_ascii=False) if new else ""
    if m:
        text = text[:m.start()] + line + text[m.end():]
    elif line:
        text = line + "\n" + text
    backup(CODEX_CONFIG)
    open(CODEX_CONFIG, "w").write(text)
    print(t("설치" if install else "제거", "Installed" if install else "Removed"), "Codex notify:", CODEX_CONFIG,
          t("(기존:", "(previous:"), original or t("없음", "none"), ")")


if __name__ == "__main__":
    uninstall = "--uninstall" in sys.argv
    claude(not uninstall)
    if "--codex" in sys.argv or uninstall:
        codex(not uninstall)
