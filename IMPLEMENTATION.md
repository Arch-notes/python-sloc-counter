# 実装状況

- 開始: 2026-11-27（設計文書群と同じフォルダがプロジェクトルート）
- 現在: 第1増分が動作し、テスト 7 件が通っている

## 実装済み

- 正規化層（python_sloc_counter/normalize.py）: BOM（UTF-8／UTF-16）、ISO-2022-JP の
  エスケープ検出、UTF-8／CP932／EUC-JP の strict 試行＋日本語らしさスコア、
  ambiguous_encoding 警告、バイナリ判定（先頭 8KB の NUL。UTF-16 は除外）、
  改行は CR／LF／CRLF のみで分割
- カウント層:
  - Python: ast による関数／メソッド／property 抽出。行は最内側の関数へ
    帰属させる分割方式で「ファイル＝Σ関数＋関数外」を常時成立させる。
    docstring はコメント行。ラムダは独立カウントしない
  - 行数カテゴリ: config（YAML／TOML／JSON／XML／INI／properties／.env／conf／HTML）、
    docs（Markdown）、Dockerfile、.tfvars 等
  - IaC ユニット: Terraform／Bicep は正規表現＋波括弧マッチング、
    Kubernetes／CloudFormation／GitHub Actions は PyYAML のノード位置情報で抽出
- 比較層: 段階制マッチング（完全一致→シグネチャ変化→本体ハッシュで
  moved／renamed）、行レベル内訳（lines_added／deleted／unchanged）
- 出力: JSON（正本）、CSV（ロング形式、UTF-8 BOM 付き）、Markdown
- CLI: `python-sloc-counter count <path>` / `python-sloc-counter compare <before> <after>`、
  終了コード 0／1／2
- テスト（unittest、依存は PyYAML のみ）:
  文字コード5種×改行3種のマトリクスでカウント一致と相互比較ゼロ、
  Python の検算、比較の行内訳、Terraform／Kubernetes ユニット、CSV／JSON 出力

## 実装済み（追加分、2026-11-27 優先度順に1機能ずつ対応）

- 優先度1: JavaScript／TypeScript（tree-sitter）。関数宣言・メソッド・
  getter/setter に加え、「代入で名前を得る関数」を代入先名でキーにする
  （React コンポーネント、ネストしたイベントハンドラ等）。TSX/JSX 対応
- 優先度2: SQL。CREATE 文を正規表現＋BEGIN..END の深さ追跡で切り出し、
  PROCEDURE／FUNCTION は functions、TABLE／VIEW／INDEX／TRIGGER 等の
  DDL は units。方言は区別しない

## 実装済み（追加分2、2026-11-27）

- 優先度3: Git リファレンス比較。`python-sloc-counter git-compare <repo> <ref> <ref>`。
  ref をコミットへ解決し `git archive` で展開してフォルダ比較にかける。
  解決済みコミットハッシュを出力の `resolved` に必ず入れる
- 優先度4: JSON Schema を `schemas/` に同梱（count／compare）。
  テストで出力を常時検証する（jsonschema は dev 依存）
- 優先度5: `--on-error strict|abort|replace`（replace は置換箇所数と
  行番号を警告に出し、対象ファイルは行数のみ数える）と
  `--strict-detection`（曖昧な文字コード判定をエラーにする）
- 優先度6: Dockerfile と README を用意。ただしこの VM には Docker が
  無いためイメージビルド自体は未検証。代わりにクリーンな venv への
  `pip install .` とインストール済み `python-sloc-counter` の実行は検証済み

## 完了（2026-11-27）

- ゴールデンファイルによる出力固定（tests/golden、UPDATE_GOLDEN で再生成）
- N1: クラス単位の集計（classes[]、non_method_counts）
- N3: 行分類の言語別定義（LINE-CLASSIFICATION.md）
- 名称: 当初案 `kazoe` は原典由来のためユーザーが却下し、
  `python-sloc-counter`（パッケージ python_sloc_counter、コマンド
  python-sloc-counter）で確定
- 公開: https://github.com/Arch-notes/python-sloc-counter（Public、MIT）。
  初回 push は gh の OAuth に workflow スコープが無く workflow ファイルが
  弾かれたため、専用 Deploy Key（SSH エイリアス github-sloc）で push。
  GitHub Actions の CI（unittest＋ドッグフーディング）は成功を確認

## 既知の割り切り

- 行分類は文字列リテラル内を構文解析しない（古典的カウンタと同じ方式）。
  コメント記号を含む文字列がある言語では誤分類があり得る
- Python で構文エラーのファイルは警告付きで行数だけ数える（隔離はしない）
