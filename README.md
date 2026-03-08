# Script Eval — 短剧剧本商业潜力诊断

基于 AI 的短剧剧本商业潜力评估工具。输入剧本文本，自动输出四大板块、17 个维度的结构化诊断报告，包含量化评分、详细分析和可操作改稿建议。

**在线体验 →** [https://xixilynliu.github.io/script-eval/](https://xixilynliu.github.io/script-eval/)

---

## 产品定位

面向**短剧编剧、制片人、投资方**，在剧本开发阶段提供快速、系统的商业潜力预评估，辅助决策"投 or 不投"、"改什么"。

**核心价值：**
- 将行业专家的评估经验结构化为 17 个可量化维度
- 从叙事基因、市场共鸣、内容合规、商业化四个板块全方位诊断
- 每个维度给出评分 + 分析依据 + 可打磨方向，而非简单打分
- 最终输出 5-8 条优先级排序的改稿建议

## 评估体系

### 四大板块 · 17 个维度

| 板块 | 权重 | 评估维度 |
|------|------|----------|
| **A. 叙事与剧本基因** | 35% | 钩子强度、爽点密度、节奏步调、情节连贯性、角色吸引力、对白质量、悬念有效性 |
| **B. 市场共鸣与竞争定位** | 30% | 爆款契合度、原创性、观众吸引力、用户粘性、传播潜力、IP衍生价值 |
| **C. 合规性评估** | 15% | 内容合规性、价值观导向 |
| **D. 商业化与ROI展望** | 20% | 制作难度、变现潜力 |

### 评分等级

| 等级 | 分数 | 含义 |
|------|------|------|
| S | 90-100 | 极具商业爆款潜力 |
| A | 80-89 | 商业潜力优秀 |
| B | 70-79 | 商业潜力中等，需打磨 |
| C | 60-69 | 商业潜力较弱，需大幅修改 |
| D | <60 | 不建议投入 |

## 在线 Demo

打开 [在线体验页](https://xixilynliu.github.io/script-eval/)，支持三种方式输入剧本：

1. **粘贴文本** — 直接将剧本内容粘贴到输入框
2. **上传文件** — 支持 `.txt` `.docx` `.pdf` 格式
3. **示例体验** — 点击内置的三个示例剧本标签即可快速体验

内置三个不同题材的示例剧本及对应评估报告：

| 示例 | 题材 | 评级 |
|------|------|------|
| 明月照君归 | 古装虐恋 · 权谋 | B 级 (77分) |
| 你好星期六 | 现代甜宠 · 职场 | B 级 (74分) |
| 第七根琴弦 | 悬疑犯罪 · 社会 | A 级 (81分) |

> 当前 Demo 使用 Mock 数据展示报告效果。接入 LLM API 后可实现真实评估。

## 项目结构

```
script-eval/
├── index.html              # 在线 Demo（单页应用，含完整 UI + Mock 数据）
├── script_eval.py          # 核心评估引擎（调用 LLM API）
├── report_generator.py     # Markdown 报告生成器
├── methodology.md          # 评估方法论（维度定义、权重依据、评分标准）
├── prompts.md              # 各评估步骤的标准化 Prompt 模板
├── samples/                # 示例剧本文本
│   ├── 古装虐恋_明月照君归.txt
│   ├── 现代甜宠_你好星期六.txt
│   └── 悬疑犯罪_第七根琴弦.txt
├── examples/
│   └── sample_report.md    # 示例评估报告
├── PRD_剧本诊断.md          # 产品需求文档
├── product_plan.md         # 产品规划
└── LICENSE                 # MIT License
```

## 快速开始

### 环境准备

```bash
pip install openai
```

### 命令行使用

```bash
# 基础用法
python script_eval.py --input 剧本.txt --output 评估报告.md --api-key YOUR_KEY

# 使用环境变量
export SCRIPT_EVAL_API_KEY=your_api_key
python script_eval.py -i 剧本.txt -o 报告.md

# 指定模型（支持 OpenAI 兼容接口）
python script_eval.py -i 剧本.txt -o 报告.md \
  --model gpt-4o \
  --base-url https://api.openai.com/v1 \
  --api-key YOUR_KEY

# 批量评估
python script_eval.py --input-dir ./scripts/ --output-dir ./reports/

# 输出 JSON 格式
python script_eval.py -i 剧本.txt --json
```

### Python API

```python
from script_eval import ScriptEvaluator
from report_generator import generate_markdown_report

evaluator = ScriptEvaluator(api_key="your_api_key")
result = evaluator.evaluate(open("剧本.txt", encoding="utf-8").read())

print(f"总分: {result.total_score}/100 ({result.total_grade}级)")

# 生成 Markdown 报告
report = generate_markdown_report(result)
with open("评估报告.md", "w", encoding="utf-8") as f:
    f.write(report)
```

### CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input, -i` | 剧本文件路径 | 必填 |
| `--input-dir` | 批量评估目录 | |
| `--output, -o` | 输出报告路径 | stdout |
| `--output-dir` | 批量输出目录 | `{input-dir}/reports/` |
| `--json` | 输出 JSON 格式 | false |
| `--api-key` | API Key | `$SCRIPT_EVAL_API_KEY` |
| `--model` | 模型名称 | `ernie-4.5-8k` |
| `--base-url` | API 地址 | `https://qianfan.baidubce.com/v2` |
| `--verbose, -v` | 详细日志 | false |

## 评估流程

```
输入剧本
  │
  ▼
[Step 1] 基础信息提取（题材、角色、场景）
  │
  ▼
[Step 2] 四大板块并行评估（4 次 LLM 并发调用）
  ├── A. 叙事基因 → 7 个维度评分 + 分析 + 改进点
  ├── B. 市场共鸣 → 6 个维度
  ├── C. 合规性   → 2 个维度
  └── D. 商业化   → 2 个维度
  │
  ▼
[Step 3] 加权汇总 → 总分 + 等级 + 风险预警
  │
  ▼
[Step 4] 生成 5-8 条可操作改稿建议
  │
  ▼
[Step 5] 输出结构化报告（Markdown / JSON）
```

总计 6 次 LLM 调用（Step 2 的 4 次并发 + Step 1 和 Step 4 各 1 次）。

## 支持的 LLM

通过 OpenAI 兼容接口，支持多种模型：

| 模型 | `--model` | `--base-url` |
|------|-----------|--------------|
| 百度文心 | `ernie-4.5-8k` | `https://qianfan.baidubce.com/v2` |
| OpenAI | `gpt-4o` | `https://api.openai.com/v1` |
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com/v1` |
| 其他兼容接口 | 自定义 | 自定义 |

## 扩展

- **适配长剧/电影**：调整 `methodology.md` 中的权重和评分标准
- **自定义维度**：修改 `script_eval.py` 中的 Prompt 模板和数据结构
- **集成到业务系统**：`ScriptEvaluator.evaluate()` 返回结构化 `EvalResult`，可序列化为 JSON

## License

[MIT](LICENSE)
