# Sharing SFTGuard results safely

SFTGuard is local-first. It does not automatically post, upload, or publish a
dataset, Regression Card, screenshot, or result. Sharing is a separate decision
made by the person who controls the underlying data.

## Usually appropriate to share

After inspection, these fields are generally intended for reproducibility:

- SFTGuard version and implementation commit;
- protocol version, configuration, and frozen thresholds;
- aggregate finding counts and `PASS`, `FAIL`, or `ABSTAIN` status;
- synthetic benchmark seeds and synthetic evidence hashes;
- Python, Node.js, operating-system, and dependency versions;
- evaluation metric names, pair counts, and aggregate intervals when the
  evaluation contract permits disclosure.

Hashes are identifiers, not anonymization. A dataset or row hash can reveal
that two parties used the same content and may be guessable for short or common
records. Do not publish a hash when even dataset identity or equality is
sensitive.

## Do not share

- raw prompts, responses, system messages, labels, or private evaluation data;
- credentials, tokens, cookies, private keys, connection strings, or `.env`
  files;
- names, contact details, health, school, financial, or other identifying data;
- absolute local paths that reveal usernames or private project names;
- proprietary model weights, adapter files, or licensed data without
  permission;
- an unsanitized report, terminal log, screenshot, issue attachment, or browser
  export.

Finding locations should use bounded record indexes and field categories, not
the sensitive value itself. A secret-pattern finding should say where and what
category was detected without copying the candidate secret.

## Pre-publication checklist

1. Work from a copy of the intended artifact; keep the original private.
2. Validate the card schema and canonical hash.
3. Search the copy for raw prompt/response fields, credentials, local paths,
   emails, phone numbers, and other identifiers.
4. Confirm that no data sample was embedded in metadata, error text, or a
   screenshot.
5. Check the dataset and model licenses and any competition or institutional
   disclosure rules.
6. State the exact evidence boundary. A synthetic pass is not a safety
   certification or a claim about unknown faults.
7. When uncertain, share only the aggregate conclusion and reproduction code,
   or do not publish the artifact.

## Browser viewer and GitHub Pages

The public Pages site contains only static application assets from `web/dist`.
Selecting a local report reads it into the current browser; the project has no
report upload endpoint or analytics. Browser extensions, modified builds, and
the surrounding device are outside SFTGuard's control, so sensitive reports
should still be opened only in a trusted local environment.

Never commit a real Regression Card merely to view it on Pages. Use synthetic
fixtures for documentation, tests, issues, and demonstrations.

## Security reports and support requests

Use synthetic reproduction data in public issues. For suspected leakage or
another vulnerability, follow [SECURITY.md](../SECURITY.md) and report it
privately. Rotate an exposed credential before discussing code remediation, and
never include the credential value in the report.
