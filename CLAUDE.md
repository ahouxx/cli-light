# CLI Light — 桌面 CLI 状态灯

## 项目概述

Windows 桌面置顶状态灯，实时显示终端 CLI（Claude Code / Kimi Code / OpenCode / Codex）的运行状态。

- **蓝灯**：CLI 总数（进程检测）
- **绿灯**：空闲
- **橙灯**：运行中（闪烁）
- **红灯**：需确认/授权
- **布局**：支持横向/竖向切换（右键菜单 → 样式）

## 架构

```
cli_light.py          # 主程序（tkinter GUI + HTTP 服务 + 进程扫描）
run.bat               # 双击启动（pythonw，无控制台）
launch.vbs            # 自动探测 Python 路径 + 无控制台启动（install.ps1 自动生成）
hooks/
  notify.ps1          # Hook 通知脚本（POST 到 localhost:9876，回退进程树找 CLI PID）
  claude-hooks.json   # Hook 配置参考模板（推荐通过 install.ps1 自动配置）
install.ps1           # 一键安装/卸载 hook（支持 Claude Code / Kimi Code / OpenCode）
```

## 核心机制

1. **进程扫描**：每 3 秒 `Get-Process` 检测 `claude.exe` / `kimi-cli.exe` / `opencode.exe` / `codex.exe`
2. **Hook 上报**：各 CLI 通过 hook 机制 POST 状态到 `localhost:9876/hook`，携带 `{agent, state}`
3. **Per-agent 追踪**：`notify.ps1` 回溯进程树找到 CLI 进程 PID 作为 Agent ID，多实例互不干扰

## Hook 生命周期

```
UserPromptSubmit → 橙灯（running）
  ↓ 需要授权
PreToolUse / PermissionRequest → 红灯（needs_input）
  ↓ 授权通过 → 工具执行
PostToolUse → 橙灯恢复（running）
  ↓ 任务完成
Stop → 绿灯（done）
```

- Codex CLI 需在 `~/.codex/config.toml` 中启用 `[features] hooks = true`（install.ps1 自动配置）
- Claude Code 需重启会话后 hooks 才生效（install.ps1 自动配置 `~/.claude/settings.json`）

## 已知问题

- OpenCode 原生仅支持 UserPromptSubmit / Stop 两个 hook 事件，完整支持需安装 `opencode-claude-hooks` 插件
- 独占全屏模式（DX/Vulkan）下窗口无法显示
