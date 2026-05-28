# CLI Light

Desktop always-on-top traffic light that shows real-time status of your AI coding CLI tools (Claude Code, Kimi Code, OpenCode).

<p align="center">
  <em>Blue=total &nbsp; Green=idle &nbsp; Orange=running (blink) &nbsp; Red=needs approval</em>
</p>

## Light Meaning

| Light | Color | Meaning |
|-------|-------|---------|
| Blue | `#2266CC` | **Total** — number of CLI processes detected |
| Green | `#009933` | **Idle** — waiting for input |
| Orange | `#E06000` | **Running** — executing a task (blinks) |
| Red | `#CC1111` | **Needs input** — waiting for user approval |

Each light shows the count of agents in that state.

## Requirements

- Windows 10+
- Python 3.10+ (standard library only, no pip dependencies)

## Quick Start

### 1. Launch the indicator

```powershell
pythonw cli_light.py
```

Or double-click `run.bat` / `launch.vbs` (no console window).

### 2. Install hooks (one-time)

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

This auto-detects your installed CLI tools and registers hooks so they report status changes. Restart your CLI terminals afterward.

To remove hooks:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
```

### 3. That's it

Run Claude Code / Kimi Code / OpenCode — the lights update automatically.

## Supported CLIs

| CLI | Process | Hooks | Status |
|-----|---------|-------|--------|
| Claude Code | `claude.exe` | UserPromptSubmit / PermissionRequest / PostToolUse / Stop | Full |
| Kimi Code | `kimi-cli.exe` | UserPromptSubmit / PreToolUse / PostToolUse / Stop | Full |
| OpenCode | `opencode.exe` | UserPromptSubmit / Stop (native); full via `opencode-claude-hooks` plugin | Good |
| Codex CLI | `codex.exe` | userPromptSubmitted / postToolUse / Stop | Good |

## Usage

- **Drag** to move the window
- **Right-click** for menu (toggle always-on-top / quit)
- Drag to screen edges to **snap**

## How It Works

1. **Process scanner**: Polls `Get-Process` every 3s — counts running `claude.exe`, `kimi-cli.exe`, `opencode.exe`
2. **Hook server**: HTTP on `localhost:9876` — CLI hooks POST `{state, agent}` on state changes
3. **Per-agent tracking**: `notify.ps1` walks the process tree to find the CLI PID, used as agent ID so multiple instances don't interfere

## Hook Lifecycle

```
UserPromptSubmit -> Orange (running)
     |
     v  (tool needs approval)
PermissionRequest -> Red (needs_input)
     |
     v  (approved -> tool runs)
PostToolUse -> Orange (running)
     |
     v  (task complete)
Stop -> Green (done)
```

## Known Limitations

- OpenCode native hooks only expose `UserPromptSubmit` and `Stop` events; install `opencode-claude-hooks` npm plugin for full coverage
- Exclusive fullscreen apps (DirectX / Vulkan) hide the overlay
- `pythonw.exe` may briefly flash a console window on some systems (use `launch.vbs` to avoid)

## License

MIT — see [LICENSE](LICENSE)


# CLI Light · 桌面 CLI 状态红绿灯

桌面置顶红绿灯，实时显示终端 AI 编程助手（Claude Code / Kimi Code / OpenCode）的运行状态。

## 灯光说明

| 灯 | 颜色 | 含义 |
|---|------|------|
| 蓝 | `#2266CC` | **总数** — 检测到的 CLI 进程数 |
| 绿 | `#009933` | **空闲** — 等待输入 |
| 橙 | `#E06000` | **运行中** — 正在执行任务（闪烁） |
| 红 | `#CC1111` | **需确认** — 等待用户授权 |

## 环境要求

- Windows 10+
- Python 3.10+（仅标准库，无需 pip 安装依赖）

## 快速开始

### 1. 启动程序

```powershell
pythonw cli_light.py
```

或双击 `run.bat` / `launch.vbs`（无控制台窗口）。

### 2. 安装 Hook（一次性）

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

自动检测已安装的 CLI 工具并注册 hook，使其能上报状态变化。安装后**重启** CLI 终端生效。

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
```

### 3. 完成

打开 Claude Code / Kimi Code / OpenCode，灯光自动更新。

## 操作

- **拖动**窗口移动位置
- **右键**菜单 → 置顶显示 / 退出
- 拖到屏幕边缘**自动吸附**

## 已知限制

- OpenCode 原生仅支持 `UserPromptSubmit` 和 `Stop` 事件；安装 `opencode-claude-hooks` npm 插件可获得完整支持
- 独占全屏程序（DirectX / Vulkan）下无法显示
- 部分系统上 `pythonw.exe` 会短暂闪现控制台窗口（使用 `launch.vbs` 可避免）
