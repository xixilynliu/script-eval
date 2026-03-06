#!/usr/bin/env python3
"""
短剧剧本商业潜力评估引擎

使用 OpenAI 兼容接口调用 LLM，对剧本进行结构化评估。
支持百度文心、OpenAI、DeepSeek 等兼容 API。

用法：
    # 命令行
    python script_eval.py --input 剧本.txt --output 评估报告.md
    python script_eval.py --input-dir ./scripts/ --output-dir ./reports/

    # Python API
    from script_eval import ScriptEvaluator
    evaluator = ScriptEvaluator(api_key="xxx")
    result = evaluator.evaluate(open("剧本.txt").read())
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    print("需要安装 openai 库: pip install openai")
    sys.exit(1)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class CharacterInfo:
    name: str
    role: str  # 主角/配角
    description: str


@dataclass
class BasicInfo:
    title: str = "未知"
    genre: str = "通用"  # 女频/男频/通用
    themes: list = field(default_factory=list)
    episode_count: int = -1
    main_characters: list = field(default_factory=list)
    scenes: dict = field(default_factory=lambda: {"day": [], "night": []})
    plot_summary: str = ""
    plot_features: str = ""
    time_setting: str = "未知"


@dataclass
class DimensionScore:
    """单个维度的评分结果"""
    score: int = 0
    grade: str = "D"
    analysis: list = field(default_factory=list)
    improvements: list = field(default_factory=list)


@dataclass
class NarrativeScore:
    """A板块：叙事与剧本基因"""
    hook_strength: DimensionScore = field(default_factory=DimensionScore)
    excitement_density: DimensionScore = field(default_factory=DimensionScore)
    pacing: DimensionScore = field(default_factory=DimensionScore)
    plot_coherence: DimensionScore = field(default_factory=DimensionScore)
    character_appeal: DimensionScore = field(default_factory=DimensionScore)
    dialogue_quality: DimensionScore = field(default_factory=DimensionScore)
    suspense_effectiveness: DimensionScore = field(default_factory=DimensionScore)

    # 板块内权重
    WEIGHTS = {
        "hook_strength": 0.20,
        "excitement_density": 0.20,
        "pacing": 0.15,
        "plot_coherence": 0.15,
        "character_appeal": 0.15,
        "dialogue_quality": 0.08,
        "suspense_effectiveness": 0.07,
    }

    def weighted_score(self) -> float:
        total = 0
        for dim_name, weight in self.WEIGHTS.items():
            dim: DimensionScore = getattr(self, dim_name)
            total += dim.score * weight
        return round(total, 1)


@dataclass
class MarketScore:
    """B板块：市场共鸣与竞争定位"""
    hit_potential: DimensionScore = field(default_factory=DimensionScore)
    originality: DimensionScore = field(default_factory=DimensionScore)
    audience_attraction: DimensionScore = field(default_factory=DimensionScore)
    user_stickiness: DimensionScore = field(default_factory=DimensionScore)
    viral_potential: DimensionScore = field(default_factory=DimensionScore)
    ip_value: DimensionScore = field(default_factory=DimensionScore)

    WEIGHTS = {
        "hit_potential": 0.25,
        "originality": 0.20,
        "audience_attraction": 0.20,
        "user_stickiness": 0.15,
        "viral_potential": 0.10,
        "ip_value": 0.10,
    }

    def weighted_score(self) -> float:
        total = 0
        for dim_name, weight in self.WEIGHTS.items():
            dim: DimensionScore = getattr(self, dim_name)
            total += dim.score * weight
        return round(total, 1)


@dataclass
class ComplianceScore:
    """C板块：合规性评估"""
    content_compliance: DimensionScore = field(default_factory=DimensionScore)
    value_orientation: DimensionScore = field(default_factory=DimensionScore)

    WEIGHTS = {
        "content_compliance": 0.60,
        "value_orientation": 0.40,
    }

    def weighted_score(self) -> float:
        total = 0
        for dim_name, weight in self.WEIGHTS.items():
            dim: DimensionScore = getattr(self, dim_name)
            total += dim.score * weight
        return round(total, 1)


@dataclass
class ProductionDifficultyScore(DimensionScore):
    """制作难度（扩展了场景表和难度等级）"""
    level: str = "中"
    scene_table: dict = field(default_factory=lambda: {"day": [], "night": []})


@dataclass
class MonetizationScore(DimensionScore):
    """变现潜力（扩展了付费点建议）"""
    paywall_suggestions: list = field(default_factory=list)


@dataclass
class CommercialScore:
    """D板块：商业化与ROI展望"""
    production_difficulty: ProductionDifficultyScore = field(
        default_factory=ProductionDifficultyScore
    )
    monetization_potential: MonetizationScore = field(
        default_factory=MonetizationScore
    )

    WEIGHTS = {
        "production_difficulty": 0.40,
        "monetization_potential": 0.60,
    }

    def weighted_score(self) -> float:
        total = 0
        total += self.production_difficulty.score * 0.40
        total += self.monetization_potential.score * 0.60
        return round(total, 1)


@dataclass
class Suggestion:
    title: str
    detail: str


@dataclass
class EvalResult:
    """完整评估结果"""
    basic_info: BasicInfo = field(default_factory=BasicInfo)
    total_score: int = 0
    total_grade: str = "D"
    core_conclusion: str = ""
    narrative: NarrativeScore = field(default_factory=NarrativeScore)
    market: MarketScore = field(default_factory=MarketScore)
    compliance: ComplianceScore = field(default_factory=ComplianceScore)
    commercial: CommercialScore = field(default_factory=CommercialScore)
    suggestions: list = field(default_factory=list)
    risk_warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
# Prompt 模板
# ============================================================

PROMPT_BASIC_INFO = """你是一个专业的剧本分析师。请阅读以下剧本文本，提取基础信息。

【剧本文本】：
{script_text}

请严格按以下 JSON 格式输出，不要输出任何其他内容：

{{
  "title": "剧本名称（从文本中识别，如无法识别则填'未知'）",
  "genre": "频类（女频/男频/通用）",
  "themes": ["题材标签1", "题材标签2"],
  "episode_count": 集数整数,
  "main_characters": [
    {{"name": "角色名", "role": "主角/配角", "description": "一句话角色定位"}}
  ],
  "scenes": {{
    "day": ["日景场景1", "日景场景2"],
    "night": ["夜景场景1", "夜景场景2"]
  }},
  "plot_summary": "100字以内的剧情主线概述",
  "plot_features": "50字以内的剧情特点描述",
  "time_setting": "时代背景"
}}"""

PROMPT_NARRATIVE = """你是一个资深的短剧商业评估专家。请对以下剧本进行「叙事与剧本基因」维度的深度评估。

【剧本基础信息】：
{basic_info_json}

【剧本文本】：
{script_text}

请从以下 7 个维度逐一评估，每个维度必须包含：评分（0-100整数）、3条分析要点、至少2条可打磨建议。

评分标准：90-100(S级) / 80-89(A级) / 70-79(B级) / 60-69(C级) / <60(D级)

维度1：钩子强度（权重20%）- 前30秒/第一集开篇吸引力、悬念设置强度、角色魅力展现速度
维度2：爽点密度（权重20%）- 爽点分布均匀度、类型覆盖、集均密度、升级递进
维度3：节奏与步调（权重15%）- 短剧节奏适配度、单场戏时长、信息释放节奏
维度4：情节连贯性（权重15%）- 主线逻辑、人物动机、伏笔呼应、时间线
维度5：角色吸引力（权重15%）- 主角共鸣、角色魅力、配角功能性、人物关系
维度6：对白质量（权重8%）- 风格匹配、金句密度、网感传播性、语言区分度
维度7：悬念有效性（权重7%）- 集尾钩子、多层次悬念、解答循环、视觉化悬念

严格按以下 JSON 格式输出，不要输出其他内容：

{{
  "hook_strength": {{"score": 72, "grade": "B", "analysis": ["要点1", "要点2", "要点3"], "improvements": ["建议1", "建议2"]}},
  "excitement_density": {{"score": 75, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "pacing": {{"score": 74, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "plot_coherence": {{"score": 82, "grade": "A", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "character_appeal": {{"score": 80, "grade": "A", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "dialogue_quality": {{"score": 76, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "suspense_effectiveness": {{"score": 77, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}}
}}

要求：分析要点必须有具体剧本内容引用，建议必须具体可执行，评分客观严格。"""

PROMPT_MARKET = """你是一个资深的短剧市场分析专家。请对以下剧本进行「市场共鸣与竞争定位」维度的深度评估。

【剧本基础信息】：
{basic_info_json}

【剧本文本】：
{script_text}

从以下 6 个维度评估，每个维度：评分（0-100）、3条分析要点、至少2条可打磨建议。

维度1：爆款契合度（权重25%）- 题材热度、核心元素齐全度、对标爆款相似度
维度2：原创性（权重20%）- 人物关系新意、核心机制创新、套路内差异化
维度3：观众吸引力（权重20%）- 受众定位精准度、情感冲突层次、跨圈层吸引力
维度4：用户粘性（权重15%）- 连载潜力、角色讨论度、情感投入度、互动话题
维度5：传播潜力（权重10%）- 视觉传播、金句传播性、话题营销、跨平台适配
维度6：IP衍生价值（权重10%）- 世界观扩展性、角色IP化、跨媒体改编

严格按以下 JSON 格式输出：

{{
  "hit_potential": {{"score": 81, "grade": "A", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "originality": {{"score": 73, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "audience_attraction": {{"score": 79, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "user_stickiness": {{"score": 76, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "viral_potential": {{"score": 74, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}},
  "ip_value": {{"score": 72, "grade": "B", "analysis": ["...", "...", "..."], "improvements": ["...", "..."]}}
}}"""

PROMPT_COMPLIANCE = """你是一个专业的内容合规审核专家。请对以下剧本进行合规性评估。

【剧本基础信息】：
{basic_info_json}

【剧本文本】：
{script_text}

从以下 2 个维度评估：

维度1：内容合规性（权重60%）
检查项：政治安全、暴力尺度、性内容尺度、未成年人保护、社会影响

维度2：价值观导向（权重40%）
检查项：情感价值观、家庭伦理、权力观念、性别形象、正面示范

严格按以下 JSON 格式输出：

{{
  "content_compliance": {{"score": 88, "grade": "A+", "analysis": ["...", "...", "..."], "risk_items": [], "improvements": []}},
  "value_orientation": {{"score": 85, "grade": "A+", "analysis": ["...", "...", "..."], "improvements": []}}
}}

合规评估必须严格客观，明确指出每个潜在风险点。"""

PROMPT_COMMERCIAL = """你是一个资深的短剧商业分析专家。请对以下剧本进行商业化潜力评估。

【剧本基础信息】：
{basic_info_json}

【剧本文本】：
{script_text}

从以下 2 个维度评估：

维度1：制作难度（权重40%）
评估：场景数量和复杂度、演员要求、特效需求、服化道投入、群演需求、难度等级（低/中/高/极高）
注意：制作难度越高，该维度得分越低（因为短剧对成本敏感）

维度2：变现潜力（权重60%）
评估：付费点设计空间（具体到集数）、广告植入适配度、打赏潜力、可商业化元素

严格按以下 JSON 格式输出：

{{
  "production_difficulty": {{
    "score": 65, "grade": "C", "level": "高",
    "analysis": ["...", "...", "..."],
    "scene_table": {{"day": ["日景1"], "night": ["夜景1"]}},
    "improvements": ["...", "..."]
  }},
  "monetization_potential": {{
    "score": 78, "grade": "B",
    "analysis": ["...", "...", "..."],
    "paywall_suggestions": ["第X集末尾：情节描述"],
    "improvements": ["...", "..."]
  }}
}}"""

PROMPT_SUMMARY = """你是一个资深的短剧商业评估专家。请基于以下评估结果，生成核心结论和可操作建议。

【剧本基础信息】：
{basic_info_json}

【各板块评估结果】：
{all_scores_json}

【总体评分】：{total_score}/100（{total_grade}级）

生成：
1. 核心结论（200字以内）：总结核心优势和问题，给出投入判断
2. 可操作建议（5-8条）：按优先级排序，每条具体可执行

严格按以下 JSON 格式输出：

{{
  "core_conclusion": "核心结论文本",
  "suggestions": [
    {{"title": "建议标题", "detail": "详细建议内容"}}
  ]
}}"""


# ============================================================
# 工具函数
# ============================================================

def score_to_grade(score: int) -> str:
    """将百分制分数转换为等级"""
    if score >= 90:
        return "S"
    elif score >= 85:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    else:
        return "D"


def parse_json_response(text: str) -> dict:
    """从 LLM 响应中解析 JSON，处理 markdown 代码块等干扰"""
    # 尝试直接解析
    text = text.strip()

    # 移除 markdown 代码块标记
    if text.startswith("```"):
        lines = text.split("\n")
        # 移除首行 ```json 或 ```
        lines = lines[1:]
        # 移除末尾 ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # 尝试找到 JSON 对象
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        text = text[brace_start : brace_end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 尝试修复常见问题：尾部多余逗号
        text_fixed = re.sub(r",\s*}", "}", text)
        text_fixed = re.sub(r",\s*]", "]", text_fixed)
        try:
            return json.loads(text_fixed)
        except json.JSONDecodeError:
            raise ValueError(f"无法解析 LLM 返回的 JSON: {e}\n原文: {text[:500]}...")


def truncate_script(script_text: str, max_chars: int = 80000) -> str:
    """截断过长的剧本文本，保留前后部分"""
    if len(script_text) <= max_chars:
        return script_text

    # 保留前70%和后30%
    front = int(max_chars * 0.7)
    back = max_chars - front
    return (
        script_text[:front]
        + f"\n\n...... [中间省略约{len(script_text) - max_chars}字] ......\n\n"
        + script_text[-back:]
    )


# ============================================================
# 核心评估引擎
# ============================================================

class ScriptEvaluator:
    """短剧剧本商业潜力评估引擎"""

    # 四大板块权重
    SECTION_WEIGHTS = {
        "narrative": 0.35,
        "market": 0.30,
        "compliance": 0.15,
        "commercial": 0.20,
    }

    def __init__(
        self,
        api_key: str,
        model: str = "ernie-4.5-8k",
        base_url: str = "https://qianfan.baidubce.com/v2",
        max_script_chars: int = 80000,
        verbose: bool = False,
    ):
        """
        初始化评估引擎。

        Args:
            api_key: API Key
            model: 模型名称，支持 ernie-4.5-8k / gpt-4o / deepseek-chat 等
            base_url: API 基础 URL
            max_script_chars: 剧本最大字符数限制
            verbose: 是否输出详细日志
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_script_chars = max_script_chars
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[ScriptEval] {msg}")

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """调用 LLM 并返回文本响应"""
        self._log(f"调用 LLM，prompt 长度: {len(prompt)} 字符")
        start = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=4096,
        )

        result = response.choices[0].message.content
        elapsed = time.time() - start
        self._log(f"LLM 响应完成，耗时 {elapsed:.1f}s，响应长度: {len(result)} 字符")
        return result

    def _call_llm_json(self, prompt: str, temperature: float = 0.3) -> dict:
        """调用 LLM 并解析为 JSON"""
        text = self._call_llm(prompt, temperature)
        return parse_json_response(text)

    def evaluate(self, script_text: str) -> EvalResult:
        """
        对剧本进行完整评估。

        Args:
            script_text: 剧本原文

        Returns:
            EvalResult 评估结果
        """
        result = EvalResult()
        script_truncated = truncate_script(script_text, self.max_script_chars)

        # Step 1: 提取基础信息
        self._log("Step 1: 提取基础信息...")
        result.basic_info = self._extract_basic_info(script_truncated)
        basic_info_json = json.dumps(asdict(result.basic_info), ensure_ascii=False, indent=2)
        self._log(f"  剧本名称: {result.basic_info.title}")
        self._log(f"  频类: {result.basic_info.genre}")
        self._log(f"  题材: {', '.join(result.basic_info.themes)}")

        # Step 2: 四大板块并行评估
        self._log("Step 2: 四大板块评估（并行）...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self._eval_narrative, script_truncated, basic_info_json
                ): "narrative",
                executor.submit(
                    self._eval_market, script_truncated, basic_info_json
                ): "market",
                executor.submit(
                    self._eval_compliance, script_truncated, basic_info_json
                ): "compliance",
                executor.submit(
                    self._eval_commercial, script_truncated, basic_info_json
                ): "commercial",
            }

            for future in as_completed(futures):
                section = futures[future]
                try:
                    score_obj = future.result()
                    setattr(result, section, score_obj)
                    self._log(f"  {section} 完成: {score_obj.weighted_score()}")
                except Exception as e:
                    self._log(f"  {section} 评估失败: {e}")
                    # 保留默认值

        # Step 3: 计算总分
        self._log("Step 3: 计算总分...")
        result.total_score = self._calc_total_score(result)
        result.total_grade = score_to_grade(result.total_score)
        self._log(f"  总分: {result.total_score}/100 ({result.total_grade}级)")

        # 一票否决检查
        result.risk_warnings = self._check_vetoes(result)
        if result.risk_warnings:
            self._log(f"  风险预警: {result.risk_warnings}")

        # Step 4: 生成结论和建议
        self._log("Step 4: 生成结论和建议...")
        self._generate_summary(result, script_truncated, basic_info_json)

        self._log("评估完成！")
        return result

    def _extract_basic_info(self, script_text: str) -> BasicInfo:
        """提取剧本基础信息"""
        prompt = PROMPT_BASIC_INFO.format(script_text=script_text[:30000])
        try:
            data = self._call_llm_json(prompt)
            info = BasicInfo(
                title=data.get("title", "未知"),
                genre=data.get("genre", "通用"),
                themes=data.get("themes", []),
                episode_count=data.get("episode_count", -1),
                main_characters=data.get("main_characters", []),
                scenes=data.get("scenes", {"day": [], "night": []}),
                plot_summary=data.get("plot_summary", ""),
                plot_features=data.get("plot_features", ""),
                time_setting=data.get("time_setting", "未知"),
            )
            return info
        except Exception as e:
            self._log(f"基础信息提取失败: {e}，使用默认值")
            return BasicInfo()

    def _parse_dimension_score(self, data: dict) -> DimensionScore:
        """解析单个维度评分"""
        return DimensionScore(
            score=int(data.get("score", 0)),
            grade=data.get("grade", score_to_grade(int(data.get("score", 0)))),
            analysis=data.get("analysis", []),
            improvements=data.get("improvements", []),
        )

    def _eval_narrative(self, script_text: str, basic_info_json: str) -> NarrativeScore:
        """评估 A板块：叙事与剧本基因"""
        prompt = PROMPT_NARRATIVE.format(
            basic_info_json=basic_info_json, script_text=script_text
        )
        data = self._call_llm_json(prompt)

        score = NarrativeScore()
        for dim_name in NarrativeScore.WEIGHTS:
            if dim_name in data:
                setattr(score, dim_name, self._parse_dimension_score(data[dim_name]))
        return score

    def _eval_market(self, script_text: str, basic_info_json: str) -> MarketScore:
        """评估 B板块：市场共鸣与竞争定位"""
        prompt = PROMPT_MARKET.format(
            basic_info_json=basic_info_json, script_text=script_text
        )
        data = self._call_llm_json(prompt)

        score = MarketScore()
        for dim_name in MarketScore.WEIGHTS:
            if dim_name in data:
                setattr(score, dim_name, self._parse_dimension_score(data[dim_name]))
        return score

    def _eval_compliance(self, script_text: str, basic_info_json: str) -> ComplianceScore:
        """评估 C板块：合规性评估"""
        prompt = PROMPT_COMPLIANCE.format(
            basic_info_json=basic_info_json, script_text=script_text
        )
        data = self._call_llm_json(prompt)

        score = ComplianceScore()
        if "content_compliance" in data:
            d = data["content_compliance"]
            score.content_compliance = DimensionScore(
                score=int(d.get("score", 0)),
                grade=d.get("grade", ""),
                analysis=d.get("analysis", []),
                improvements=d.get("improvements", []),
            )
        if "value_orientation" in data:
            d = data["value_orientation"]
            score.value_orientation = DimensionScore(
                score=int(d.get("score", 0)),
                grade=d.get("grade", ""),
                analysis=d.get("analysis", []),
                improvements=d.get("improvements", []),
            )
        return score

    def _eval_commercial(self, script_text: str, basic_info_json: str) -> CommercialScore:
        """评估 D板块：商业化与ROI展望"""
        prompt = PROMPT_COMMERCIAL.format(
            basic_info_json=basic_info_json, script_text=script_text
        )
        data = self._call_llm_json(prompt)

        score = CommercialScore()
        if "production_difficulty" in data:
            d = data["production_difficulty"]
            score.production_difficulty = ProductionDifficultyScore(
                score=int(d.get("score", 0)),
                grade=d.get("grade", ""),
                level=d.get("level", "中"),
                scene_table=d.get("scene_table", {"day": [], "night": []}),
                analysis=d.get("analysis", []),
                improvements=d.get("improvements", []),
            )
        if "monetization_potential" in data:
            d = data["monetization_potential"]
            score.monetization_potential = MonetizationScore(
                score=int(d.get("score", 0)),
                grade=d.get("grade", ""),
                analysis=d.get("analysis", []),
                paywall_suggestions=d.get("paywall_suggestions", []),
                improvements=d.get("improvements", []),
            )
        return score

    def _calc_total_score(self, result: EvalResult) -> int:
        """加权计算总分"""
        total = (
            result.narrative.weighted_score() * self.SECTION_WEIGHTS["narrative"]
            + result.market.weighted_score() * self.SECTION_WEIGHTS["market"]
            + result.compliance.weighted_score() * self.SECTION_WEIGHTS["compliance"]
            + result.commercial.weighted_score() * self.SECTION_WEIGHTS["commercial"]
        )
        return round(total)

    def _check_vetoes(self, result: EvalResult) -> list:
        """一票否决检查"""
        warnings = []
        if result.compliance.content_compliance.score < 60:
            warnings.append(
                f"合规风险预警：内容合规性得分 {result.compliance.content_compliance.score}，低于60分安全线"
            )
        if result.narrative.hook_strength.score < 50:
            warnings.append(
                f"留存风险预警：钩子强度得分 {result.narrative.hook_strength.score}，开篇无法留住观众"
            )
        if result.narrative.pacing.score < 50:
            warnings.append(
                f"节奏风险预警：节奏步调得分 {result.narrative.pacing.score}，完全不适配短剧"
            )
        return warnings

    def _generate_summary(
        self, result: EvalResult, script_text: str, basic_info_json: str
    ):
        """生成执行摘要和建议"""
        # 构造各板块得分摘要
        scores_summary = {
            "A_叙事与剧本基因": {
                "板块加权得分": result.narrative.weighted_score(),
                "钩子强度": result.narrative.hook_strength.score,
                "爽点密度": result.narrative.excitement_density.score,
                "节奏步调": result.narrative.pacing.score,
                "情节连贯性": result.narrative.plot_coherence.score,
                "角色吸引力": result.narrative.character_appeal.score,
                "对白质量": result.narrative.dialogue_quality.score,
                "悬念有效性": result.narrative.suspense_effectiveness.score,
            },
            "B_市场共鸣": {
                "板块加权得分": result.market.weighted_score(),
                "爆款契合度": result.market.hit_potential.score,
                "原创性": result.market.originality.score,
                "观众吸引力": result.market.audience_attraction.score,
                "用户粘性": result.market.user_stickiness.score,
                "传播潜力": result.market.viral_potential.score,
                "IP衍生价值": result.market.ip_value.score,
            },
            "C_合规性": {
                "板块加权得分": result.compliance.weighted_score(),
                "内容合规性": result.compliance.content_compliance.score,
                "价值观导向": result.compliance.value_orientation.score,
            },
            "D_商业化": {
                "板块加权得分": result.commercial.weighted_score(),
                "制作难度": result.commercial.production_difficulty.score,
                "变现潜力": result.commercial.monetization_potential.score,
            },
        }

        prompt = PROMPT_SUMMARY.format(
            basic_info_json=basic_info_json,
            all_scores_json=json.dumps(scores_summary, ensure_ascii=False, indent=2),
            total_score=result.total_score,
            total_grade=result.total_grade,
        )

        try:
            data = self._call_llm_json(prompt)
            result.core_conclusion = data.get("core_conclusion", "")
            raw_suggestions = data.get("suggestions", [])
            result.suggestions = [
                Suggestion(title=s.get("title", ""), detail=s.get("detail", ""))
                for s in raw_suggestions
                if isinstance(s, dict)
            ]
        except Exception as e:
            self._log(f"建议生成失败: {e}")
            result.core_conclusion = "建议生成失败，请查看各维度详细评分。"
            result.suggestions = []


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="短剧剧本商业潜力评估工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 评估单个剧本
  python script_eval.py --input 剧本.txt --output 评估报告.md

  # 指定模型
  python script_eval.py --input 剧本.txt --model gpt-4o --base-url https://api.openai.com/v1

  # 批量评估
  python script_eval.py --input-dir ./scripts/ --output-dir ./reports/

  # 输出JSON（不生成Markdown报告）
  python script_eval.py --input 剧本.txt --json
        """,
    )

    # 输入参数
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", "-i", help="单个剧本文件路径")
    input_group.add_argument("--input-dir", help="批量评估：剧本目录")

    # 输出参数
    parser.add_argument("--output", "-o", help="输出报告文件路径")
    parser.add_argument("--output-dir", help="批量评估：输出目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")

    # API 参数
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SCRIPT_EVAL_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
        help="API Key（默认读取 SCRIPT_EVAL_API_KEY 或 OPENAI_API_KEY 环境变量）",
    )
    parser.add_argument(
        "--model",
        default="ernie-4.5-8k",
        help="模型名称（默认 ernie-4.5-8k）",
    )
    parser.add_argument(
        "--base-url",
        default="https://qianfan.baidubce.com/v2",
        help="API Base URL",
    )

    # 其他参数
    parser.add_argument("--verbose", "-v", action="store_true", help="输出详细日志")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=80000,
        help="剧本最大字符数（默认80000）",
    )

    args = parser.parse_args()

    if not args.api_key:
        print("错误：请通过 --api-key 参数或 SCRIPT_EVAL_API_KEY 环境变量提供 API Key")
        sys.exit(1)

    # 初始化评估器
    evaluator = ScriptEvaluator(
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        max_script_chars=args.max_chars,
        verbose=args.verbose,
    )

    # 延迟导入报告生成器
    from report_generator import generate_markdown_report

    if args.input:
        # 单文件评估
        script_path = Path(args.input)
        if not script_path.exists():
            print(f"错误：文件不存在 {script_path}")
            sys.exit(1)

        print(f"正在评估: {script_path.name}")
        script_text = script_path.read_text(encoding="utf-8")
        result = evaluator.evaluate(script_text)

        if args.json:
            output = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        else:
            output = generate_markdown_report(result)

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(output, encoding="utf-8")
            print(f"报告已保存: {output_path}")
        else:
            print(output)

        print(f"\n总分: {result.total_score}/100 ({result.total_grade}级)")
        if result.risk_warnings:
            for w in result.risk_warnings:
                print(f"⚠ {w}")

    elif args.input_dir:
        # 批量评估
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir) if args.output_dir else input_dir / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)

        script_files = list(input_dir.glob("*.txt")) + list(input_dir.glob("*.md"))
        if not script_files:
            print(f"错误：{input_dir} 中没有找到 .txt 或 .md 文件")
            sys.exit(1)

        print(f"找到 {len(script_files)} 个剧本文件")

        for i, script_path in enumerate(script_files, 1):
            print(f"\n[{i}/{len(script_files)}] 正在评估: {script_path.name}")
            try:
                script_text = script_path.read_text(encoding="utf-8")
                result = evaluator.evaluate(script_text)

                ext = ".json" if args.json else ".md"
                output_path = output_dir / f"{script_path.stem}_评估报告{ext}"

                if args.json:
                    output = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
                else:
                    output = generate_markdown_report(result)

                output_path.write_text(output, encoding="utf-8")
                print(f"  总分: {result.total_score}/100 ({result.total_grade}级) → {output_path}")
            except Exception as e:
                print(f"  评估失败: {e}")

        print(f"\n批量评估完成，报告保存在: {output_dir}")


if __name__ == "__main__":
    main()
