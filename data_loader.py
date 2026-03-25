"""
data_loader.py — 加载和清洗 WeChatMsg 导出的 CSV 数据
"""

import re
import pandas as pd

# 低信号消息的正则过滤（单字/语气词/纯emoji占位符）
_NOISE_RE = re.compile(
    r'^(好|嗯+|哦|哈+|ok|OK|好的|收到|嗯嗯+|好哒|好滴|是的|对|呢|吧|啊|哎|\[.*?\])$',
    re.IGNORECASE
)
_FORWARDED_RE = re.compile(r'^[-─]+\s*转发的聊天记录\s*[-─]+')
_EMOJI_ONLY_RE = re.compile(
    r'^[\U0001F300-\U0001FFFF\U00002600-\U000027BF\s]+$'
)
# 非对话内容：XML/小程序、链接、百度网盘/京东等分享、结构化文档
_XML_RE      = re.compile(r'^\s*<')                          # XML / 小程序卡片
_URL_RE      = re.compile(r'https?://')                      # 含链接
_MULTILINE_RE = re.compile(r'\n.*\n')                        # 含两个以上换行（结构化文档）
_SHARE_RE    = re.compile(                                    # 常见分享前缀
    r'^(【|通过网盘分享|【京东】|【淘宝】|【拼多多】'
    r'|【Tencent Docs】|链接:|提取码:)'
)

# WeChatMsg 不同版本可能有不同列名，做统一映射
_COL_MAP = {
    'StrContent': 'content',  'strContent': 'content',
    'IsSender':   'is_sender','isSender':   'is_sender',
    'CreateTime': 'ts',       'createTime': 'ts',
    'timestamp':  'ts',
    'Type':       'msg_type', 'type':       'msg_type',
    'StrTalker':  'talker',   'strTalker':  'talker',
}


def load(csv_path: str, sender: int = 1) -> pd.DataFrame:
    """
    加载 CSV，标准化列名，解析时间，过滤出指定发送方的文本消息。
    sender=1 为自己，sender=0 为对方。
    返回已清洗的 DataFrame，包含列：
      content, datetime, date, hour, month, weekday
    """
    df = pd.read_csv(csv_path)
    df = df.rename(columns=_COL_MAP)

    for col in ('content', 'is_sender', 'ts'):
        if col not in df.columns:
            raise ValueError(
                f"CSV 中缺少列 '{col}'，请确认使用 WeChatMsg 导出格式。\n"
                f"当前列名：{list(df.columns)}"
            )

    # 只保留文本消息 (type==1)，按 sender 过滤
    if 'msg_type' in df.columns:
        df = df[df['msg_type'] == 1]
    df = df[df['is_sender'] == sender].copy()

    df['content'] = df['content'].fillna('').astype(str)
    df = df[df['content'].str.len() > 0]

    # 时间解析（Unix 秒）
    df['datetime'] = pd.to_datetime(df['ts'], unit='s', errors='coerce')
    df = df.dropna(subset=['datetime'])

    df['date']    = df['datetime'].dt.date
    df['hour']    = df['datetime'].dt.hour
    df['month']   = df['datetime'].dt.to_period('M')
    df['weekday'] = df['datetime'].dt.dayofweek  # 0=周一

    return df.reset_index(drop=True)


def filter_for_personality(df: pd.DataFrame) -> pd.DataFrame:
    """
    去除低信号消息，保留有人格分析价值的内容。
    规则：
      - 长度 12-150 字符（过短无信息量，过长通常是转发文档）
      - 非纯噪音（语气词、"好的"等）
      - 非转发聊天记录
      - 非纯 emoji
      - 非 XML / 小程序卡片
      - 不含 URL（链接分享）
      - 非结构化多行文档（含两个以上换行）
      - 非常见分享前缀（网盘/电商/文档链接）
    """
    c = df['content']
    mask = (
        (c.str.len() >= 12) &
        (c.str.len() <= 150) &
        (~c.str.strip().apply(lambda x: bool(_NOISE_RE.fullmatch(x)))) &
        (~c.apply(lambda x: bool(_FORWARDED_RE.match(x)))) &
        (~c.apply(lambda x: bool(_EMOJI_ONLY_RE.match(x)))) &
        (~c.apply(lambda x: bool(_XML_RE.match(x)))) &
        (~c.apply(lambda x: bool(_URL_RE.search(x)))) &
        (~c.apply(lambda x: bool(_MULTILINE_RE.search(x)))) &
        (~c.apply(lambda x: bool(_SHARE_RE.match(x))))
    )
    return df[mask].reset_index(drop=True)
