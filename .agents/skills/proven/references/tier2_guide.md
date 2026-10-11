# Proven Tier 2 Intelligence Guide: HGT Blast Radius & Triage

This reference guide provides in-depth technical details on Proven's **Tier 2 (Graph AI Core)** capabilities for Coding Agents.

---

## 1. What is Tier 2 Intelligence?

While Tier 1 operates strictly on deterministic AST analysis and dynamic runtime coverage tracing (zero training required), **Tier 2** leverages an offline **Heterogeneous Graph Transformer (HGT)** deep learning model to uncover hidden relationships across the codebase.

```
AST & Direct Tracing (Tier 1)      HGT Graph Embeddings (Tier 2)
────────────────────────────      ────────────────────────────
A calls B directly                A and C share semantic embedding space
A imports module M                A and C frequently co-change in Git commits
Deterministic & Instant           Predicts Latent (Hidden) Regression Risks
```

---

## 2. Latent Blast Radius Prediction (`query_impact.py`)

When modifying a core component (e.g. authentication, database pool, pricing logic), static AST only reveals direct callers. Tier 2 uncovers remote components that have high **latent risk**.

### Invocation:
```bash
python skills/proven/scripts/query_impact.py \
  --target "FUNC:my_module.core_func" \
  --mode hybrid
```

### Analysis Modes:
- `hybrid` (Default): Combines structural AST graph traversal with GNN cosine embedding similarity.
- `graph`: Pure topological graph traversal (direct callers, callees, definitions).
- `gnn`: Pure GNN embedding similarity ranking.

### Understanding the JSON Output:
```json
{
  "status": "success",
  "target": "FUNC:auth.verify_token",
  "direct_impact_count": 2,
  "direct_dependents": [
    {
      "symbol": "FUNC:api.routes.login",
      "type": "Function",
      "score": 0.85,
      "relation": "direct caller",
      "path": "api/routes.py -> calls -> FUNC:auth.verify_token"
    }
  ],
  "latent_risk_candidates": [
    {
      "symbol": "FILE:services/billing_webhook.py",
      "type": "File",
      "score": 0.76,
      "gnn_score": 0.92,
      "relation": "git co-change, Latent GNN Correlation",
      "path": "auth.py <- co-change x8 -> billing_webhook.py"
    }
  ]
}
```

### Agent Action Strategy:
1. **Target Tests**: Write behavioral unit tests for the modified target function.
2. **Direct Tests**: Ensure callers in `direct_dependents` are covered.
3. **Regression Tests**: If any `latent_risk_candidates` have `score > 0.70`, write integration/regression tests for those remote files to prevent hidden regressions!

---

## 3. Semantic Bug Triage & Reviewer Recommendation (`triage_expert.py`)

When resolving an issue or preparing a Pull Request, use Tier 2 to identify the most authoritative code owners and related files based on the bug description or PR change summary.

### Invocation:
```bash
python skills/proven/scripts/triage_expert.py \
  --query "Database connection timeout under heavy concurrent traffic" \
  --max-devs 3 \
  --max-files 5
```

### Scoring Formula:
The hybrid triage score combines three signals:
$$\text{Final Score} = (0.45 \times \text{GNN Score}) + (0.35 \times \text{Git Ownership}) + (0.20 \times \text{Semantic File Score})$$

### Understanding the JSON Output:
```json
{
  "status": "success",
  "query": "Database connection timeout under heavy concurrent traffic",
  "top_engineers": [
    {
      "rank": 1,
      "developer": "minhquang0407",
      "final_score": 0.892,
      "gnn_score": 0.951,
      "git_score": 0.880,
      "sem_score": 0.800,
      "evidence": "Direct: db/connection_pool.py (14)"
    }
  ],
  "related_files": [
    {
      "rank": 1,
      "file": "db/connection_pool.py",
      "relevance": 0.942,
      "semantic_score": 0.950,
      "lexical_score": 0.920
    }
  ]
}
```

### Agent Action Strategy:
- **PR Reviewers**: Automatically suggest tagging the top-ranked developer in the PR summary (e.g. `CC @minhquang0407`).
- **File Checklist**: Verify that all files listed in `related_files` were reviewed during bug resolution.

---

## 4. Offline HGT Graph AI Training (`train_gnn.py`)

HGT does not need to be retrained for routine commits or PRs. Retrain only when:
1. Onboarding a new repository.
2. After massive architectural refactoring (50+ files modified).
3. The user explicitly requests model re-training.

### Invocation:
```bash
python skills/proven/scripts/train_gnn.py
```

### Prerequisites:
Requires PyTorch Geometric installed (`pip install proven[gnn]`).
Training runs full-batch link prediction on CPU or GPU and typically completes in 15–45 seconds.
