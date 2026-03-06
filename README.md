# 短剧剧本商业潜力评估工具 (Script Eval)

基于 AI 的短剧剧本商业潜力自动评估工具。输入剧本文本，自动产出结构化评估报告。

## 文件说明

| 文件 | 用途 |
|------|------|
| `methodology.md` | 评估方法论：维度体系、权重、评分标准、评估陷阱 |
| `prompts.md` | 各评估步骤的标准化 prompt 模板 |
| `script_eval.py` | 核心评估引擎，含 CLI 入口 |
| `report_generator.py` | Markdown 报告生成器 |
| `examples/sample_report.md` | 示例评估报告（对标《明月照君归》） |

## 评估体系

### 四大板块 · 17个维度

| 板块 | 权重 | 维度 |
|------|------|------|
| A. 叙事与剧本基因 | 35% | 钩子强度、爽点密度、节奏步调、情节连贯性、角色吸引力、对白质量、悬念有效性 |
| B. 市场共鸣与竞争定位 | 30% | 爆款契合度、原创性、观众吸引力、用户粘性、传播潜力、IP衍生价值 |
| C. 合规性评估 | 15% | 内容合规性、价值观导向 |
| D. 商业化与ROI展望 | 20% | 制作难度、变现潜力 |

### 评分等级

| 等级 | 分数 | 含义 |
|------|------|------|
| S | 90-100 | 极具商业爆款潜力 |
| A | 80-89 | 商业潜力优秀 |
| B | 70-79 | 商业潜力中等，需打磨 |
| C | 60-69 | 商业潜力较弱 |
| D | <60 | 不建议投入 |

## 快速开始

### 环境准备

```bash
pip install openai
```

### 命令行使用

```bash
# 基础用法：评估单个剧本
python script_eval.py --input 剧本.txt --output 评估报告.md --api-key YOUR_KEY

# 使用百度文心（默认）
export SCRIPT_EVAL_API_KEY=your_api_key
python script_eval.py -i 剧本.txt -o 报告.md

# 使用 OpenAI
python script_eval.py -i 剧本.txt -o 报告.md \
  --model gpt-4o \
  --base-url https://api.openai.com/v1 \
  --api-key YOUR_OPENAI_KEY

# 使用 DeepSeek
python script_eval.py -i 剧本.txt -o 报告.md \
  --model deepseek-chat \
  --base-url https://api.deepseek.com/v1 \
  --api-key YOUR_DEEPSEEK_KEY

# 批量评估
python script_eval.py --input-dir ./scripts/ --output-dir ./reports/

# 输出 JSON 格式
python script_eval.py -i 剧本.txt --json

# 详细日志
python script_eval.py -i 剧本.txt -o 报告.md -v
```

### Python API 使用

```python
from script_eval import ScriptEvaluator
from report_generator import generate_markdown_report

# 初始化
evaluator = ScriptEvaluator(
    api_key="your_api_key",
    model="ernie-4.5-8k",              # 或 gpt-4o / deepseek-chat
    base_url="https://qianfan.baidubce.com/v2",
    verbose=True,
)

# 评估
script_text = open("剧本.txt", encoding="utf-8").read()
result = evaluator.evaluate(script_text)

# 查看结果
print(f"总分: {result.total_score}/100 ({result.total_grade}级)")
print(f"叙事基因: {result.narrative.weighted_score()}")
print(f"市场共鸣: {result.market.weighted_score()}")
print(f"合规性: {result.compliance.weighted_score()}")
print(f"商业化: {result.commercial.weighted_score()}")

# 生成报告
report = generate_markdown_report(result)
with open("评估报告.md", "w", encoding="utf-8") as f:
    f.write(report)

# 获取 JSON
import json
print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
```

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input, -i` | 单个剧本文件路径 | 必填（与 --input-dir 二选一）|
| `--input-dir` | 批量评估目录 | |
| `--output, -o` | 输出报告路径 | stdout |
| `--output-dir` | 批量输出目录 | `{input-dir}/reports/` |
| `--json` | 输出 JSON 格式 | false |
| `--api-key` | API Key | `$SCRIPT_EVAL_API_KEY` 或 `$OPENAI_API_KEY` |
| `--model` | 模型名称 | `ernie-4.5-8k` |
| `--base-url` | API Base URL | `https://qianfan.baidubce.com/v2` |
| `--max-chars` | 剧本最大字符数 | 80000 |
| `--verbose, -v` | 详细日志 | false |

## 评估流程

```
输入剧本文本
     │
     ▼
[Step 1] 基础信息提取（题材、角色、场景）
     │
     ▼
[Step 2] 四大板块并行评估（4个LLM调用并发）
  ├── A. 叙事与剧本基因（7个维度）
  ├── B. 市场共鸣（6个维度）
  ├── C. 合规性（2个维度）
  └── D. 商业化（2个维度）
     │
     ▼
[Step 3] 加权汇总 → 总分 + 等级 + 一票否决检查
     │
     ▼
[Step 4] 生成核心结论 + 5-8条可操作建议
     │
     ▼
[Step 5] 输出 Markdown 报告
```

总计 6 次 LLM 调用（Step 2 的 4 次并发 + Step 1 和 Step 4 各 1 次）。

## 扩展

### 支持其他剧本类型

当前默认配置针对竖屏短剧优化。通过调整 `methodology.md` 中的权重和评分标准，可适配：
- **长剧**：降低爽点密度权重，提升情节连贯性和角色深度
- **电影**：取消付费点设计，增加三幕结构评估

### 自定义评估维度

修改 `script_eval.py` 中的 prompt 模板和数据结构即可增减维度。

### 集成到业务系统

`ScriptEvaluator.evaluate()` 返回结构化的 `EvalResult` 对象，可直接序列化为 JSON 供下游系统消费。
