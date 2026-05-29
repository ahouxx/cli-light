CLI Light v0.2 for Windows
桌面置顶状态灯，实时显示 AI CLI 工具的运行状态
Desktop always-on-top traffic light for AI CLI tools

🔵 总数 / Total    🟢 空闲 / Idle    🟠 运行中 / Running（闪烁 blink）   🔴 需确认 / Needs Input

✅ Claude Code 已完美适配（CLI + VS Code 插件）
✅ Claude Code fully supported (CLI + VS Code extension)
🟡 Kimi Code / OpenCode / Codex 适配中 — In progress

效果展示 / Screenshots
VS Code	Customize
与 VS Code 融为一体 / Blends into VS Code	深色/透明，横/竖布局 / Dark or transparent, H/V layout
Large	Small
放大显示 — 老板一眼就看到 / Large — your boss can see it	小到当托盘指示灯 / Small as a tray indicator
支持 CLI / Supported CLIs
CLI	状态 / Status
Claude Code	✅ 完美适配 / Perfect
Kimi Code	🟡 适配中 / WIP
OpenCode	🟡 适配中 / WIP
Codex CLI	🟡 适配中 / WIP
配色方案 / Color Schemes
默认 / Default 🔵 #2266CC　🟢 #009933　🟠 #E06000　🔴 #CC1111

海洋 / Ocean 🔵 #0077B6　🟢 #00B4D8　🟠 #48CAE4　🔴 #E63946

森林 / Forest 🔵 #2D6A4F　🟢 #52B788　🟠 #D4A373　🔴 #E76F51

霓虹 / Neon 🔵 #7C3AED　🟢 #06D6A0　🟠 #FFD166　🔴 #FF6B6B

琥珀 / Amber 🔵 #8B5CF6　🟢 #10B981　🟠 #F59E0B　🔴 #EF4444

功能一览 / Features
功能 / Feature	说明 / Description
进程自动检测 / Process scan	每 3 秒扫描 CLI 进程 / Scans CLI processes every 3s
Hook 状态上报 / Hook reporting	任务状态实时推送 / Real-time state push via hooks
一键安装 / One-click install	自动配置 Hook + 创建快捷方式 / Auto-configure hooks + shortcuts
多实例追踪 / Multi-instance	PID 区分 Agent / Track by PID
自由拖拽 / Drag	拖拽移动，位置记忆 / Drag to move, remembers position
四种主题 / 4 themes	深色 / 浅色 / 透明 / 跟随系统 / Dark / Light / Transparent / System
5 种配色 / 5 schemes	默认 / 海洋 / 森林 / 霓虹 / 琥珀
七档缩放 / 7 zoom levels	75% ~ 500%
横竖布局 / H/V layout	横向或竖向排列 / Horizontal or vertical
显示边框 / Dividers	可选方形边框 / Optional square borders
干净卸载 / Clean uninstall	一键移除所有配置 / Remove all configs
安装 / Install
# 一键安装（自动复制到 %LOCALAPPDATA%\CLI Light + 配置 Hook + 创建快捷方式）
# One-click install (auto-copy to %LOCALAPPDATA% + configure hooks + create shortcuts)
powershell -ExecutionPolicy Bypass -File install.ps1

# 重启 CLI 终端，开始使用
# Restart CLI terminal to activate
Hook 生命周期 / Hook Lifecycle
UserPromptSubmit ──→ 🟠 橙灯 / Orange (running)
        │
        ▼ 需要授权 / Needs auth
PermissionRequest ──→ 🔴 红灯 / Red (needs_input)
        │
        ▼ 授权通过 / Approved
PostToolUse ──→ 🟠 橙灯 / Orange (running)
        │
        ▼ 任务完成 / Done
Stop ──→ 🟢 绿灯 / Green (done)
操作 / Controls
操作 / Action	说明 / Description
拖拽 / Drag	移动窗口 / Move window
双击 / Double-click	紧急关闭 / Emergency close
右键 / Right-click	菜单：置顶 / 边框 / 主题 / 配色 / 缩放 / 样式 / 退出
环境要求 / Requirements
Windows 10 / 11
Python 3.10+（纯标准库，零外部依赖 / stdlib only, zero dependencies）
CLI Light · MIT License
