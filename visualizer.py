"""
visualizer.py — 生成所有可视化图表（姜饼棕白风格）
"""

import os
from collections import Counter
from typing import Optional

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from wordcloud import WordCloud

# ── 品牌色 ────────────────────────────────────────────────────────────────────
BROWN_DARK   = '#8B5E3C'
BROWN_MID    = '#C68642'
BROWN_LIGHT  = '#D4956A'
BROWN_PALE   = '#E8C49A'
CREAM        = '#FFF8F0'
CHART_BG     = '#FDFAF6'
TEXT_DARK    = '#3A2A1A'
TEXT_MID     = '#7A6655'
TEAL_DARK    = '#4A7B6F'
TEAL_MID     = '#6FAA9C'

# 词云字体文件路径（需要文件路径，不能只用字体名称）
_WC_FONT_PATH: Optional[str] = None

# 候选字体文件路径
_FONT_FILE_CANDIDATES = [
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simhei.ttf',
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
]


# ── 字体检测 ──────────────────────────────────────────────────────────────────
def setup_font() -> Optional[str]:
    global _WC_FONT_PATH
    candidates = [
        'PingFang SC', 'Heiti SC', 'STHeiti', 'STSong',
        'Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC',
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams['font.family'] = [font, 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            # 同时设置词云用的字体文件路径
            for p in _FONT_FILE_CANDIDATES:
                if os.path.exists(p):
                    _WC_FONT_PATH = p
                    break
            return font
    print("⚠️  未找到中文字体，图表汉字可能显示为方块。")
    return None


def _style(ax, title='', xlabel='', ylabel=''):
    ax.set_facecolor(CHART_BG)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    ax.spines['left'].set_color(BROWN_PALE)
    ax.spines['bottom'].set_color(BROWN_PALE)
    if title:
        ax.set_title(title, fontsize=13, fontweight='bold', color=TEXT_DARK, pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, color=TEXT_MID, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=TEXT_MID, fontsize=10)
    ax.tick_params(colors=TEXT_MID)


# ── 各图表 ────────────────────────────────────────────────────────────────────

def hourly(stats: dict) -> plt.Figure:
    """每小时消息分布"""
    fig, ax = plt.subplots(figsize=(11, 4), facecolor=CHART_BG)
    h = stats['hourly']
    colors = [BROWN_MID if i == h.idxmax() else BROWN_DARK for i in range(24)]
    ax.bar(h.index, h.values, color=colors, width=0.75, alpha=0.88)

    # 深夜/清晨阴影
    for span in [(0, 6), (22, 24)]:
        ax.axvspan(*span, alpha=0.06, color='navy', lw=0)

    peak = h.idxmax()
    ax.annotate(
        f'最活跃：{peak}:00',
        xy=(peak, h[peak]),
        xytext=(min(peak + 2, 21), h[peak] * 0.82),
        arrowprops=dict(arrowstyle='->', color=BROWN_MID, lw=1.5),
        color=BROWN_MID, fontsize=9,
    )
    _style(ax, title='你几点最爱发消息？', xlabel='时间', ylabel='消息数')
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f'{h}:00' for h in range(0, 24, 2)], rotation=45, fontsize=8)
    plt.tight_layout()
    return fig


def monthly_trend(stats: dict) -> plt.Figure:
    """月度消息趋势"""
    fig, ax = plt.subplots(figsize=(13, 4), facecolor=CHART_BG)
    m = stats['monthly']
    x = range(len(m))

    ax.fill_between(x, m.values, alpha=0.18, color=BROWN_DARK)
    ax.plot(x, m.values, color=BROWN_DARK, linewidth=2.2, marker='o', markersize=3.5)

    peak_idx = int(np.argmax(m.values))
    ax.annotate(
        f'峰值 {m.values[peak_idx]} 条',
        xy=(peak_idx, m.values[peak_idx]),
        xytext=(max(peak_idx - 3, 0), m.values[peak_idx] * 0.82),
        arrowprops=dict(arrowstyle='->', color=BROWN_MID, lw=1.5),
        color=BROWN_MID, fontsize=9,
    )
    _style(ax, title='每月消息量变化', ylabel='消息数')
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(p) for p in m.index], rotation=45, fontsize=7)
    plt.tight_layout()
    return fig


def weekday_bar(stats: dict) -> plt.Figure:
    """一周各天消息分布"""
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=CHART_BG)
    wd = stats['weekday']
    day_labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    colors = [BROWN_MID if i >= 5 else BROWN_DARK for i in range(7)]
    ax.bar(range(7), wd.values, color=colors, alpha=0.88)
    _style(ax, title='你哪天最爱聊天？', ylabel='消息数')
    ax.set_xticks(range(7))
    ax.set_xticklabels(day_labels)
    patches = [
        mpatches.Patch(color=BROWN_DARK, alpha=0.88, label='工作日'),
        mpatches.Patch(color=BROWN_MID, alpha=0.88, label='周末'),
    ]
    ax.legend(handles=patches, fontsize=9)
    plt.tight_layout()
    return fig


def _make_wordcloud(word_freq: Counter, colormap: str = 'YlOrBr',
                    width: int = 800, height: int = 420) -> 'WordCloud':
    """内部：生成 WordCloud 对象"""
    from wordcloud import WordCloud as WC
    kwargs: dict = dict(
        background_color=CREAM,
        max_words=70,
        width=width, height=height,
        colormap=colormap,
        collocations=False,
    )
    if _WC_FONT_PATH:
        kwargs['font_path'] = _WC_FONT_PATH
    return WC(**kwargs).generate_from_frequencies(dict(word_freq.most_common(100)))


def word_cloud(stats: dict) -> plt.Figure:
    """单人中文词云（兼容旧接口）"""
    wf: Counter = stats['word_freq']
    if not wf:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, '词频数据不足', ha='center', va='center', fontsize=14)
        ax.axis('off')
        return fig

    wc = _make_wordcloud(wf)
    fig, ax = plt.subplots(figsize=(11, 5.5), facecolor=CREAM)
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    ax.set_title('你嘴里最常出现的词', fontsize=13, fontweight='bold', color=TEXT_DARK, pad=10)
    fig.patch.set_facecolor(CREAM)
    plt.tight_layout()
    return fig


def word_cloud_pair(stats_self: dict, stats_partner: dict,
                    self_name: str = '你', partner_name: str = '对方') -> plt.Figure:
    """双人词云：左右并排，棕色（自己）vs 青绿色（对方）"""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), facecolor=CREAM)
    fig.patch.set_facecolor(CREAM)

    pairs = [
        (axes[0], stats_self,   self_name,    'YlOrBr'),
        (axes[1], stats_partner, partner_name, 'GnBu_r'),
    ]
    for ax, stats, name, cmap in pairs:
        wf = stats.get('word_freq', Counter())
        if not wf:
            ax.text(0.5, 0.5, '词频数据不足', ha='center', va='center',
                    fontsize=12, color=TEXT_MID, transform=ax.transAxes)
            ax.axis('off')
        else:
            wc = _make_wordcloud(wf, colormap=cmap)
            ax.imshow(wc, interpolation='bilinear')
            ax.axis('off')
        ax.set_title(f'{name} 的高频词', fontsize=12, fontweight='bold',
                     color=TEXT_DARK, pad=8)

    plt.tight_layout(pad=1.5)
    return fig


def length_dist(stats: dict) -> plt.Figure:
    """消息长度分布直方图"""
    fig, ax = plt.subplots(figsize=(9, 4), facecolor=CHART_BG)
    lengths = stats['length_series'].clip(upper=200)
    ax.hist(lengths, bins=40, color=BROWN_DARK, alpha=0.82, edgecolor='white', linewidth=0.4)
    mean_len = lengths.mean()
    ax.axvline(mean_len, color=BROWN_MID, linestyle='--', linewidth=2,
               label=f'平均 {mean_len:.0f} 字')
    _style(ax, title='你的消息习惯有多长？', xlabel='字数', ylabel='条数')
    ax.legend(fontsize=9)
    plt.tight_layout()
    return fig


def big5_radar(scores: dict) -> plt.Figure:
    """大五人格雷达图"""
    labels = ['开放性\nOpenness', '尽责性\nConscientiousness',
              '外倾性\nExtraversion', '宜人性\nAgreeableness', '神经质\nNeuroticism']
    keys   = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
    vals   = [scores.get(k, 50) / 100 for k in keys]

    N      = len(labels)
    angles = [n / N * 2 * np.pi for n in range(N)] + [0]
    vals   = vals + vals[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True), facecolor=CHART_BG)
    ax.set_facecolor(CHART_BG)
    ax.fill(angles, vals, alpha=0.28, color=BROWN_DARK)
    ax.plot(angles, vals, color=BROWN_DARK, linewidth=2.2)
    ax.scatter(angles[:-1], vals[:-1], s=55, color=BROWN_MID, zorder=5)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=9, color=TEXT_DARK)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8])
    ax.set_yticklabels(['20', '40', '60', '80'], size=7, color=TEXT_MID)
    ax.set_ylim(0, 1)
    ax.grid(color=BROWN_PALE, linestyle='--', alpha=0.5)
    ax.set_title('大五人格 · 雷达图', fontsize=13, fontweight='bold', color=TEXT_DARK, pad=22)
    plt.tight_layout()
    return fig


def save_all(charts: dict, charts_dir: str, dpi: int = 150):
    """把所有图表保存为 PNG"""
    os.makedirs(charts_dir, exist_ok=True)
    for name, fig in charts.items():
        path = os.path.join(charts_dir, f'{name}.png')
        fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=CHART_BG)
        plt.close(fig)
        print(f'   ✓ {name}.png')
