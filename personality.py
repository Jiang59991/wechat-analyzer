"""
personality.py — 调用 Claude API 进行两阶段人格分析

阶段一：程序化提取语言特征（客观指标）
阶段二：将采样消息 + 特征一起发给 Claude，输出结构化 JSON
"""

import json
import re
from typing import List

import pandas as pd
from anthropic import Anthropic

# ── 阶段一：语言特征提取 ──────────────────────────────────────────────────────

_OPINION_WORDS  = ['我觉得', '我认为', '感觉', '我想', '我希望', '在我看来', '我以为']
_EMOTION_POS    = ['开心', '高兴', '快乐', '喜欢', '爱', '棒', '不错', '满意', '幸福', '兴奋']
_EMOTION_NEG    = ['难过', '伤心', '生气', '烦', '焦虑', '担心', '害怕', '失望', '委屈', '无聊']
_PLANNING_WORDS = ['打算', '计划', '准备', '决定', '目标', '将来', '以后', '未来']
_CERTAINTY_POS  = ['一定', '肯定', '确定', '绝对', '必须']
_CERTAINTY_NEG  = ['可能', '也许', '大概', '应该', '或许', '不确定']
_FIRST_PERSON   = ['我', '我的', '我觉得', '我认为', '我想']
_SOCIAL_WORDS   = ['朋友', '大家', '我们', '一起', '聚', '出去', '玩']


def _rate(texts: List[str], words: List[str]) -> float:
    """words 中任意词出现在消息里的比例"""
    hits = sum(1 for t in texts if any(w in t for w in words))
    return round(hits / len(texts) * 100, 1) if texts else 0.0


def extract_features(messages: List[str]) -> dict:
    """从消息列表中提取可量化的语言特征"""
    if not messages:
        return {}
    avg_len = round(sum(len(m) for m in messages) / len(messages), 1)
    return {
        'avg_length':       avg_len,
        'opinion_rate':     _rate(messages, _OPINION_WORDS),
        'positive_emotion': _rate(messages, _EMOTION_POS),
        'negative_emotion': _rate(messages, _EMOTION_NEG),
        'planning_rate':    _rate(messages, _PLANNING_WORDS),
        'certainty_high':   _rate(messages, _CERTAINTY_POS),
        'certainty_low':    _rate(messages, _CERTAINTY_NEG),
        'question_rate':    round(sum(1 for m in messages if '?' in m or '？' in m) / len(messages) * 100, 1),
        'social_rate':      _rate(messages, _SOCIAL_WORDS),
        'first_person_rate':_rate(messages, _FIRST_PERSON),
        'sample_count':     len(messages),
        'total_words':      sum(len(m) for m in messages),
    }


# ── 阶段二：Claude 人格分析 ───────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
你是一位语言学人格研究者，正在分析一位用户的微信聊天记录样本。

【数据概况】
- 样本消息数：{n} 条（已过滤噪音，按时间均匀采样）
- 覆盖时间跨度：约 {months} 个月
- 语言特征摘要：{features_str}

【消息样本】
---
{messages_text}
---

【分析要求】
请基于语言模式推断人格特质，输出严格符合以下格式的 JSON：

```json
{{
  "big5": {{
    "openness":          {{"score": 0-100, "level": "低/中/高", "evidence": "引用1条原文", "note": "一句解读"}},
    "conscientiousness": {{"score": 0-100, "level": "低/中/高", "evidence": "引用1条原文", "note": "一句解读"}},
    "extraversion":      {{"score": 0-100, "level": "低/中/高", "evidence": "引用1条原文", "note": "一句解读"}},
    "agreeableness":     {{"score": 0-100, "level": "低/中/高", "evidence": "引用1条原文", "note": "一句解读"}},
    "neuroticism":       {{"score": 0-100, "level": "低/中/高", "evidence": "引用1条原文", "note": "一句解读"}}
  }},
  "mbti": {{
    "type":       "四字母类型",
    "confidence": "低/中/高",
    "note":       "一句话说明置信度原因",
    "dims": {{
      "EI": {{"lean": "E或I", "strength": "明显/轻微", "reason": "简短理由"}},
      "SN": {{"lean": "S或N", "strength": "明显/轻微", "reason": "简短理由"}},
      "TF": {{"lean": "T或F", "strength": "明显/轻微", "reason": "简短理由"}},
      "JP": {{"lean": "J或P", "strength": "明显/轻微", "reason": "简短理由"}}
    }}
  }},
  "style": {{
    "one_line":    "用一句话描述这个人，要生动、有画面感",
    "summary":     "2-3句话描述聊天风格",
    "strengths":   ["特点1", "特点2", "特点3"],
    "fun_facts":   ["有趣发现1", "有趣发现2"]
  }},
  "reliability": "关于本次分析可靠性的简短说明（样本量、语言偏差等）"
}}
```

重要提醒：
- MBTI 在学术上信效度有限，请在 confidence 和 note 中如实体现不确定性
- Big Five 具有更强研究支撑，是本分析的重点
- evidence 必须是消息样本中真实出现的原文片段，不要编造
"""


def analyze(messages: List[str], date_range: tuple) -> dict:
    """
    调用 Claude 进行完整人格分析。
    返回结构化 dict，若 JSON 解析失败则返回 {'raw': ..., 'parse_error': True}。
    """
    client = Anthropic()

    months = max(1, (date_range[1] - date_range[0]).days // 30)
    features = extract_features(messages)
    features_str = ', '.join(f'{k}={v}' for k, v in features.items())
    messages_text = '\n'.join(f'• {m}' for m in messages)

    prompt = _PROMPT_TEMPLATE.format(
        n=len(messages),
        months=months,
        features_str=features_str,
        messages_text=messages_text,
    )

    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=2500,
        messages=[{'role': 'user', 'content': prompt}],
    )
    raw = resp.content[0].text

    # 提取 JSON 块
    m = re.search(r'```json\s*([\s\S]+?)\s*```', raw)
    json_str = m.group(1) if m else raw
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return {'raw': raw, 'parse_error': True}
