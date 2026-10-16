# Related work and project boundary

This comparison defines SFTGuard's scope; it is not an exhaustive novelty
search. SFTGuard is a local correctness and regression gate around a fine-tuning
pipeline. It does not replace trainers, parameter-efficient tuning methods,
data-selection research, or general model benchmarks.

## Training frameworks

[TRL](https://github.com/huggingface/trl) provides post-training algorithms and
trainers, including supervised fine-tuning. Its official
[SFTTrainer documentation](https://huggingface.co/docs/trl/main/en/sft_trainer)
defines dataset formats, chat-template application, token-level loss, and
assistant/completion masking. SFTGuard inspects evidence about those semantics;
it does not implement or accelerate the training loop.

[LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) and
[Axolotl](https://github.com/axolotl-ai-cloud/axolotl) are configurable
fine-tuning systems spanning model loading, dataset preparation, distributed
training, parameter-efficient methods, and evaluation integrations. SFTGuard is
designed to sit beside such a system: it can audit exported local records and
gate supplied base-versus-adapter results, but it does not launch their jobs or
claim configuration parity with them.

## Parameter-efficient fine-tuning

[PEFT](https://github.com/huggingface/peft) implements LoRA and other
parameter-efficient methods. Its
[LoRA API](https://huggingface.co/docs/peft/main/en/package_reference/lora)
supports target modules, per-module rank and alpha patterns, multiple
initialization methods, quantization-aware workflows, and automatic target
selection. SFTGuard does not propose a new adapter, choose an optimal rank, or
allocate modules. It checks pipeline correctness and evaluates an explicit
release contract for an adapter that another tool produced.

## Prediction and experiment screening

[TuneAhead](https://arxiv.org/abs/2606.17660) predicts full fine-tuning
performance using static dataset descriptors and features from a short probe
run. SFTGuard deliberately makes a different claim: it does not estimate a
future score. It verifies bounded, observable properties and returns `ABSTAIN`
when the evidence required for a gate is missing.

## Data selection and processing

[LESS](https://github.com/princeton-nlp/LESS) selects influential examples for
targeted instruction tuning using optimizer-aware low-rank gradient features.
[DataInf](https://github.com/ykwon0407/DataInf) estimates data influence for
LoRA-tuned language and diffusion models. These methods rank training examples
by estimated utility. SFTGuard does not rank examples or assert that a dataset
is high quality; its data checks target deterministic conditions such as schema
errors, exact duplication, conflicting answers, split leakage, and bounded
privacy signals.

[Data-Juicer](https://github.com/datajuicer/data-juicer) is a broad data
processing system with filtering, analysis, transformation, and distributed
execution operators for foundation-model data. SFTGuard is narrower: it uses a
small frozen audit contract and emits a release decision artifact. It is not a
general cleaning or data-transformation pipeline.

## Evaluation and forgetting

[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
runs a large catalog of language-model evaluations.
[TRACE](https://github.com/BeyonderXX/TRACE), introduced in the
[TRACE paper](https://arxiv.org/abs/2310.06762), benchmarks continual learning
across multiple tasks and measures degradation in general and
instruction-following abilities. SFTGuard does not reproduce those benchmark
suites. It consumes paired evaluation records chosen by the user and applies
explicit target and retention budgets; the resulting Regression Card is valid
only for that supplied contract.

## Practical distinction

SFTGuard's intended contribution is the integration of four conservative
software checks: exact training-data semantics where they can be verified,
deterministic fault findings, paired regression budgets, and shareable
content-addressed provenance. Existing projects above can provide the trainer,
adapter, data pipeline, selector, or benchmark. SFTGuard records whether a
specific proposed release met its declared evidence gates, without converting
missing evidence into success or claiming that the release is safe in general.
