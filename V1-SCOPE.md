# v1 の範囲（スコープ）

- 日付: 2026-11-27
- 位置づけ: これまでの決定（設計の穴 A〜D、言語、HTML、config、IaC、Markdown、SQL）を
  v1 の範囲として一枚に集約したもの。詳細は各設計文書を参照。

## 1. カテゴリと対象

### code（関数単位）
| 言語 | 単位 | 備考 |
|------|------|------|
| Python | 関数／メソッド | 標準 `ast`。同一性は FUNCTION-IDENTITY.md |
| JavaScript／TypeScript | 関数／メソッド | tree-sitter。「代入で名前を得る関数」は代入先名がキー（React コンポーネント含む）。JSX/TSX はファイル単位でこの言語として数える |
| SQL | ストアドプロシージャ／関数は `functions`、DDL オブジェクトは `units` | 方言は区別しない（汎用 SQL）。DML／SELECT スクリプトは単位にしない |

### iac（行数＋ユニット単位）
| 形式 | 単位 | 備考 |
|------|------|------|
| Terraform／OpenTofu (.tf) | ブロック（種別＋ラベル） | .tfvars は行数のみ |
| Kubernetes マニフェスト | 文書（apiVersion/kind/namespace/name） | Helm テンプレートは行数のみ＋警告 |
| CloudFormation／SAM | Resources の論理 ID | |
| GitHub Actions | job（`jobs.<job_id>`） | 置き場所 `.github/workflows/` で判定 |
| Bicep | resource／module（シンボリック名） | 型＋API バージョンは属性 |
| Dockerfile | 行数のみ | ステージ単位は将来候補 |
| Ansible | 行数のみ | |

### config（行数のみ）
YAML、TOML、JSON、XML、INI、properties、.env、各種 .conf。
HTML はファイル単位方式でこの枠（行数のみ、埋め込みスクリプトは切り出さない）。

### docs（行数のみ）
Markdown。見出しセクション単位は将来候補。

## 2. 核の機能（全カテゴリ共通）

- 正規化層: 文字コード判定・デコード（CP932／EUC-JP／ISO-2022-JP／UTF-8／UTF-16、
  CR のみ改行を含む全範囲）→ Unicode＋LF 化。失敗時の方針は DECODE-POLICY.md
  （ファイル単位の隔離、終了コード 0／1／2、判定メタデータと警告を常時出す）
- 比較層: Before/After の対応付けは段階制（完全一致→シグネチャ変化→
  本体ハッシュによる移動／リネーム検出→追加／削除）。あいまいな候補は結ばず出す
- 出力層: JSON が正本（JSON Schema 同梱で常時検証）、Markdown と CSV は派生。
  検算ルール（ファイル＝Σ単位＋単位外）を常時成立させる。
  CSV は本家と同じくファイル名・カウント結果・行数を出す（ロング形式、
  UTF-8 BOM 付き既定。詳細は JSON-SCHEMA.md 8章）
- 実行形態: CLI、OS 非依存、Docker 配布。終了コードで失敗を CI に伝える

## 3. v1 に入らないもの

- コード言語の追加分: C、C++、Java、C#、Go、Rust（後続追加。優先順は候補表どおり）
- 除外が決定済み: VB、R、MASM
- 分類の「流用」（類似度マッチングは v2）
- 静的解析連携（SARIF 等）、キーワードカウント、MCP サーバ化
- HTML 埋め込みスクリプトの分離（後付けオプション）
- Dockerfile ステージ単位、Markdown 見出しセクション単位（将来候補）
- GUI、外部エディタ起動、言語定義の手作りファイル、自動実行ファイル独自形式、
  独自 HTML／TEXT 出力（いずれも「不要」で推奨提示済み、正式追認は未決定側に残る）

## 4. v1 の範囲に影響する未決定（残り）

- Before/After の主経路（推奨: フォルダ比較が本体、Git はアダプタで両対応）
- 分類の確定（推奨: 追加／削除／変更／無変更＋移動／リネームまでを v1）
- プロジェクト名は `python-sloc-counter`（コマンド名も同じ。当初案 `kazoe` は原典由来のため不採用）。リポジトリは **Arch-notes
  （ITアーキテクト）で公開する方針が決定（2026-11-27 ユーザー）**。
  ただし **v1 が完全にできるまで push しない**（同日ユーザー指示）。
  作成と公開は完成後
- N1: クラス直下のメソッド外カウントの持ち方
- N2: `--strict-detection` の要否と閾値
- N3: 行分類の言語別定義（Python の docstring 等）
- プリプロセッサ区別は C を入れる時点で再検討（v1 の範囲外で保留可）
