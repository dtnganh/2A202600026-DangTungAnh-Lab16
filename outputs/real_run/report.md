# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_100.json
- Mode: mock
- Records: 300
- Agents: mini_lats_branching, react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.86 | 0.93 | 0.07 |
| Avg attempts | 1 | 1.23 | 0.23 |
| Avg token estimate | 1741.16 | 2249.44 | 508.28 |
| Avg latency (ms) | 2170.8 | 3056.21 | 885.41 |

## Failure modes
```json
{
  "react": {
    "none": 86,
    "entity_drift": 7,
    "wrong_final_answer": 7
  },
  "reflexion": {
    "none": 93,
    "entity_drift": 4,
    "wrong_final_answer": 3
  },
  "mini_lats_branching": {
    "none": 95,
    "entity_drift": 2,
    "wrong_final_answer": 3
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding
- mini_lats_branching

## Discussion
Reflexion helps when the first attempt stops after the first hop or drifts to a wrong second-hop entity. The tradeoff is higher attempts, token cost, and latency. In a real report, students should explain when the reflection memory was useful, which failure modes remained, and whether evaluator quality limited gains.
