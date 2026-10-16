# Security policy

## Supported versions

Security fixes are applied to the latest released version and the `main` branch.
Pre-release branches may change without a compatibility guarantee.

## Report a vulnerability privately

Do not open a public issue for a vulnerability, exposed credential, private
dataset, or personally identifying record. Use GitHub's
[private vulnerability reporting](https://github.com/Labeeb2339/sftguard/security/advisories/new)
for this repository. Include only the minimum synthetic information needed to
reproduce the problem.

If a credential has already been exposed, revoke or rotate it with its provider
before changing local files. Do not paste the credential into a report, commit,
chat, screenshot, or Regression Card. Rewriting Git history is a separate,
potentially disruptive action and should be planned only after rotation and
current-file redaction.

Please allow the maintainer a reasonable period to reproduce and address a
report before public disclosure. There is no guaranteed response or remediation
time. Good-faith reports that avoid privacy violations and service disruption
are welcome.

## Local-data privacy boundary

SFTGuard is designed for local analysis. The command-line tool must not upload
datasets, prompts, responses, model weights, or generated reports. Its public
static viewer has no report-upload endpoint, analytics, or server-side report
processing; a report selected in the viewer remains in that browser context.

Generated artifacts are intended to contain aggregates, configuration,
content-addressing information, and bounded findings rather than raw dataset
text. This is a design boundary, not a guarantee that every user-supplied file
is safe to publish. Before sharing any artifact, follow
[docs/SHARING.md](docs/SHARING.md). Treat hashes as stable identifiers that can
still reveal equality or permit guessing when the underlying data is simple.

When reporting a suspected privacy failure:

- name the affected command, version, and output field;
- describe the data category, not the sensitive value;
- use synthetic reproduction data whenever possible;
- remove local usernames, absolute paths, access tokens, and model credentials;
- do not attach the original dataset or an unsanitized report.

## Security scope

Reports about unsafe parsing, path traversal, command construction, secret or
raw-text leakage, unbounded resource use, cross-site scripting in the viewer,
and dependency compromise are in scope. A `PASS` Regression Card is not a
safety certification and does not show that a model, adapter, or dataset is
secure.
