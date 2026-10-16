# Roadmap

SFTGuard grows through evidence, not feature count.

## v0.1 — correctness and regression gate

- Local JSONL audit with bounded parsing and redacted findings.
- Exact inspection of trusted, exported token-role and loss-mask evidence.
- Base-versus-adapter Regression Cards.
- Deterministic synthetic fault matrix.
- Static report viewer and GitHub Action integration.

## v0.2 — real training integration

- TRL callback for checkpoint-level target and retention evaluation.
- Tested Transformers chat-template mask exporter for compatible templates.
- LLaMA-Factory and Axolotl result importers.
- One small, redistributable real-model benchmark with pinned revisions.

## Research track

- Fault-injection benchmark across multiple trainers and model families.
- False-alarm and fault-detection calibration on independently authored cases.
- Retention-contract design for structured output, multilingual behavior, and
  safety probes.
- Post-merge and post-quantization Regression Cards.

## Deliberately out of scope

- Hosted dataset upload or model training.
- A new LoRA rank allocator or optimizer.
- Predicted final performance without full evaluation.
- Automatic claims that an adapter is safe or production-ready.
