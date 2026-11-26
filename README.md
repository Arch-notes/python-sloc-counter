# kazoe

CI-oriented step counter — a Python reimplementation of Kazoe Chao!
(かぞえチャオ！), extended for modern repositories.

- Function-level counts for Python, JavaScript/TypeScript and SQL
  stored procedures; declarative units for Terraform, Kubernetes,
  CloudFormation, GitHub Actions, Bicep and SQL DDL
- Line counts for config formats (YAML/TOML/JSON/XML/INI/...) and Markdown
- Legacy Japanese encodings (CP932 / EUC-JP / ISO-2022-JP / UTF-16) are
  normalized before counting, so the same logical text counts the same
  regardless of encoding or line endings
- Before/after comparison at file, function and unit level, from folders
  or from git refs, with added/deleted/unchanged line breakdowns
- JSON is the canonical output; CSV (UTF-8 with BOM) and Markdown are
  derived from it. Exit codes: 0 ok, 1 fatal, 2 partial failure

## Usage

```console
kazoe count <path> [--format json|csv|md]
kazoe compare <before> <after> [--format json|csv|md]
kazoe git-compare <repo> <ref-before> <ref-after>
```

Options: `--encoding` to force an encoding, `--on-error strict|abort|replace`
for undecodable files, `--strict-detection` to fail on ambiguous encoding
detection.

## Docker

```console
docker build -t kazoe .
docker run --rm -v "$PWD:/work" kazoe count . --format md
```

Design documents (Japanese) live next to the source: V1-SCOPE.md,
FUNCTION-IDENTITY.md, DECODE-POLICY.md, JSON-SCHEMA.md, IAC.md,
LANGUAGES-AND-OPEN-ITEMS.md, IMPLEMENTATION.md.
