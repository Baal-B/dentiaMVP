### FINAL (adjudicated labels): 43 articles, 17 relevant (40 %)

| Strategy | Notified | Precision | Recall | F1 |
|---|---|---|---|---|
| Like scrape.py (notify everything found) | 43 | 0.40 | 1.00 | 0.57 |
| Regex rule only (no model) | 39 | 0.44 | 1.00 | 0.61 |
| Agent (LLM qwen2.5:3b + rule) | 34 | 0.50 | 1.00 | 0.67 |

### Labeller 1: 43 articles, 10 relevant (23 %)

| Strategy | Notified | Precision | Recall | F1 |
|---|---|---|---|---|
| Like scrape.py (notify everything found) | 43 | 0.23 | 1.00 | 0.38 |
| Regex rule only (no model) | 39 | 0.26 | 1.00 | 0.41 |
| Agent (LLM qwen2.5:3b + rule) | 34 | 0.29 | 1.00 | 0.45 |

### Labeller 2: 43 articles, 17 relevant (40 %)

| Strategy | Notified | Precision | Recall | F1 |
|---|---|---|---|---|
| Like scrape.py (notify everything found) | 43 | 0.40 | 1.00 | 0.57 |
| Regex rule only (no model) | 39 | 0.44 | 1.00 | 0.61 |
| Agent (LLM qwen2.5:3b + rule) | 34 | 0.50 | 1.00 | 0.67 |

### Consensus (both labellers agree): 36 articles, 10 relevant (28 %)

| Strategy | Notified | Precision | Recall | F1 |
|---|---|---|---|---|
| Like scrape.py (notify everything found) | 36 | 0.28 | 1.00 | 0.43 |
| Regex rule only (no model) | 32 | 0.31 | 1.00 | 0.48 |
| Agent (LLM qwen2.5:3b + rule) | 27 | 0.37 | 1.00 | 0.54 |

