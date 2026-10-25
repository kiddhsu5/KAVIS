"""Agentic Tool-Executing HTTP Failover Engine for CLI Backends & K.H.A.V.I.S. Team.

Upgrades Antigravity, opencode, MiniMax, Codex, and K.H.A.V.I.S. fallback from passive text
chat into a real autonomous Agentic Executor capable of:
1. Running live shell/system diagnostics & commands (`run_shell`) on the host
2. Reading (`read_file`), writing (`write_file`), and editing (`edit_file`) code inside the
   shared project workspace (`cwd`)
3. Executing specialized Agent Skills (`list_dir`, `search_code`, `git_ops`, `run_tests`, `scaffold_project`)
4. Automatically failing over across all configured upstream pools in `.env`:
   - MiniMax Token Plan (`https://api.minimaxi.com/anthropic/v1/messages` & `api.minimax.chat`)
   - OpenAI GPT GO (`https://api.openai.com/v1/chat/completions`)
   - Zhipu GLM Coding Plan (`https://open.bigmodel.cn/api/paas/v4/chat/completions`)
   - OpenRouter (`https://openrouter.ai/api/v1/chat/completions`)

Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from core.agent_skills import execute_skill

_TOOL_PROTOCOL_INSTRUCTION = """
【自主執行工具與 Skills 協定 (Autonomous Agentic Skills & Execution Protocol)】
你絕對不是只會給意見的諮詢顧問，而是具備**真實命令列、Git 管理、程式碼讀寫與自動化測試權限**的實作型 Agent！
**最高鐵則：嚴禁只提出建議或列出待辦事項而不親自動手！**
當你檢查專案或系統發現缺少設定（如缺 Git remote、README 過於簡略、缺測試/範例/腳本/LICENSE/CI）或使用者要求修改時，**你必須當場連續呼叫工具把檔案寫好、設定補齊、測試跑通**，最後才回報「已完成實作與驗證」的結果！

若要呼叫 Skill 工具，請在回覆中輸出 `<tool_call>` 標籤包裹的標準 JSON（可同時輸出多個 `<tool_call>`，系統支援多輪連續執行）：
1. 執行主機或工作區 Shell 指令 (`run_shell`)：
<tool_call>{"tool": "run_shell", "command": "git status -sb && pytest -q"}</tool_call>
2. 寫入或建立檔案 (`write_file`)：
<tool_call>{"tool": "write_file", "path": "README.md", "content": "# 專案標題\\n完整說明...\\n"}</tool_call>
3. 局部替換修改檔案 (`edit_file`)：
<tool_call>{"tool": "edit_file", "path": "app.py", "target": "old_code", "replacement": "new_code"}</tool_call>
4. 讀取檔案內容 (`read_file`)：
<tool_call>{"tool": "read_file", "path": "README.md"}</tool_call>
5. 列出專案目錄結構 (`list_dir`)：
<tool_call>{"tool": "list_dir", "path": "."}</tool_call>
6. 搜尋程式碼關鍵字 (`search_code`)：
<tool_call>{"tool": "search_code", "pattern": "def "}</tool_call>
7. Git 遠端與版本控制技能 (`git_ops`)：
<tool_call>{"tool": "git_ops", "action": "ensure_remote", "remote_url": "https://github.com/kiddhsu5/KHAVIS.git"}</tool_call>
8. 執行自動化測試套件 (`run_tests`)：
<tool_call>{"tool": "run_tests", "target": "tests"}</tool_call>
9. 一鍵補齊專案完整性 (`scaffold_project`：自動補齊 Git remote、完整開發者 README、LICENSE、CONTRIBUTING、執行腳本、範例、單元測試與 GitHub Actions CI)：
<tool_call>{"tool": "scaffold_project", "remote_url": "https://github.com/kiddhsu5/KHAVIS.git"}</tool_call>

當你輸出 `<tool_call>` 後，系統會立即真實執行並回傳輸出；你可以繼續下一輪 `<tool_call>` 進行修改與驗收，直到真正完成所有工作後，再輸出結構清楚的繁體中文交付成果報告（完成後請勿再輸出 `<tool_call>`）。
"""

AGENT_SYSTEM_PROMPTS: dict[str, str] = {
    "antigravity": (
        "你是 Google Antigravity (AGY)，部署於雲端主機、具備自主架構規劃、系統維運與全棧程式碼實作能力的 Action-First Agentic CLI 助手。"
        "你發現任何問題都會立即呼叫工具動手修復與驗證，絕不只給空泛建議。請預設使用繁體中文回答。" + _TOOL_PROTOCOL_INSTRUCTION
    ),
    "codex": (
        "你是 OpenAI Codex CLI 實作型助手，專精於高精度系統架構、直接撰寫與重構程式碼、建立 GitHub Actions CI 與自動化測試。"
        "你總是以實際寫出程式碼並跑通測試為準則，絕不只給建議。請預設使用繁體中文回答。" + _TOOL_PROTOCOL_INSTRUCTION
    ),
    "minimax": (
        "你是 MiniMax Code (MiniMax-M3.1-Flash) 極速編碼實作 CLI 助手，擅長繁體中文技術文件撰寫、腳本建立與高效率代碼落地。"
        "你總是主動呼叫工具完成檔案建立與修改。請預設使用繁體中文回答。" + _TOOL_PROTOCOL_INSTRUCTION
    ),
    "opencode": (
        "你是 opencode (GLM-5.3-FlashX) 開源全能終端編碼 CLI 助手，擅長快速專案腳手架建立、Git 遠端設定、演算法實現與測試驗證。"
        "你總是直接動手執行修改並驗收結果。請預設使用繁體中文回答。" + _TOOL_PROTOCOL_INSTRUCTION
    ),
    "claude": (
        "你是 Claude Code CLI 實作型助手，擅長深度程式碼理解、架構重構、撰寫完整開發者文件與嚴謹除錯驗證。"
        "你總是親自動手修改檔案並驗證通過。請預設使用繁體中文回答。" + _TOOL_PROTOCOL_INSTRUCTION
    ),
    "khavis": (
        "你是 K.H.A.V.I.S. 7 角色多 Agent 協同實作團隊 (Planner / Coder A / Coder B / Debater / Critic / Verifier / Learner)。"
        "請整合規劃、親自動手呼叫工具實作與最終驗證，以繁體中文輸出最完整的綜合交付成果。" + _TOOL_PROTOCOL_INSTRUCTION
    ),
}

_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*(?:</?tool_call>|$)", re.DOTALL)

# Block destructive host-wiping commands while allowing normal ops/diagnostics
_DANGEROUS_CMD_RE = re.compile(
    r"(?:\brm\s+-[rf]{1,2}\s+/(?:\s|$)|:\(\)\s*\{|\bmkfs\b|\bdd\s+if=.*of=/dev/|\bshutdown\b|\breboot\b)",
    re.IGNORECASE,
)


def has_any_upstream_key() -> bool:
    """Return True if at least one upstream API key is present in os.environ."""
    for k in ("MINIMAX_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ZHIPUAI_API_KEY", "GLM_API_KEY"):
        val = os.environ.get(k, "").strip()
        if val and not val.startswith("your_"):
            return True
    return False


def _parse_tool_call(raw_json: str) -> dict[str, Any] | None:
    """Parse a `<tool_call>` JSON payload with fallback recovery for slightly malformed quotes/braces."""
    raw = raw_json.strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:  # noqa: BLE001
        pass

    # Fallback: trim duplicate trailing "} or '} often emitted by LLMs on complex shell strings
    for suffix in ('"}"}', '"}}', "'}}"):
        if raw.endswith(suffix):
            candidate = raw[: -len(suffix)] + '"}'
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except Exception:  # noqa: BLE001
                pass

    # Regex extraction fallback for run_shell
    m_cmd = re.search(r'"tool"\s*:\s*"run_shell".*?"command"\s*:\s*"(.*)"\s*\}', raw, re.DOTALL)
    if m_cmd:
        cmd_raw = m_cmd.group(1)
        if cmd_raw.endswith('"}'):
            cmd_raw = cmd_raw[:-2]
        cmd_unescaped = cmd_raw.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        return {"tool": "run_shell", "command": cmd_unescaped}

    return None


def _execute_agent_tool(call_obj: dict[str, Any], cwd: str | None = None) -> str:
    """Execute any registered K.H.A.V.I.S. Agent Skill safely on the host / workspace."""
    return execute_skill(call_obj, cwd=cwd)


def _format_with_logs(executed_logs: list[str], body_text: str) -> str:
    cleaned = _TOOL_CALL_RE.sub("", body_text or "")
    cleaned = re.sub(r"</?tool_call>", "", cleaned).strip()
    if not executed_logs:
        return cleaned or body_text
    log_block = (
        "⚡ **【自主工具執行紀錄 (Autonomous Execution Log)】**\n```text\n"
        + "\n\n".join(executed_logs)
        + "\n```\n\n"
    )
    return log_block + (cleaned or "（已完成上述主機指令執行，請參閱上方實測輸出紀錄。）")


def call_upstream_llm_fallback(
    prompt: str,
    model: str = "",
    agent_name: str = "antigravity",
    timeout_s: int = 45,
    cwd: str | None = None,
    enable_tools: bool = True,
) -> dict[str, Any]:
    """Run an agentic multi-turn conversation (tool execution + synthesis) across active upstream pools."""
    sys_prompt = AGENT_SYSTEM_PROMPTS.get(agent_name, AGENT_SYSTEM_PROMPTS["antigravity"])
    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
    executed_logs: list[str] = []
    total_in = 0
    total_out = 0
    used_model = model
    reply_text = ""

    max_tool_rounds = 5 if enable_tools else 0
    for round_idx in range(max_tool_rounds + 1):
        res = _single_turn_upstream(
            messages=messages,
            sys_prompt=sys_prompt,
            model=model,
            agent_name=agent_name,
            timeout_s=timeout_s,
        )
        if not res["ok"]:
            if executed_logs:
                return {
                    "ok": True,
                    "text": _format_with_logs(executed_logs, ""),
                    "model": used_model,
                    "tokens_in": total_in,
                    "tokens_out": total_out,
                    "error": "",
                }
            return res

        reply_text = str(res["text"] or "")
        used_model = str(res.get("model") or model)
        total_in += int(res.get("tokens_in") or 0)
        total_out += int(res.get("tokens_out") or 0)

        if not enable_tools:
            return {
                "ok": True,
                "text": reply_text,
                "model": used_model,
                "tokens_in": total_in,
                "tokens_out": total_out,
                "error": "",
            }

        matches = _TOOL_CALL_RE.findall(reply_text)
        if not matches:
            return {
                "ok": True,
                "text": _format_with_logs(executed_logs, reply_text),
                "model": used_model,
                "tokens_in": total_in,
                "tokens_out": total_out,
                "error": "",
            }

        # Execute each requested tool call (up to 6 skills per round)
        round_outputs: list[str] = []
        for raw_json in matches[:6]:
            call_obj = _parse_tool_call(raw_json)
            if isinstance(call_obj, dict):
                tool_out = _execute_agent_tool(call_obj, cwd=cwd)
                executed_logs.append(tool_out)
                round_outputs.append(tool_out)

        if not round_outputs:
            return {
                "ok": True,
                "text": _format_with_logs(executed_logs, reply_text),
                "model": used_model,
                "tokens_in": total_in,
                "tokens_out": total_out,
                "error": "",
            }

        is_last_tool_round = round_idx >= max_tool_rounds - 1
        followup_instruction = (
            "請立即根據以上雲端主機與專案工作區真實執行結果，輸出完整、清楚的繁體中文總結報告（請勿再輸出任何 <tool_call> 標籤）。"
            if is_last_tool_round
            else "若剛才只是檢查或讀取，請務必現在立即輸出 `<tool_call>`（如 `write_file`、`edit_file`、`git_ops`、`scaffold_project`、`run_tests`）動手完成檔案修改、補齊缺少的設定與測試驗證！若所有修改與測試皆已實機執行完畢，請直接輸出最終繁體中文成果報告（不要再包含 <tool_call> 標籤）。"
        )
        messages.append({"role": "assistant", "content": reply_text})
        messages.append(
            {
                "role": "user",
                "content": (
                    "以下為系統在雲端主機上為你真實執行上述工具後的輸出結果：\n\n"
                    + "\n---\n".join(round_outputs)
                    + "\n\n"
                    + followup_instruction
                ),
            }
        )

    return {
        "ok": True,
        "text": _format_with_logs(executed_logs, reply_text),
        "model": used_model,
        "tokens_in": total_in,
        "tokens_out": total_out,
        "error": "",
    }


def _single_turn_upstream(
    messages: list[dict[str, str]],
    sys_prompt: str,
    model: str,
    agent_name: str,
    timeout_s: int,
) -> dict[str, Any]:
    minimax_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    glm_key = (os.environ.get("ZHIPUAI_API_KEY") or os.environ.get("GLM_API_KEY") or "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

    errors: list[str] = []

    # 1. If GLM key is configured and model explicitly asks for glm, try GLM first
    if glm_key and not glm_key.startswith("your_") and ("glm" in model.lower() or agent_name == "opencode"):
        for glm_url in (
            "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions",
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        ):
            res = _try_openai_compat(
                url=glm_url,
                api_key=glm_key,
                model="glm-4-flash" if "glm" not in model.lower() else model,
                sys_prompt=sys_prompt,
                messages=messages,
                timeout_s=min(timeout_s, 20),
            )
            if res["ok"]:
                res["model"] = model or res["model"]
                return res
            errors.append(f"GLM: {res['error']}")

    # 2. MiniMax Token Plan (Anthropic-compatible endpoint on minimaxi.com)
    if minimax_key and not minimax_key.startswith("your_"):
        mm_model = model if "minimax" in model.lower() else "MiniMax-M2.7"
        res = _try_minimax_anthropic(
            api_key=minimax_key,
            model=mm_model,
            sys_prompt=sys_prompt,
            messages=messages,
            timeout_s=timeout_s,
        )
        if res["ok"]:
            res["model"] = model or mm_model
            return res
        errors.append(f"MiniMax-Anthropic: {res['error']}")

        # Also try MiniMax V2 chatcompletion endpoint
        res_v2 = _try_openai_compat(
            url="https://api.minimax.chat/v1/text/chatcompletion_v2",
            api_key=minimax_key,
            model="MiniMax-Text-01",
            sys_prompt=sys_prompt,
            messages=messages,
            timeout_s=timeout_s,
        )
        if res_v2["ok"]:
            res_v2["model"] = model or "MiniMax-M3.1-Flash"
            return res_v2
        errors.append(f"MiniMax-V2: {res_v2['error']}")

    # 3. OpenAI GPT GO Platform API
    if openai_key and not openai_key.startswith("your_"):
        oa_model = model if model.startswith("gpt-") else "gpt-4o-mini"
        res_oa = _try_openai_compat(
            url="https://api.openai.com/v1/chat/completions",
            api_key=openai_key,
            model=oa_model,
            sys_prompt=sys_prompt,
            messages=messages,
            timeout_s=timeout_s,
        )
        if res_oa["ok"]:
            res_oa["model"] = model or oa_model
            return res_oa
        errors.append(f"OpenAI: {res_oa['error']}")

    # 4. OpenRouter API
    if openrouter_key and not openrouter_key.startswith("your_"):
        res_or = _try_openai_compat(
            url="https://openrouter.ai/api/v1/chat/completions",
            api_key=openrouter_key,
            model="openrouter/auto",
            sys_prompt=sys_prompt,
            messages=messages,
            timeout_s=timeout_s,
        )
        if res_or["ok"]:
            res_or["model"] = model or "openrouter/auto"
            return res_or
        errors.append(f"OpenRouter: {res_or['error']}")

    return {
        "ok": False,
        "text": "",
        "model": model,
        "tokens_in": 0,
        "tokens_out": 0,
        "error": "; ".join(errors) if errors else "No valid upstream API keys configured in .env",
    }


def _try_minimax_anthropic(
    api_key: str,
    model: str,
    sys_prompt: str,
    messages: list[dict[str, str]],
    timeout_s: int,
) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 2048,
            "system": sys_prompt,
            "messages": messages,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.minimaxi.com/anthropic/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
            blocks = raw.get("content") or []
            texts = [
                str(b.get("text") or "")
                for b in blocks
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            if not texts and blocks:
                texts = [str(b.get("text") or b.get("thinking") or "") for b in blocks if isinstance(b, dict)]
            text = "\n".join(t for t in texts if t).strip()
            usage = raw.get("usage") or {}
            if text:
                return {
                    "ok": True,
                    "text": text,
                    "model": raw.get("model") or model,
                    "tokens_in": int(usage.get("input_tokens") or 0),
                    "tokens_out": int(usage.get("output_tokens") or 0),
                    "error": "",
                }
            return {"ok": False, "error": "empty content from MiniMax Anthropic API"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _try_openai_compat(
    url: str,
    api_key: str,
    model: str,
    sys_prompt: str,
    messages: list[dict[str, str]],
    timeout_s: int,
) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                *messages,
            ],
            "temperature": 0.25,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
            choices = raw.get("choices") or []
            msg = (choices[0].get("message") or {}) if choices else {}
            content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            usage = raw.get("usage") or {}
            if content:
                return {
                    "ok": True,
                    "text": content,
                    "model": raw.get("model") or model,
                    "tokens_in": int(usage.get("prompt_tokens") or 0),
                    "tokens_out": int(usage.get("completion_tokens") or 0),
                    "error": "",
                }
            return {"ok": False, "error": f"empty response from {url}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
