# IaC の扱い — 検討と設計案

- 日付: 2026-11-27
- 状態: **IaC を対象に含めること、ユニット単位まで v1 に含めること、いずれも
2026-11-27 ユーザー決定**。v1 のユニット対象は §4 の区分どおり。
- 前提: CI 基準に照らすと IaC はど真ん中にある。Terraform の plan/apply、
マニフェストの GitOps 適用、Dockerfile のビルドは CI で回るのが普通であり、
「変更量をリソース単位で把握したい」という需要もコードと同型。

## 1. 他ツールの扱い

行数カウンタ（cloc／tokei 等）は Terraform/HCL・Dockerfile を「言語」として
行数（有効／コメント／空白）だけ数える。宣言ユニット単位の抽出はどのツールもやらない。
→ ユニット単位までやれば本家同様の差別化になるが、v1 の必須条件ではない。

## 2. IaC の内訳と「単位」

IaC は一枚岩ではない。形式ごとに「意味のある単位」と同一性キーが違う。

| 形式 | 検出方法 | 単位 | 同一性キー | 備考 |
|------|----------|------|-----------|------|
| Terraform / OpenTofu (.tf) | 拡張子 | ブロック | ブロック種別＋ラベル（例: `resource aws_instance.web`、`module.vpc`、`variable.image_id`） | HCL パーサ（tree-sitter-hcl / python-hcl2）が要る。コメントは `#` `//` `/* */` |
| Terraform 変数値 (.tfvars) | 拡張子 | なし | — | 値の代入だけ。行数のみ |
| Kubernetes マニフェスト (.yaml) | 内容判定: `apiVersion`＋`kind` を持つ文書 | 文書（リソース） | `apiVersion/kind/namespace/name` | マルチドキュメント（`---` 区切り）が普通。Helm テンプレートは Go テンプレート構文で YAML として壊れる → 行数のみ＋警告 |
| CloudFormation / SAM (.yaml/.json) | 内容判定: `AWSTemplateFormatVersion` または `Resources` に `Type: AWS::` | リソース | 論理 ID（`Resources` 直下のキー） | テンプレート全体は大きいが単位は Resources が中心。Parameters/Outputs は単位にしない |
| GitHub Actions ワークフロー (.yml) | 置き場所: `.github/workflows/` | job | `jobs.<job_id>` | 通常の YAML と置き場所で区別するのが確実。steps は単位にしない（名前が任意で弱い） |
| Dockerfile | ファイル名（Dockerfile / *.dockerfile） | ステージ | `FROM... AS <name>` のステージ名（無名は序数） | 命令単位の同一性は弱い。行数＋ステージ数が現実的。コメントは `#` |
| Ansible (.yml) | 内容判定: play の構造（hosts/tasks）※弱い | play | play の序数＋name（任意） | task の name は任意で同一性が弱い。行数のみが無難 |
| Bicep (.bicep) | 拡張子 | resource／module | シンボリック名（例: `resource stg` の `stg`） | **2026-11-27 ユーザー指示で初期範囲に追加**。リソース型＋API バージョン（`Microsoft.Storage/storageAccounts@2023-01-01`）は変わりやすいのでキーではなく属性として持つ（関数のシグネチャと同じ扱い）。コメントは `//` `/* */`。文法は Azure/bicep 側で保守される tree-sitter 文法がある |
| Pulumi / CDK / CDKTF | — | — | — | Python／TypeScript 等のコードで書くため、コード言語としてそのまま数える。IaC 専用扱いは不要 |

## 3. カテゴリ設計

JSON スキーマに第3のカテゴリを追加する。

- `code`: 関数単位（既存）
- `config`: ファイル単位の行数のみ（決定済み）
- `iac`: ファイル単位の行数＋（対象形式では）宣言ユニット単位

ユニットは関数ではないので `functions` には入れない。汎用の `units` として持つ:

```json
{
"path": "infra/main.tf",
"category": "iac",
"language": "terraform",
"counts": {"total": 210, "effective": 180, "comment": 20, "blank": 10},
"units": [
{
"key": "infra/main.tf::resource.aws_instance.web",
"kind": "resource",
"name": "aws_instance.web",
"start_line": 12, "end_line": 38,
"counts": {"total": 27, "effective": 24, "comment": 2, "blank": 1},
"body_hash": "sha256:…"
}
]
}
```

- 検算ルールは code と同型に保つ: ファイル＝Σユニット＋ユニット外
（`non_unit_counts` を出す。provider ブロックや terraform ブロックの外側、
変数値だけのファイルは全行がユニット外になる）。
- Before/After の対応付けは関数の段階制をそのまま流用できる
（キー完全一致→本体ハッシュによる移動／リネーム検出→残りは追加／削除）。
IaC のユニットキーはコードより安定している（リソース名は状態と結びつくため
安易にリネームされない）ので、むしろコードより誤対応が少ない。
- 値だけが変わったユニット（例: インスタンスタイプの変更）は「変更」として
行差分が出る。値の意味の解釈（破壊的変更かどうか等）は AI 層の仕事で、
カウント層は関与しない（決定的処理の原則どおり）。

## 4. v1 の範囲【2026-11-27 ユーザー決定: ユニット単位まで v1 に含める】

- **行数**: IaC 全形式を v1 から対象にする（config と同じ実装単価）。
- **ユニット単位（v1 に含める）**: Terraform ブロック、Kubernetes 文書、
CloudFormation 論理 ID、GitHub Actions の job、Bicep の resource／module
（2026-11-27 ユーザー指示で Bicep を初期範囲に追加）。
- **行数のみ（v1）**: Dockerfile（ステージは将来候補）、Ansible、
.tfvars 等の値ファイル。
- **判定の注意**: YAML の素性判定（素の YAML か、k8s か、CFn か、Actions か）は
「置き場所 → 内容キーの順」で決定的に行い、判定根拠を `language` と
`language_source`（extension / path / content）として JSON に出す。
判定できない YAML は config に落とす（誤ってユニットをでっち上げない）。

## 5. 決定事項（メモ v0.2 へ移す）

1. IaC を対象に含め、カテゴリ `iac` を新設する【決定済み】
2. v1 のユニット単位は Terraform ブロック／Kubernetes 文書／CFn 論理 ID／
Actions job。Dockerfile と Ansible は行数のみ【決定済み】
3. ユニットは `units` として持ち、検算ルールと対応付けは関数の仕組みを流用する
4. YAML の素性判定は 置き場所→内容 の順で決定的に行い、根拠を JSON に出す
