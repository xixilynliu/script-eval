"""
Markdown 报告生成器

将 EvalResult 渲染为结构化 Markdown 报告，
报告格式对标「创一AI·剧本医生」短剧商业潜力评估报告。
"""

from datetime import datetime
from typing import Optional

from script_eval import (
    CommercialScore,
    ComplianceScore,
    DimensionScore,
    EvalResult,
    MarketScore,
    NarrativeScore,
    score_to_grade,
)


# ============================================================
# 维度中文名映射
# ============================================================

NARRATIVE_DIM_NAMES = {
    "hook_strength": "钩子强度",
    "excitement_density": "爽点密度",
    "pacing": "节奏与步调",
    "plot_coherence": "情节连贯性",
    "character_appeal": "角色吸引力",
    "dialogue_quality": "对白质量",
    "suspense_effectiveness": "悬念有效性",
}

MARKET_DIM_NAMES = {
    "hit_potential": "爆款契合度",
    "originality": "原创性评分",
    "audience_attraction": "观众吸引力",
    "user_stickiness": "用户粘性",
    "viral_potential": "传播潜力",
    "ip_value": "IP衍生价值",
}


# ============================================================
# 报告生成
# ============================================================

def _render_grade_badge(score: int, grade: str) -> str:
    """渲染评分徽章"""
    return f"**{score}/100（{grade}级）**"


def _render_dimension_detail(dim_name: str, dim: DimensionScore) -> str:
    """渲染单个维度的详细分析"""
    lines = []
    lines.append(f"{_render_grade_badge(dim.score, dim.grade)}")

    # 分析要点
    for i, point in enumerate(dim.analysis, 1):
        lines.append(f"{i}. {point}")

    # 可打磨点
    if dim.improvements:
        lines.append("")
        lines.append("**可打磨点：**")
        for i, imp in enumerate(dim.improvements, 1):
            lines.append(f"{i}. {imp}")

    return "\n".join(lines)


def _render_scene_table(scenes: dict) -> str:
    """渲染场景表"""
    lines = []
    lines.append("| 类型 | 场景 |")
    lines.append("|------|------|")
    day_scenes = "、".join(scenes.get("day", [])) or "无"
    night_scenes = "、".join(scenes.get("night", [])) or "无"
    lines.append(f"| 日 | {day_scenes} |")
    lines.append(f"| 夜 | {night_scenes} |")
    return "\n".join(lines)


def generate_markdown_report(result: EvalResult, product_name: str = "短剧商业潜力评估报告") -> str:
    """
    将评估结果生成 Markdown 格式报告。

    Args:
        result: EvalResult 评估结果
        product_name: 报告产品名称

    Returns:
        Markdown 格式的报告文本
    """
    info = result.basic_info
    lines = []

    # ========== 标题页 ==========
    lines.append(f"# {product_name}")
    lines.append("")
    lines.append("AI智能诊断 | 商业适配度 · 结构风险 · 变现潜力")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    if info.episode_count > 0:
        lines.append(f"本报告所依据的评估素材，仅限于该剧的前{info.episode_count}集剧本内容。")
        lines.append("")
    lines.append("---")
    lines.append("")

    # ========== 剧本基本信息 ==========
    lines.append(f"## 剧本名称：《{info.title}》")
    lines.append("")

    # 制作难度
    prod = result.commercial.production_difficulty
    lines.append(f"### 制作难度：{prod.level}")
    lines.append("")
    if prod.analysis:
        lines.append(f"**难度说明：** {''.join(prod.analysis)}")
        lines.append("")

    # 场景表
    scene_data = prod.scene_table if prod.scene_table.get("day") or prod.scene_table.get("night") else info.scenes
    if scene_data.get("day") or scene_data.get("night"):
        lines.append("### 场景表：")
        lines.append("")
        lines.append(_render_scene_table(scene_data))
        lines.append("")

    lines.append("---")
    lines.append("")

    # ========== I. 总体潜力评分 ==========
    lines.append(f"## I. 总体潜力评分：{result.total_score}/100（{result.total_grade}级）")
    lines.append("")

    # 风险预警
    if result.risk_warnings:
        for w in result.risk_warnings:
            lines.append(f"> **风险预警：** {w}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # ========== II. 执行摘要 ==========
    lines.append("## II. 执行摘要")
    lines.append("")
    lines.append(f"**频类：** {info.genre}")
    lines.append("")
    lines.append(f"**题材：** {'、'.join(info.themes)}")
    lines.append("")
    if info.plot_features:
        lines.append(f"**剧情特点：** {info.plot_features}")
        lines.append("")
    if info.plot_summary:
        lines.append(f"**剧情主线：** {info.plot_summary}")
        lines.append("")
    if result.core_conclusion:
        lines.append(f"**核心结论：** {result.core_conclusion}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ========== III. 详细分析 ==========
    lines.append("## III. 详细分析")
    lines.append("")

    # ---------- A. 叙事与剧本基因 ----------
    lines.append(f"### A. 叙事与剧本基因（板块得分：{result.narrative.weighted_score()}）")
    lines.append("")
    lines.append("| 分析维度 | 内容 |")
    lines.append("|----------|------|")

    for dim_key, dim_name in NARRATIVE_DIM_NAMES.items():
        dim: DimensionScore = getattr(result.narrative, dim_key)
        detail = _render_dimension_detail(dim_name, dim)
        # 表格内换行用 <br>
        detail_cell = detail.replace("\n", "<br>")
        lines.append(f"| {dim_name} | {detail_cell} |")

    lines.append("")

    # ---------- B. 市场共鸣与竞争定位 ----------
    lines.append(f"### B. 市场共鸣与竞争定位（板块得分：{result.market.weighted_score()}）")
    lines.append("")
    lines.append("| 分析维度 | 内容 |")
    lines.append("|----------|------|")

    for dim_key, dim_name in MARKET_DIM_NAMES.items():
        dim: DimensionScore = getattr(result.market, dim_key)
        detail = _render_dimension_detail(dim_name, dim)
        detail_cell = detail.replace("\n", "<br>")
        lines.append(f"| {dim_name} | {detail_cell} |")

    lines.append("")

    # ---------- C. 合规性评估 ----------
    lines.append(f"### C. 合规性评估（板块得分：{result.compliance.weighted_score()}）")
    lines.append("")
    lines.append("| 分析维度 | 内容 |")
    lines.append("|----------|------|")

    # 内容合规性
    dim = result.compliance.content_compliance
    detail = _render_dimension_detail("内容合规性", dim)
    detail_cell = detail.replace("\n", "<br>")
    lines.append(f"| 内容合规性 | {detail_cell} |")

    # 价值观导向
    dim = result.compliance.value_orientation
    detail = _render_dimension_detail("价值观导向", dim)
    detail_cell = detail.replace("\n", "<br>")
    lines.append(f"| 价值观导向 | {detail_cell} |")

    lines.append("")

    # ---------- D. 商业化与ROI展望 ----------
    lines.append(f"### D. 商业化与ROI展望（板块得分：{result.commercial.weighted_score()}）")
    lines.append("")
    lines.append("| 分析维度 | 内容 |")
    lines.append("|----------|------|")

    # 制作难度
    prod = result.commercial.production_difficulty
    prod_detail = _render_dimension_detail("制作难度", prod)
    prod_detail += f"<br>**难度等级：** {prod.level}"
    prod_cell = prod_detail.replace("\n", "<br>")
    lines.append(f"| 制作难度 | {prod_cell} |")

    # 变现潜力
    mon = result.commercial.monetization_potential
    mon_detail = _render_dimension_detail("变现潜力", mon)
    if mon.paywall_suggestions:
        mon_detail += "<br>**付费点建议：**"
        for i, s in enumerate(mon.paywall_suggestions, 1):
            mon_detail += f"<br>{i}. {s}"
    mon_cell = mon_detail.replace("\n", "<br>")
    lines.append(f"| 变现潜力 | {mon_cell} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ========== IV. 评分总览 ==========
    lines.append("## IV. 评分总览")
    lines.append("")
    lines.append("### 板块得分")
    lines.append("")
    lines.append("| 板块 | 权重 | 得分 |")
    lines.append("|------|------|------|")
    lines.append(f"| A. 叙事与剧本基因 | 35% | {result.narrative.weighted_score()} |")
    lines.append(f"| B. 市场共鸣与竞争定位 | 30% | {result.market.weighted_score()} |")
    lines.append(f"| C. 合规性评估 | 15% | {result.compliance.weighted_score()} |")
    lines.append(f"| D. 商业化与ROI展望 | 20% | {result.commercial.weighted_score()} |")
    lines.append(f"| **总分** | **100%** | **{result.total_score}** |")
    lines.append("")

    # 各维度得分明细
    lines.append("### 维度得分明细")
    lines.append("")
    lines.append("| 板块 | 维度 | 得分 | 等级 |")
    lines.append("|------|------|------|------|")

    for dim_key, dim_name in NARRATIVE_DIM_NAMES.items():
        dim = getattr(result.narrative, dim_key)
        lines.append(f"| A | {dim_name} | {dim.score} | {dim.grade} |")

    for dim_key, dim_name in MARKET_DIM_NAMES.items():
        dim = getattr(result.market, dim_key)
        lines.append(f"| B | {dim_name} | {dim.score} | {dim.grade} |")

    lines.append(f"| C | 内容合规性 | {result.compliance.content_compliance.score} | {result.compliance.content_compliance.grade} |")
    lines.append(f"| C | 价值观导向 | {result.compliance.value_orientation.score} | {result.compliance.value_orientation.grade} |")
    lines.append(f"| D | 制作难度 | {result.commercial.production_difficulty.score} | {result.commercial.production_difficulty.grade} |")
    lines.append(f"| D | 变现潜力 | {result.commercial.monetization_potential.score} | {result.commercial.monetization_potential.grade} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ========== V. 可操作建议 ==========
    lines.append("## V. 可操作建议")
    lines.append("")

    if result.suggestions:
        for i, s in enumerate(result.suggestions, 1):
            lines.append(f"{i}. **{s.title}：** {s.detail}")
            lines.append("")
    else:
        lines.append("暂无建议。")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*本报告由 AI 自动生成，仅供参考。*")
    lines.append("")

    return "\n".join(lines)
