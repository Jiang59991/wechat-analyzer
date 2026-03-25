# /analyze-wechat

分析微信聊天记录，自动完成从环境安装到生成报告的全流程。

## 路径约定

```bash
# 自动检测：如果当前目录就是工具目录，直接使用；否则从环境变量或默认位置读取
if [ -f "$(pwd)/export_contact.py" ]; then
  TOOL_DIR="$(pwd)"
else
  TOOL_DIR="${WECHAT_ANALYZER_DIR:-$HOME/.claude/wechat-analyzer}"
fi
DECRYPT_TOOL="${WECHAT_DECRYPT_DIR:-$HOME/Documents/wechat-db-decrypt-macos}"
```

---

## 完整流程

### 步骤 1：安装 Python 依赖（自动）

```bash
# 使用 venv 隔离依赖，避免污染系统 Python
VENV="$TOOL_DIR/.venv"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
"$VENV/bin/python" -c "import pandas, anthropic, jieba, wordcloud, matplotlib" 2>/dev/null \
  || pip install -r "$TOOL_DIR/requirements.txt"
```

后续所有 `python3` 命令均替换为 `"$VENV/bin/python"`。

---

### 步骤 2：安装解密工具（自动，首次）

解密工具依赖 `sqlcipher`（用于解密数据库）和系统自带的 `lldb`（用于提取密钥，需要 SIP 关闭）。

```bash
# 安装解密工具仓库
if [ ! -d "$DECRYPT_TOOL" ]; then
  git clone https://github.com/Thearas/wechat-db-decrypt-macos.git "$DECRYPT_TOOL"
  echo "DECRYPT_INSTALLED"
else
  echo "DECRYPT_EXISTS"
fi

# 检查并安装 sqlcipher
which sqlcipher >/dev/null 2>&1 || brew install sqlcipher
```

---

### 步骤 3：三级状态检查（最小化 SIP 操作）

> 核心原则：只有在密钥文件不存在时才需要 SIP 关闭。已解密的用户永远不需要再碰 SIP。

#### Level 1：检查解密数据库是否已存在

```bash
ls "$DECRYPT_TOOL/decrypted/"*.db 2>/dev/null && echo "DB_FOUND" || echo "DB_NOT_FOUND"
```

**若 `DB_FOUND`**：数据库就绪，直接跳到步骤 5（询问联系人），完全跳过所有 SIP 相关步骤。

---

#### Level 2：检查密钥文件是否已存在（SIP 无关）

```bash
ls "$DECRYPT_TOOL/wechat_keys.json" 2>/dev/null && echo "KEY_FOUND" || echo "KEY_NOT_FOUND"
```

**若 `KEY_FOUND`**：密钥已提取，`decrypt_db.py` 不需要 SIP，直接执行：

```bash
cd "$DECRYPT_TOOL" && python3 decrypt_db.py 2>&1
```

成功后记录 `$DECRYPT_TOOL/decrypted/` 路径，跳到步骤 5（询问联系人）。

---

#### Level 3：两者均不存在，需要 SIP 关闭

```bash
csrutil status
```

- 若输出包含 `enabled`：**停止并告知用户**：
  > "需要先关闭 SIP 才能提取微信密钥（仅此一次）。完成后重新运行此命令，之后永久不需要再关闭 SIP。
  >
  > 步骤：关机 → 按住电源键进入恢复模式 → 实用工具 → 终端 → `csrutil disable` → `reboot`"

- 若输出包含 `disabled`：继续步骤 4。

---

### 步骤 4：提取密钥（需要 SIP 关闭，仅此一次）

先用 AskUserQuestion 确认：
> "准备从微信内存提取密钥。请确认：① 微信 Mac 客户端当前处于登录状态 ② 近期在微信里打开过几个对话。确认后继续。"

```bash
LLDB_PYTHON="/Library/Developer/CommandLineTools/Library/PrivateFrameworks/LLDB.framework/Versions/A/Resources/Python"
cd "$DECRYPT_TOOL" && PYTHONPATH="$LLDB_PYTHON" /Library/Developer/CommandLineTools/usr/bin/python3.9 find_key.py 2>&1
# 成功后生成 wechat_keys.json
```

> ⚠️ **此命令必须在系统 Terminal.app 中手动运行，不能通过 Claude Code 执行。**
> lldb 附加进程需要 taskport 权限，Claude Code 的子进程不具备此权限。
>
> **用户操作步骤：**
> 1. 打开 Terminal.app（不是 Claude Code 终端）
> 2. 复制粘贴上方命令执行
> 3. 看到提示后的操作见下方说明

> **注意：此步骤需要用户配合操作**
> 1. 脚本启动后会附加到微信进程，期间微信界面会短暂卡住（约 2-5 分钟，正在扫描内存）
> 2. 微信恢复响应后，**切换到微信，依次点开 3-5 个不同的聊天窗口**，每次点开触发一次密钥捕获
> 3. 终端输出 `[!] Found new key!` 后说明捕获成功
> 4. 按 Ctrl+C 停止脚本，`wechat_keys.json` 自动保存

- 若失败报架构错误：改用 `arch -arm64 /Library/Developer/CommandLineTools/usr/bin/python3.9 find_key.py`
- 若失败报 `ModuleNotFoundError: No module named 'lldb'`：确认使用的是 Python 3.9，`_lldb` 只支持 3.9
- 若失败报 Permission denied：SIP 未关闭，返回 Level 3

**密钥提取成功后立即告知用户：**
> "密钥已提取完成！现在可以重新开启 SIP 了——后续解密和所有分析都不需要 SIP。
>
> 重新开启 SIP：关机 → 恢复模式 → `csrutil enable` → `reboot`
>
> 也可以先不重启，继续完成本次解密后再重启。"

然后执行解密：

```bash
cd "$DECRYPT_TOOL" && python3 decrypt_db.py 2>&1
# 成功后在 $DECRYPT_TOOL/decrypted/ 生成 .db 文件
```

成功后记录 `$DECRYPT_TOOL/decrypted/` 路径，继续步骤 5。

---

### 步骤 5：确认用户想分析谁

环境已就绪。如果调用时未说明联系人，使用 AskUserQuestion 询问：
> "你想分析和谁的聊天记录？（输入对方的备注名或微信昵称）"

---

### 步骤 6：写入配置（自动）

根据步骤 3 或步骤 4 找到的数据库路径，写入配置：

```bash
DB_DIR="<步骤3或4找到的路径>"
cat > "$TOOL_DIR/config.json" << EOF
{
  "decrypted_db_dir": "$DB_DIR",
  "output_dir": "$TOOL_DIR/wechat_analysis_output"
}
EOF
echo "配置已写入：$TOOL_DIR/config.json"
```

---

### 步骤 7：查找联系人并导出消息（自动）

```bash
cd "$TOOL_DIR" && "$VENV/bin/python" export_contact.py --contact "<步骤5确认的联系人名>" 2>&1
```

- 若出现多个匹配结果：展示给用户，用 AskUserQuestion 让用户选择编号
- 从输出中提取 `EXPORT_PATH:` 后的路径作为 `$CSV_PATH`
- 若报"未找到联系人"：运行 `"$VENV/bin/python" export_contact.py --list-contacts` 展示列表，让用户重新确认名称

---

### 步骤 8a：生成图表与分析输入（自动，无需 API Key）

```bash
cd "$TOOL_DIR" && "$VENV/bin/python" main.py "$CSV_PATH" 2>&1
```

此命令会生成：
- 所有可视化图表（`charts/` 目录）
- `wechat_analysis_output/personality_input.json`（你的消息，供下一步分析）
- `wechat_analysis_output/partner_input.json`（对方的消息，供下一步分析）

---

### 步骤 8b：Claude 直接进行人格分析（无需外部 API）

**同时**使用 Read 工具读取两个分析输入文件：

```
读取文件：$TOOL_DIR/wechat_analysis_output/personality_input.json
读取文件：$TOOL_DIR/wechat_analysis_output/partner_input.json
```

对两个文件的 `sample_messages` 均做预处理：**过滤掉超过 150 字的消息**，保留剩余消息。然后**作为语言学人格研究者**，分别对两份数据独立分析：
- 过滤后的 `sample_messages`：日常对话样本
- `top_words`：词频 Top 30
- `features`：量化语言特征
- `stats_summary`：基础统计

**分析要求：**
- evidence 必须引用对应 `sample_messages` 中真实出现的原文
- MBTI 仅供参考，需在 note 中说明不确定性
- Big Five 是分析重点

两份结果均使用相同 JSON 格式，**分别使用 Write 工具写入两个文件**：

```
写入文件：$TOOL_DIR/wechat_analysis_output/personality_result.json   （你的分析）
写入文件：$TOOL_DIR/wechat_analysis_output/partner_result.json        （对方的分析）
```

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
    "note": "置信度说明",
    "dims": {
      "EI": {"lean": "E或I", "strength": "明显/轻微", "reason": "简短理由"},
      "SN": {"lean": "S或N", "strength": "明显/轻微", "reason": "简短理由"},
      "TF": {"lean": "T或F", "strength": "明显/轻微", "reason": "简短理由"},
      "JP": {"lean": "J或P", "strength": "明显/轻微", "reason": "简短理由"}
    }
  },
  "style": {
    "one_line": "一句生动描述",
    "summary": "2-3句聊天风格描述",
    "strengths": ["特点1", "特点2", "特点3"],
    "fun_facts": ["有趣发现1", "有趣发现2"]
  },
  "reliability": "用一句话客观说明本次分析的数据基础，格式：「本次分析基于约X天、Y条消息中采样的Z条对话。[如实描述实际观察到的样本特征，例如消息长度、话题多样性、时间分布等]。人格判断以语言习惯和行为模式为主，受数据量和话题覆盖范围影响，仅作参考。」注意：只描述数据中实际观察到的事实，不要添加主观推测或未在数据中体现的场景描述。"
}
```

> 若 `partner_input.json` 不存在（对方消息为空），则跳过对方分析，只写 `personality_result.json`。

---

### 步骤 8c：生成完整对比报告（自动）

从步骤 5 取到的联系人名作为 `--partner-name`：

```bash
cd "$TOOL_DIR" && "$VENV/bin/python" main.py "$CSV_PATH" \
  --personality-result wechat_analysis_output/personality_result.json \
  --partner-personality-result wechat_analysis_output/partner_result.json \
  --partner-name "<步骤5确认的联系人名>" 2>&1
```

若无对方分析结果，则省略 `--partner-personality-result` 参数。

---

### 步骤 9：打开报告

```bash
open "$TOOL_DIR/wechat_analysis_output/report.html"
```

告知用户：
- 报告已在浏览器打开
- 图表图片在 `wechat_analysis_output/charts/`（可直接截图用于发布）
- 如需清理导出的消息文件：`rm "$TOOL_DIR"/export_*.csv`

然后检查 SIP 状态，若仍为关闭状态，提示用户重新开启：

```bash
csrutil status
```

若输出包含 `disabled`，告知用户：
> "安全提醒：数据库解密已完成，建议现在重新开启 SIP 以恢复系统保护。
>
> 步骤：关机 → 按住电源键进入恢复模式 → 终端执行 csrutil enable → reboot
>
> 重新开启 SIP 不影响已解密的数据库文件，下次分析无需再次解密。"

---

## 错误速查

| 错误 | 自动处理 | 需用户操作 |
|------|---------|-----------|
| ModuleNotFoundError | 自动 pip install | — |
| 解密工具未安装 | 自动 git clone | — |
| SIP 已启用 | 停止并提示 | 按安装指南第 1 步关闭 SIP |
| 微信未登录 | 提示确认后重试 | 打开微信并登录 |
| 联系人未找到 | 展示联系人列表 | 确认正确的联系人名称 |
| personality_input.json 不存在 | 重新运行步骤 8a | — |
| 数据库路径不存在 | 重新搜索路径 | 若仍失败则重新执行解密 |
