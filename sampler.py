"""
sampler.py — 智能分层采样，为人格分析选出最具代表性的消息

核心策略（三步）：
  1. 硬过滤：去除噪音（由 data_loader.filter_for_personality 完成）
  2. 内容打分：优先选含观点/情绪/规划的消息
  3. 分层时序采样：按月均匀取样，保证覆盖整个时间跨度

参考依据：
  - IBM Watson Personality Insights 建议最少 3500 词
  - 本工具目标采样 ~350 条消息，平均每条 20 字 ≈ 7000 字，满足阈值
"""

import math
import random
from typing import List

import pandas as pd

# 高价值消息的标志词
_OPINION_WORDS  = ['我觉得', '我认为', '感觉', '我想', '我希望', '依我看', '在我看来', '我以为']
_EMOTION_WORDS  = ['开心', '高兴', '难过', '伤心', '生气', '烦', '焦虑', '担心',
                   '害怕', '失望', '幸福', '满足', '兴奋', '郁闷', '委屈', '无聊']
_PLANNING_WORDS = ['打算', '计划', '准备', '决定', '目标', '将来', '以后', '未来', '想要']


def _score(text: str) -> int:
    """对单条消息打分（0-10），分越高越优先被采样"""
    score = 0
    score += min(len(text) // 20, 4)                          # 长度分（最多4分）
    score += 3 if any(w in text for w in _OPINION_WORDS) else 0   # 含观点词+3
    score += 2 if any(w in text for w in _EMOTION_WORDS) else 0   # 含情绪词+2
    score += 1 if any(w in text for w in _PLANNING_WORDS) else 0  # 含规划词+1
    score += 1 if ('?' in text or '？' in text) else 0            # 含问句+1
    return score


def smart_sample(df: pd.DataFrame, target_n: int = 350) -> List[str]:
    """
    分层时序采样：
      - 按自然月分组
      - 每月内按内容分数降序，取 quota 条
      - 全局打乱，消除顺序偏差
    返回消息文本列表。
    """
    if len(df) == 0:
        return []

    df = df.copy()
    df['_score'] = df['content'].apply(_score)

    months = sorted(df['month'].unique())
    n_months = len(months)
    per_month = max(5, math.ceil(target_n / n_months))

    sampled: List[str] = []
    for month in months:
        bucket = df[df['month'] == month].sort_values('_score', ascending=False)
        sampled.extend(bucket['content'].head(per_month).tolist())

    # 如果仍然超量，全局按分数截断（极端情况）
    if len(sampled) > int(target_n * 1.4):
        all_sorted = df.sort_values('_score', ascending=False)
        sampled = all_sorted['content'].head(target_n).tolist()

    random.shuffle(sampled)
    return sampled
