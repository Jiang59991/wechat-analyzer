# SKILL.md · /analyze-wechat 技术文档

本文档说明 Skill 的完整执行流程、每步调用的脚本，以及哪些节点需要用户操作。

---

## 流程总览

```
用户输入 /analyze-wechat [联系人名]
         │
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Step 1   确认分析目标                           ← 未指定时询问  │
  │  Step 2   安装 Python 依赖（venv 隔离）           自动           │
  │  Step 3   安装解密工具                           自动（首次）     │
  │  Step 4   三级数据库状态检查                                    │
  │    ├─ Level 1  .db 文件已存在？                  → 跳至 Step 7  │
  │    ├─ Level 2  wechat_keys.json 已存在？         → 跳至 Step 6  │
  │    └─ Level 3  两者均无                          → Step 5       │
  │  Step 5   【手动】提取密钥（Terminal.app）  ← 仅首次，用户操作    │
  │  Step 6   解密数据库                             自动           │
  │  Step 7   写入配置                               自动           │
  │  Step 8   导出联系人消息                         ← 多个同名时询问 │
  │  Step 9a  生成图表 + 分析输入文件                自动           │
  │  Step 9b  Claude 读取输入，完成人格分析           自动（Claude Code）│
  │  Step 9c  生成完整 HTML 报告                     自动           │
  │  Step 10  打开报告                               自动           │
  └──────────────────────────────────────────────────────────────┘
```

**最多交互 3 次**：确认联系人 / 首次密钥提取引导 / 多个同名联系人时选择。

---

## 详细步骤

---

### Step 1 · 确认分析目标

**触发条件**：用户未在命令中指定联系人

**询问内容**：
> 你想分析和谁的聊天记录？（输入对方的备注名或微信昵称）

---

### Step 2 · 安装 Python 依赖

**触发条件**：自动

```bash
VENV="$TOOL_DIR/.venv"
[ ! -d "$VENV" ] && python3 -m venv "$VENV"
"$VENV/bin/python" -c "import pandas, jieba, wordcloud, matplotlib" 2>/dev/null \
  || pip install -r "$TOOL_DIR/requirements.txt"
```

使用项目内 `.venv` 虚拟环境，不污染系统 Python。后续所有 Python 命令均使用 `$VENV/bin/python`。

**依赖库**：`pandas`, `jieba`, `wordcloud`, `matplotlib`, `numpy`, `zstd`（可选，解压新版微信消息）

---

### Step 3 · 安装解密工具

**触发条件**：自动，检测 `~/Documents/wechat-db-decrypt-macos` 是否存在

```bash
[ ! -d "$DECRYPT_TOOL" ] && \
  git clone https://github.com/Thearas/wechat-db-decrypt-macos.git "$DECRYPT_TOOL"
which sqlcipher >/dev/null 2>&1 || brew install sqlcipher
```

首次约需 10 秒，后续跳过。

---

### Step 4 · 三级数据库状态检查

> **核心原则**：已解密过的用户永远不需要再碰 SIP。

#### Level 1：检查解密数据库是否已存在

```bash
ls "$DECRYPT_TOOL/decrypted/"*.db 2>/dev/null && echo "DB_FOUND"
```

**若 DB_FOUND**：直接跳至 Step 7，跳过所有解密步骤。

#### Level 2：检查密钥文件是否已存在

```bash
ls "$DECRYPT_TOOL/wechat_keys.json" 2>/dev/null && echo "KEY_FOUND"
```

**若 KEY_FOUND**：密钥已有，直接跳至 Step 6 执行解密（无需 SIP，无需手动操作）。

#### Level 3：两者均无 → 需要提取密钥

```bash
csrutil status
```

- 若输出包含 `enabled`：**停止**，告知用户需要先关闭 SIP，参考安装指南，完成后重新运行
- 若输出包含 `disabled`：继续 Step 5

---

### Step 5 · 【手动】提取微信密钥

> **为什么需要手动**：`find_key.py` 通过 `lldb` 附加到微信进程读取内存中的密钥。
> Claude Code 的子进程不具备 `taskport` 权限，**必须由用户在系统 Terminal.app 中执行**。

**操作前询问（AskUserQuestion）**：
> 准备从微信内存中提取密钥。运行前请确认：
> ① 微信 Mac 客户端当前处于**登录状态**
> ② 近期在微信里打开过几个对话（确保消息已写入本地）
>
> 确认后输入"继续"，我会给出需要在 Terminal.app 中执行的命令。

**确认后给出以下命令，让用户复制到 Terminal.app 执行**：

```bash
cd ~/Documents/wechat-db-decrypt-macos
PYTHONPATH="/Library/Developer/CommandLineTools/Library/PrivateFrameworks/LLDB.framework/Versions/A/Resources/Python" \
/Library/Developer/CommandLineTools/usr/bin/python3.9 find_key.py
```

**同时告知用户操作步骤**：
1. 脚本启动后微信会**短暂卡住**（正在附加进程，约 2～5 分钟，属正常现象）
2. 微信恢复响应后，切换到微信，**依次点开 3～5 个不同的聊天窗口**
3. 终端出现 `[!] Found new key!` 表示成功
4. 按 `Ctrl+C` 停止，`wechat_keys.json` 自动保存
5. 完成后回到 Claude Code 告知已完成

**错误处理**：
| 错误信息 | 处理方式 |
|---------|---------|
| `ModuleNotFoundError: No module named 'lldb'` | 确认使用的是 Python 3.9，`_lldb` 只支持 3.9 |
| 架构错误（Apple Silicon） | 命令前加 `arch -arm64` |
| `Permission denied` / `process attach denied` | SIP 未关闭，返回 Level 3 |

**密钥提取成功后，主动提示用户**：
> 密钥已提取完成！现在可以立刻重新开启 SIP 了——后续解密和所有分析都不需要 SIP。
>
> 步骤：关机 → 恢复模式 → 终端执行 `csrutil enable` → `reboot`
>
> 也可以先继续完成本次解密，之后再重启开启。

---

### Step 6 · 解密数据库

**触发条件**：Level 2（密钥已有）或 Step 5 完成后

```bash
cd "$DECRYPT_TOOL" && python3 decrypt_db.py 2>&1
```

成功后在 `$DECRYPT_TOOL/decrypted/` 生成 `.db` 文件，记录路径，继续 Step 7。

---

### Step 7 · 写入配置

**触发条件**：自动，找到数据库路径后

```json
{
  "decrypted_db_dir": "<自动检测到的路径>",
  "output_dir": "<项目目录>/tools/wechat_analyzer/wechat_analysis_output"
}
```

写入 `$TOOL_DIR/config.json`，后续所有脚本从此文件读取路径。

---

### Step 8 · 导出联系人消息

**触发条件**：自动

```bash
cd "$TOOL_DIR" && "$VENV/bin/python" export_contact.py --contact "<联系人名>"
```

`export_contact.py` 会：
- 模糊搜索联系人（备注名 / 昵称 / 微信号）
- 导出所有文本消息为 `export_<联系人名>.csv`
- 自动查找并导出双方头像（存入 meta sidecar JSON）
- 输出 `EXPORT_PATH:<路径>` 和 `META_PATH:<路径>` 供后续步骤使用

**三种情况**：

| 情况 | 处理方式 |
|------|---------|
| 唯一匹配 | 自动导出，继续 |
| 多个匹配 | 展示列表，询问用户选择编号 |
| 未找到 | 运行 `--list-contacts` 展示全部联系人，让用户重新输入名称 |

---

### Step 9a · 生成图表与分析输入

**触发条件**：自动

```bash
cd "$TOOL_DIR" && "$VENV/bin/python" main.py "$CSV_PATH" 2>&1
```

生成内容：
- `charts/hourly.png`、`monthly_trend.png`、`weekday_bar.png`、`length_dist.png`
- `charts/word_cloud_pair.png`（双人词云）或 `charts/word_cloud.png`（单人词云）
- `wechat_analysis_output/personality_input.json`（自己的消息样本，供分析）
- `wechat_analysis_output/partner_input.json`（对方的消息样本，供分析，若有）

---

### Step 9b · Claude 完成人格分析

**触发条件**：自动（Claude Code 直接执行，无需外部 API）

**同时**读取两个文件：
```
$TOOL_DIR/wechat_analysis_output/personality_input.json
$TOOL_DIR/wechat_analysis_output/partner_input.json（若存在）
```

对两份数据的 `sample_messages` 预处理：**过滤超过 150 字的消息**（通常为转发文档），保留日常对话。

**作为语言学人格研究者**，基于以下维度独立分析双方：
- `sample_messages`：日常对话样本（直接引用原文作为 evidence）
- `top_words`：词频 Top 30（揭示关注领域和话题偏好）
- `features`：量化语言特征（观点词率、情绪词率、规划词率等）
- `stats_summary`：基础统计（活跃时段、消息量、时间跨度）

**分析要求**：
- `evidence` 必须是 `sample_messages` 中真实出现的原文片段
- Big Five 是分析重点，MBTI 仅供参考（在 note 中注明置信度原因）
- `reliability` 字段：客观描述本次数据的实际情况（样本量、时间跨度、实际观察到的话题分布），只写事实，不做推测

**分析结果分别写入**：
```
写入：$TOOL_DIR/wechat_analysis_output/personality_result.json  （自己）
写入：$TOOL_DIR/wechat_analysis_output/partner_result.json      （对方，若有数据）
```

**输出 JSON 结构**：

```json
{
  "big5": {
    "openness":          {"score": 0-100, "level": "低/中/高", "evidence": "原文片段", "note": "一句解读"},
    "conscientiousness": {"score": 0-100, "level": "低/中/高", "evidence": "原文片段", "note": "一句解读"},
    "extraversion":      {"score": 0-100, "level": "低/中/高", "evidence": "原文片段", "note": "一句解读"},
    "agreeableness":     {"score": 0-100, "level": "低/中/高", "evidence": "原文片段", "note": "一句解读"},
    "neuroticism":       {"score": 0-100, "level": "低/中/高", "evidence": "原文片段", "note": "一句解读"}
  },
  "mbti": {
    "type": "四字母",
    "confidence": "低/中/高",
    "note": "置信度说明（样本特征、信号强弱）",
    "dims": {
      "EI": {"lean": "E或I", "strength": "明显/轻微", "reason": "简短理由"},
      "SN": {"lean": "S或N", "strength": "明显/轻微", "reason": "简短理由"},
      "TF": {"lean": "T或F", "strength": "明显/轻微", "reason": "简短理由"},
      "JP": {"lean": "J或P", "strength": "明显/轻微", "reason": "简短理由"}
    }
  },
  "style": {
    "one_line": "一句生动描述这个人的聊天风格",
    "summary": "2-3句综合描述",
    "strengths": ["沟通特点1", "沟通特点2", "沟通特点3"],
    "fun_facts": ["有趣发现1", "有趣发现2"]
  },
  "reliability": "本次分析基于约X天、Y条消息中采样的Z条对话。[基于实际数据描述样本特征]。人格判断以语言习惯和行为模式为主，受数据量和话题覆盖影响，仅作参考。"
}
```

> 若 `partner_input.json` 不存在（对方消息为空或过滤后为空），跳过对方分析，只写 `personality_result.json`。

---

### Step 9c · 生成完整报告

**触发条件**：自动

```bash
cd "$TOOL_DIR" && "$VENV/bin/python" main.py "$CSV_PATH" \
  --personality-result wechat_analysis_output/personality_result.json \
  --partner-personality-result wechat_analysis_output/partner_result.json \
  --partner-name "<联系人名>" 2>&1
```

若无对方分析结果，省略 `--partner-personality-result` 参数，以单人模式生成报告。

生成文件：
- `report.html` + `report.css`（完整 HTML 报告及样式）
- `charts/radar.png`（单人模式下的 Big Five 雷达图）
- `personality_raw.json`（最终人格分析原始数据备份）

---

### Step 10 · 打开报告

**触发条件**：自动

```bash
open "$TOOL_DIR/wechat_analysis_output/report.html"
```

**Skill 最终告知用户**：
- 报告已在浏览器打开
- 图表截图路径：`wechat_analysis_output/charts/`
- 如需清理导出的原始消息文件：`rm "$TOOL_DIR"/export_*.csv`

若 SIP 仍为关闭状态，提示用户重新开启：

```bash
csrutil status
# 若输出包含 disabled，提示用户进恢复模式执行 csrutil enable
```

---

## 用户全程交互汇总

| # | 何时 | 问什么 | 频率 |
|---|------|--------|------|
| 1 | 启动时 | 分析哪个联系人？ | 每次（除非命令里已指定） |
| 2 | 首次运行（Level 3） | 确认微信已登录，给出 Terminal 命令 | 仅首次提取密钥时 |
| 3 | 有多个同名联系人 | 选择哪个？ | 按需 |

**正常复用场景（数据库已存在）：仅被问第 1 次，其余全自动。**

---

## 错误速查

| 错误 | 自动处理 | 需用户操作 |
|------|---------|-----------|
| Python 模块缺失 | 自动 pip install | — |
| 解密工具未安装 | 自动 git clone + brew install sqlcipher | — |
| SIP 已启用 | 停止并给出指引 | 进恢复模式关闭 SIP，重启 |
| 密钥提取失败（权限） | 提示检查 SIP | 确认 SIP 已关闭 |
| 密钥提取失败（架构） | 给出 arch -arm64 命令 | 在 Terminal.app 重试 |
| 联系人未找到 | 展示全部联系人列表 | 确认正确名称 |
| 多个同名联系人 | 展示列表 | 输入编号 |
| personality_input.json 不存在 | 重新运行 Step 9a | — |
| 数据库路径不存在 | 重新搜索路径 | 若仍失败则重新执行解密 |

---

## 模块说明

```
main.py           主流程编排（Step 9a + 9c）
data_loader.py    加载 CSV，过滤非文本消息，区分自己/对方消息
stats.py          统计分析（时段分布、词频、消息长度、每日消息数）
visualizer.py     图表生成（matplotlib + wordcloud）
sampler.py        智能采样（分层 + 优先观点/情感类消息）
personality.py    语言特征提取（供分析输入使用）
report.py         HTML 报告生成（双人对比 / 单人模式自适应）
export_contact.py 从解密数据库导出指定联系人消息 + 头像
```

---

*更多内容见 [README.md](./README.md) 和 [安装指南.md](./安装指南.md)*
