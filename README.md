# 🍪 微信聊天记录分析工具

> 一个运行在 Claude Code 里的 Skill：输入联系人的名字，自动生成**双人聊天行为可视化 + AI 人格对比分析报告**。无需 API Key，分析由 Claude Code 本地完成。

---

## 效果预览

| 可视化图表 | AI 人格分析 |
|-----------|------------|
| 聊天频率日历热力图（GitHub 风格） | Big Five 人格 · 蝴蝶对比图 |
| 每小时 / 每月 / 星期发消息趋势 | MBTI 四维推断 + 置信度 |
| 双人高频词词云（左右并排对比） | 一句话性格总结 + 沟通风格 |
| 消息长度分布 | Big Five 雷达图（单人模式） |

所有内容整合为一份精美 HTML 报告，图表可直接截图发布。

---

## 使用要求

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS 12 及以上 |
| 微信版本 | Mac 客户端 4.x |
| Python | 3.10 及以上（`python3 --version` 检查） |
| Claude Code | 已安装（`claude --version` 检查） |

---

## 安装部署

**克隆仓库，在目录内打开 Claude Code，即可使用。**

```bash
git clone https://github.com/Jiang59991/wechat-analyzer.git ~/wechat-analyzer
cd ~/wechat-analyzer
claude
```

仓库内置了 `.claude/commands/analyze-wechat.md`，Claude Code 在该目录下会**自动识别**，无需任何注册步骤。

> **想在任意目录都能用？** 在 Claude Code 里说：
> `"帮我把 analyze-wechat 全局安装"`
> Claude 会自动把命令文件复制到 `~/.claude/commands/`。

---

## 快速开始

在仓库目录打开 Claude Code，直接运行：

```
/analyze-wechat
```

或者自然语言：

```
帮我分析和小明的聊天记录
```

**Skill 会自动完成从安装依赖到生成报告的全部流程。**

---

## 需要手动完成的前置步骤

以下两步是**一次性操作**，完成后后续所有分析均全自动。

### 步骤一：关闭 SIP（系统完整性保护）

macOS 的 SIP 会阻止读取微信进程中的加密密钥，必须先在恢复模式中关闭一次。

**详细步骤见 [安装指南.md](./安装指南.md)**

### 步骤二：手动运行密钥提取脚本

密钥提取需要调试器权限（lldb），Claude Code 子进程不具备此权限，**必须在系统 Terminal.app 中手动运行**。

Skill 会给出完整命令，你复制粘贴到 Terminal.app 执行，然后在微信里依次点开几个聊天窗口触发密钥捕获即可。

**完整操作说明见 [安装指南.md](./安装指南.md)**

> 这两步只需做一次。完成后可以立刻重新开启 SIP，之后所有分析完全自动。

---

## Skill 会问你哪些问题？

整个流程**最多只会被问 3 次**：

| 时机 | 问题 | 频率 |
|------|------|------|
| 启动时 | 你想分析和谁的聊天记录？ | 每次（除非命令里已指定） |
| 首次运行（仅 Level 3） | 确认微信已登录并给出手动命令 | 仅首次提取密钥时 |
| 按需 | 找到多个同名联系人，选择哪个？ | 有重名联系人时 |

其余所有步骤均**全自动完成**，无需干预。

---

## 输出文件

分析完成后，所有文件保存在工具目录的 `wechat_analysis_output/` 下（默认 `~/.claude/wechat-analyzer/wechat_analysis_output/`）：

```
wechat_analysis_output/
├── report.html              ← 完整 HTML 报告（浏览器打开）
├── report.css               ← 报告样式文件（与 report.html 同目录）
├── personality_result.json  ← 自己的 AI 分析结果
├── partner_result.json      ← 对方的 AI 分析结果（双人模式）
├── personality_raw.json     ← 最终输出的分析原始数据
└── charts/
    ├── hourly.png           ← 24 小时发消息分布
    ├── monthly_trend.png    ← 月度消息趋势
    ├── weekday_bar.png      ← 星期分布
    ├── word_cloud_pair.png  ← 双人高频词词云（有对方数据时）
    ├── word_cloud.png       ← 单人词云（仅自己数据时）
    ├── length_dist.png      ← 消息长度分布
    └── radar.png            ← Big Five 雷达图（单人模式）
```

---

## 隐私说明

- 所有数据处理在**本地**完成
- AI 人格分析由 **Claude Code 本身**完成，不需要 Anthropic API Key，不向外部发送消息内容
- 不会收集或上传任何数据到其他地方
- 请勿用于分析他人设备上的数据

---

## 技术流程

见 [SKILL.md](./SKILL.md)

---

*macOS 12+ · WeChat 4.x · Python 3.10+ · Claude Code*
