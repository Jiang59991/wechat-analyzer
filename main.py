#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🍪 微信聊天记录人格分析工具 — 姜饼探AI

两步工作流（无需外部 API Key）：
  步骤一：生成图表 + 分析输入文件（自己 + 对方）
    python main.py <CSV路径>

  步骤二：读取 Claude 分析结果，生成完整对比报告
    python main.py <CSV路径> --personality-result personality_result.json \
                             --partner-personality-result partner_result.json \
                             --partner-name <联系人名>

选项：
  --output DIR                        输出目录（默认 ./wechat_analysis_output）
  --sample-size N                     供 Claude 分析的采样消息数上限（默认 100）
  --personality-result FILE           自己的人格分析结果 JSON
  --partner-personality-result FILE   对方的人格分析结果 JSON
  --partner-name NAME                 对方的名字（默认"对方"）
"""

import argparse
import base64
import json
import os
import sys
from typing import Optional

import data_loader
from data_loader import _replace_wechat_emoji
import report as report_mod
import sampler
import stats as stats_mod
import visualizer
from personality import extract_features


def _fix_emoji(obj):
    """递归替换 JSON 对象中所有字符串里的微信表情占位符"""
    if isinstance(obj, str):
        return _replace_wechat_emoji(obj)
    if isinstance(obj, dict):
        return {k: _fix_emoji(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fix_emoji(v) for v in obj]
    return obj


def _load_meta(csv_path: str) -> dict:
    """尝试读取 export 脚本写出的 meta sidecar JSON"""
    meta_path = csv_path.replace('.csv', '.meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _avatar_b64(path: Optional[str]) -> Optional[str]:
    """读取头像文件并转为 base64 data URI，失败返回 None"""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as f:
            data = f.read()
        if data[:4] == b'\x89PNG':
            mime = 'image/png'
        elif data[:3] == b'\xff\xd8\xff':
            mime = 'image/jpeg'
        elif data[:4] == b'GIF8':
            mime = 'image/gif'
        else:
            mime = 'image/jpeg'
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description='微信聊天记录人格分析工具 · 姜饼探AI')
    parser.add_argument('csv_file', help='CSV 文件路径')
    parser.add_argument('--output', default='./wechat_analysis_output')
    parser.add_argument('--sample-size', type=int, default=100,
                        help='供 Claude 分析的采样消息数上限（默认 100）')
    parser.add_argument('--personality-result', default=None,
                        help='自己的人格分析结果 JSON 文件')
    parser.add_argument('--partner-personality-result', default=None,
                        help='对方的人格分析结果 JSON 文件')
    parser.add_argument('--self-name', default=None,
                        help='自己的名字（默认从 meta JSON 读取，否则"我"）')
    parser.add_argument('--partner-name', default=None,
                        help='对方的名字（默认从 meta JSON 读取，否则"对方"）')
    args = parser.parse_args()

    if not os.path.exists(args.csv_file):
        print(f'❌ 文件不存在：{args.csv_file}')
        sys.exit(1)

    output_dir = args.output
    charts_dir = os.path.join(output_dir, 'charts')
    os.makedirs(charts_dir, exist_ok=True)

    font = visualizer.setup_font()
    if font:
        print(f'🖋  使用字体：{font}')

    # ── 读取 meta sidecar（昵称 + 头像），CLI 参数可覆盖 ────────────────────
    meta = _load_meta(args.csv_file)
    self_name    = args.self_name    or meta.get('self_name', '我')
    partner_name = args.partner_name or meta.get('partner_name', '对方')
    self_avatar_data    = _avatar_b64(meta.get('self_avatar_path'))
    partner_avatar_data = _avatar_b64(meta.get('partner_avatar_path'))

    # ── Step 1: 加载数据（自己 + 对方） ─────────────────────────────────────
    print('\n📂 正在加载数据...')
    try:
        df = data_loader.load(args.csv_file, sender=1)
    except ValueError as e:
        print(f'❌ 数据加载失败：{e}')
        sys.exit(1)

    print(f'   自己：{len(df):,} 条文本消息')
    if len(df) < 50:
        print('⚠️  自己消息数量较少，分析结果可靠性有限。')

    try:
        df_partner = data_loader.load(args.csv_file, sender=0)
        print(f'   对方：{len(df_partner):,} 条文本消息')
    except Exception:
        df_partner = None
        print('   ⚠️  无法加载对方消息')

    # ── Step 2: 统计分析 ────────────────────────────────────────────────────
    print('\n📊 正在计算统计数据...')
    stats = stats_mod.compute(df)
    dr = stats['date_range']
    print(f'   时间跨度：{dr[0].strftime("%Y-%m-%d")} → {dr[1].strftime("%Y-%m-%d")}')
    print(f'   平均消息长度：{stats["avg_length"]} 字')
    print(f'   最活跃时段：{stats["hourly"].idxmax()}:00')

    partner_stats = stats_mod.compute(df_partner) if df_partner is not None and len(df_partner) > 0 else None

    # ── Step 3: 生成可视化图表 ──────────────────────────────────────────────
    print('\n🎨 正在生成可视化图表...')
    charts = {
        'hourly':        visualizer.hourly(stats),
        'monthly_trend': visualizer.monthly_trend(stats),
        'weekday_bar':   visualizer.weekday_bar(stats),
        'length_dist':   visualizer.length_dist(stats),
    }
    # 词云：有对方数据用双人词云，否则用单人
    if partner_stats is not None:
        charts['word_cloud_pair'] = visualizer.word_cloud_pair(
            stats, partner_stats, self_name, partner_name
        )
    else:
        charts['word_cloud'] = visualizer.word_cloud(stats)
    visualizer.save_all(charts, charts_dir)

    # ── Step 4: 读取人格分析结果 OR 导出分析输入 ──────────────────────────
    personality_result: dict = {}
    partner_personality: dict = {}

    if args.personality_result:
        # 模式B：读取 Claude 写入的结果，生成完整报告
        if not os.path.exists(args.personality_result):
            print(f'❌ 找不到人格分析结果文件：{args.personality_result}')
            sys.exit(1)
        with open(args.personality_result, encoding='utf-8') as f:
            personality_result = _fix_emoji(json.load(f))
        print(f'\n🧠 已读取自己的人格分析结果：{args.personality_result}')

        if args.partner_personality_result:
            if not os.path.exists(args.partner_personality_result):
                print(f'⚠️  找不到对方人格分析结果文件：{args.partner_personality_result}，将跳过对比')
            else:
                with open(args.partner_personality_result, encoding='utf-8') as f:
                    partner_personality = _fix_emoji(json.load(f))
                print(f'🧠 已读取对方（{partner_name}）的人格分析结果')

        big5 = personality_result.get('big5', {})
        if big5:
            scores = {k: v.get('score', 50) for k, v in big5.items()}
            radar = visualizer.big5_radar(scores)
            visualizer.save_all({'radar': radar}, charts_dir)

    else:
        # 模式A（默认）：采样消息，导出 personality_input.json 供 Claude 分析
        print('\n🧠 正在采样消息，准备人格分析输入...')
        clean_df = data_loader.filter_for_personality(df)
        messages = sampler.smart_sample(clean_df, target_n=args.sample_size)
        features = extract_features(messages)
        top_words = sorted(stats['word_freq'].items(), key=lambda x: x[1], reverse=True)[:30]

        ai_input = {
            'sample_messages': messages,
            'top_words': [{'word': w, 'count': c} for w, c in top_words],
            'features': features,
            'stats_summary': {
                'date_range': [dr[0].strftime('%Y-%m-%d'), dr[1].strftime('%Y-%m-%d')],
                'total_messages': stats['total_messages'],
                'avg_length': stats['avg_length'],
                'most_active_hour': int(stats['hourly'].idxmax()),
            },
        }
        input_path = os.path.join(output_dir, 'personality_input.json')
        with open(input_path, 'w', encoding='utf-8') as f:
            json.dump(ai_input, f, ensure_ascii=False, indent=2)
        print(f'   自己：已采样 {len(messages)} 条消息 → {input_path}')

        # 生成对方的分析输入
        if df_partner is not None and len(df_partner) > 0 and partner_stats is not None:
            clean_partner = data_loader.filter_for_personality(df_partner)
            if len(clean_partner) > 0:
                partner_messages = sampler.smart_sample(clean_partner, target_n=args.sample_size)
                partner_features = extract_features(partner_messages)
                partner_top_words = sorted(
                    partner_stats['word_freq'].items(), key=lambda x: x[1], reverse=True
                )[:30]
                partner_dr = partner_stats['date_range']
                partner_ai_input = {
                    'sample_messages': partner_messages,
                    'top_words': [{'word': w, 'count': c} for w, c in partner_top_words],
                    'features': partner_features,
                    'stats_summary': {
                        'date_range': [partner_dr[0].strftime('%Y-%m-%d'), partner_dr[1].strftime('%Y-%m-%d')],
                        'total_messages': partner_stats['total_messages'],
                        'avg_length': partner_stats['avg_length'],
                        'most_active_hour': int(partner_stats['hourly'].idxmax()),
                    },
                }
                partner_path = os.path.join(output_dir, 'partner_input.json')
                with open(partner_path, 'w', encoding='utf-8') as f:
                    json.dump(partner_ai_input, f, ensure_ascii=False, indent=2)
                print(f'   对方：已采样 {len(partner_messages)} 条消息 → {partner_path}')
            else:
                print('   ⚠️  对方消息过滤后为空，跳过对方分析输入生成')
        else:
            print('   ⚠️  对方消息不足，跳过对方分析输入生成')

        print(f'   → Claude skill 将读取上述文件进行人格分析')

    # ── Step 5: 生成报告 ────────────────────────────────────────────────────
    print('\n📝 正在生成 HTML 报告...')
    has_pair_wordcloud = partner_stats is not None
    report_path = report_mod.generate(
        stats, personality_result, output_dir,
        partner_stats=partner_stats,
        partner_personality=partner_personality,
        self_name=self_name,
        partner_name=partner_name,
        self_avatar_data=self_avatar_data,
        partner_avatar_data=partner_avatar_data,
        has_pair_wordcloud=has_pair_wordcloud,
    )

    json_path = os.path.join(output_dir, 'personality_raw.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(personality_result, f, ensure_ascii=False, indent=2)

    has_partner = bool(partner_personality)
    print(f'''
🍪 {"完整对比报告已生成" if has_partner else ("完整报告已生成" if args.personality_result else "图表已生成，等待人格分析")}！
─────────────────────────────────
  HTML 报告：{report_path}
  图表目录： {charts_dir}
─────────────────────────────────
在浏览器中查看：
  open "{report_path}"
''')


if __name__ == '__main__':
    main()
