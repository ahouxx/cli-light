# CLI Light <sup>Windows</sup> v0.2

Desktop always-on-top traffic light for Windows that shows real-time status of your AI coding CLI tools (Claude Code, Kimi Code, OpenCode, Codex).

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
| Claude Code | `claude.exe` | UserPromptSubmit / PermissionRequest / PostToolUse / Stop | ✅ Perfect |
| Kimi Code | `kimi-cli.exe` | UserPromptSubmit / PreToolUse / PostToolUse / Stop | WIP |
| OpenCode | `opencode.exe` | UserPromptSubmit / Stop (native); full via `opencode-claude-hooks` plugin | WIP |
| Codex CLI | `codex.exe` | UserPromptSubmit / PermissionRequest / PostToolUse / Stop | WIP¹ |

✅ Claude Code is fully supported (both CLI and VS Code extension). Other CLIs have minor compatibility issues being worked on.

## Usage

- ¹ Codex requires `[features] hooks = true` in `~/.codex/config.toml` for hook events to fire. The installer adds this automatically.
- **Drag** to move the window
- **Right-click** for menu (toggle always-on-top / layout / color scheme / scale / quit)
- Drag to screen edges to **snap**
- Right-click menu → **样式** to switch between horizontal and vertical layout

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


# CLI Light <sup>Windows</sup> v0.2 · 桌面 CLI 状态灯

桌面置顶状态灯，实时显示终端 AI 编程助手（Claude Code / Kimi Code / OpenCode / Codex）的运行状态。

✅ **Claude Code 已完美适配**（CLI 及 VS Code 插件均可正常使用）。其他 CLI 存在少量兼容性问题，正在修复中。

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
- **右键**菜单 → 置顶 / 显示边框 / 主题 / 配色 / 缩放 / 样式（横向/竖向） / 退出

## 已知限制

- OpenCode 原生仅支持 `UserPromptSubmit` 和 `Stop` 事件；安装 `opencode-claude-hooks` npm 插件可获得完整支持
- 独占全屏程序（DirectX / Vulkan）下无法显示
- 部分系统上 `pythonw.exe` 会短暂闪现控制台窗口（使用 `launch.vbs` 可避免）
