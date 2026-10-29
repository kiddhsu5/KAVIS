# K.H.A.V.I.S. 部署指南（騰訊雲 / 任一 Ubuntu VM）

> 目標架構：整個項目的運行在雲端 VM 上，本地 Mac 只做開發。
> 一鍵安裝：`bash deploy/install.sh`

## 架構總覽

```
瀏覽器 ── https ──► nginx (443) ──► khavis-workbench (127.0.0.1:8080)
                                        │
                                        ├─ K.A.V.I.S. 內建 agent
                                        │   ├─ 本地：LangGraph 7 角色團隊協同
                                        │   └─ 遠端：kavis-adapter (127.0.0.1:18081)
                                        │            └─ hermes -z（openclaw × hermes 環境）
                                        ├─ Telegram bot（khavis-bot，選配）
                                        └─ 供應商 API pools（.env keys）
```

- **K.A.V.I.S.** 是項目內建的唯一協同 agent：對話中勾選即調度本地 LangGraph
  團隊（Planner/Coder×2/Debater/Critic/Verifier/Learner）；裝了
  `kavis-adapter` 後，遠端 openclaw × hermes 節點是同一個 agent 的雲端執行點。

## 一鍵安裝（全新 VM）

```bash
# 基本安裝（~/khavis，port 8080）
bash deploy/install.sh

# 完整安裝：含 K.A.V.I.S. 遠端派工橋接器（需已裝 hermes）
bash deploy/install.sh --with-adapter

# 自訂路徑與埠
bash deploy/install.sh --home /opt/khavis --port 8080 --with-adapter
```

安裝器行為：環境檢查（Python ≥ 3.11）→ clone repo → venv + 依賴 → `.env`
初始化（已存在不覆蓋）→ systemd 服務 → 健康檢查。

## 既有非 git 部署的遷移

若機器上已有舊版 `~/khavis`（scp 檔案堆），安裝器會把它搬到
`~/khavis-preinstall-<時間戳>` 再 clone。之後手動回復運行資料：

```bash
OLD=~/khavis-preinstall-<時間戳>
cp "$OLD/.env" ~/khavis/.env
cp "$OLD/config/workbench_catalog.json" ~/khavis/config/ 2>/dev/null || true
cp -r "$OLD/workspace" ~/khavis/ 2>/dev/null || true
cp -r "$OLD/logs" ~/khavis/ 2>/dev/null || true
sudo systemctl restart khavis-workbench
```

## 日常維運

| 操作 | 指令 |
| --- | --- |
| 升級版本 | `git -C ~/khavis pull && sudo systemctl restart khavis-workbench` |
| 看日誌 | `journalctl -u khavis-workbench -n 50 --no-pager` |
| 重啟 | `sudo systemctl restart khavis-workbench` |
| K.A.V.I.S. 橋接器 | `systemctl --user status kavis-adapter` |
| 橋接器健康 | `curl -s http://127.0.0.1:18081/healthz` |

## 對外服務（nginx）

監聽 127.0.0.1:8080，僅本機可達。對外請以 nginx 反代並上 TLS：

```nginx
server {
    listen 443 ssl;
    server_name khavis.example.com;
    ssl_certificate     /etc/ssl/certs/khavis.pem;
    ssl_certificate_key /etc/ssl/private/khavis.key;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_read_timeout 300s;   # 多 Agent 協同可能超過 60s
    }
}
```

## 環境變數

見 `.env.example`。重點：

- 供應商 keys（`MINIMAX_API_KEY`、`ZHIPUAI_API_KEY`…）— BYOK，各自計費
- `KHAVIS_API_KEY` — Workbench 寫操作令牌（對外服務強烈建議設定）
- `KAVIS_TENCENT_DISPATCH_URL` — K.A.V.I.S. 遠端派工通道（`--with-adapter` 自動寫入）
- `KAVIS_TENCENT_ENDPOINT` — 騰訊雲節點健康探測位址（預設 443 狀態頁）
