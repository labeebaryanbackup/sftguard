# Share copy

These drafts describe the checked-in v0.1 result without calling it a
breakthrough, benchmark win, or safety certification. Check each community's
current self-promotion rules before posting and do not mass-post identical copy.

## Reddit

**Title**

> I built SFTGuard: a fail-closed preflight and regression gate for supervised fine-tuning

**Body**

> I kept seeing fine-tuning checks discussed separately, so I built a small
> local tool that turns the deterministic ones into a release gate.
>
> SFTGuard audits chat JSONL plus exported token/loss-mask evidence for schema,
> role order, exact duplicates, conflicting answers, train/eval leakage,
> credential-shaped text, EOS handling, prompt supervision, and destructive
> truncation. It also compares paired base-vs-adapter metrics against explicit
> target and retention budgets. Missing evidence returns ABSTAIN instead of
> silently passing.
>
> I preregistered the synthetic fault protocol before running its confirmatory
> seeds. On the frozen internal matrix it detected 270/270 injected faults, had
> 0/30 clean-control false positives, and reproduced the artifact byte-for-byte
> from the recorded implementation commit.
>
> Important limitation: this is internal regression evidence using one
> structural template per known fault class—not an external benchmark, model
> quality result, or proof that it catches unknown failures.
>
> I would especially value technical feedback on the exported mask-evidence
> contract and the paired retention gate.
>
> Repo: https://github.com/Labeeb2339/sftguard
>
> Static viewer: https://labeeb2339.github.io/sftguard/

## Discord

> I built **SFTGuard**, a local fail-closed preflight + regression gate for SFT
> pipelines. It checks chat data and exported loss-mask evidence, then gates
> paired base-vs-adapter target/retention metrics with PASS / FAIL / ABSTAIN.
>
> Frozen synthetic result: 270/270 known fault injections detected, 0/30 clean
> controls flagged, exact implementation replay matched. This is internal
> detector regression evidence, not an external benchmark or safety claim.
>
> Feedback on the mask-evidence format and regression contract would help:
> https://github.com/Labeeb2339/sftguard

## Optional author line

Use this only if you want to identify yourself as a student; otherwise omit it:

> I’m a student learning how to make AI tooling claims reproducible instead of
> relying on demos alone.

## Before posting

- Open the public repo and Pages link in a signed-out window.
- Use only [`docs/assets/sftguard-confirmatory-dashboard.png`](assets/sftguard-confirmatory-dashboard.png);
  do not capture private tabs,
  local file paths, Discord messages, tokens, or notifications.
- Keep the limitation paragraph intact.
- Ask for specific technical feedback; do not trade stars, spam, or imply that
  stars validate the research claim.
- If a community bans project promotion, do not post there.
