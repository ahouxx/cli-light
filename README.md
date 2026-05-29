# CLI Light v0.2

> 🔵 Total · 🟢 Idle · 🟠 Running · 🔴 Needs Input
>
> 桌面置顶状态灯，实时显示 AI CLI 工具的运行状态
> Desktop always-on-top traffic light for AI CLI tools

✅ **Claude Code 完美适配** — CLI + VS Code 插件均支持
✅ **Claude Code fully supported** — CLI + VS Code extension
🟡 Kimi Code / OpenCode / Codex 适配中

---

## 效果展示

| | |
|:---:|:---:|
| ![1](https://raw.githubusercontent.com/ahouxx/cli-light/main/cli-light/docs/screenshots/vscode.png) | ![2](https://raw.githubusercontent.com/ahouxx/cli-light/main/cli-light/docs/screenshots/customize.png) |
| 与 VS Code 融为一体 | 深色/透明，横/竖布局 |
| ![3](https://raw.githubusercontent.com/ahouxx/cli-light/main/cli-light/docs/screenshots/large.png) | ![4](https://raw.githubusercontent.com/ahouxx/cli-light/main/cli-light/docs/screenshots/small.png) |
| 放大显示，一眼就看到 | 小到当托盘指示灯 |

---

## 支持 CLI

| CLI | 状态 |
|-----|:----:|
| **Claude Code** | ✅ 完美适配 |
| Kimi Code | 🟡 适配中 |
| OpenCode | 🟡 适配中 |
| Codex CLI | 🟡 适配中 |

---

## 配色方案

| 方案 | 颜色 |
|------|------|
| **默认** | 🔵 `#2266CC` 🟢 `#009933` 🟠 `#E06000` 🔴 `#CC1111` |
| **海洋** | 🔵 `#0077B6` 🟢 `#00B4D8` 🟠 `#48CAE4` 🔴 `#E63946` |
| **森林** | 🔵 `#2D6A4F` 🟢 `#52B788` 🟠 `#D4A373` 🔴 `#E76F51` |
| **霓虹** | 🔵 `#7C3AED` 🟢 `#06D6A0` 🟠 `#FFD166` 🔴 `#FF6B6B` |
| **琥珀** | 🔵 `#8B5CF6` 🟢 `#10B981` 🟠 `#F59E0B` 🔴 `#EF4444` |

---

## 功能

- **进程自动检测** — 每 3 秒扫描 CLI 进程
- **Hook 状态上报** — 任务状态实时推送
- **一键安装** — 自动配置 Hook + 快捷方式
- **多实例追踪** — PID 区分 Agent
- **自由拖拽** — 位置记忆
- **四种主题** — 深色 / 浅色 / 透明 / 跟随系统
- **5 种配色** — 默认 / 海洋 / 森林 / 霓虹 / 琥珀
- **七档缩放** — 75% ~ 500%
- **横竖布局** — 横向或竖向
- **显示边框** — 可选方形边框
- **重复启动保护** — 检测到已有实例时弹窗
- **干净卸载** — 一键移除所有配置

---

## 安装

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
