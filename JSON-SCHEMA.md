# JSON スキーマ — 詳細設計案

- 日付: 2026-11-27
- 位置づけ: 設計メモ v0.1 検討メモ（REVIEW-v0.1.md）D 項の詳細版。2026-11-27 にユーザーが「OK」で承認済み。v0.2 では決定事項として 2 章へ移す。
- JSON は AI・機械向けの**主形式**であり、正本（canonical）である。
  Markdown / CSV は同じ内部モデルから生成する派生形式とし、数値は JSON と一致しなければならない。

## 0. 設計原則

1. **合計は検算できる**: summary は details の合計と一致する。AI が自分で集計し直して
   検証できることが、AI 向け形式としての信頼性になる（後述の「関数外」問題を含む）。
2. **決定的な並び**: 配列はパス→キーの辞書順で固定。同じ入力からは（生成時刻を除き）
   同じ内容が出る。差分ツールで JSON 同士を比較してもノイズが出ない。
3. **数値は整数だけ**: ステップ数・差分はすべて整数。確度のような小数も
   整数スコアで表す（浮動小数の表記揺れで再現性を壊さない）。
4. **コードは言語中立、文章は Markdown 側**: change_type や status は英語の enum 値。
   JSON に自然文の説明は入れない（AI が読んで自国語で要約する。文面は陳腐化のもと）。
5. **知らないフィールドは無視できる**: 読む側は未知のフィールドを無視する前提とし、
   追加は互換変更として扱う（版管理ルールと対）。

## 1. 版管理

- トップレベルに `schema_version`（例: `"1.0"`）を必須とする。
- ルール（セマンティックバージョニングに準じる）:
  - **minor 上昇**（1.0 → 1.1）: フィールドの追加など、後方互換のある変更
  - **major 上昇**（1.x → 2.0）: フィールドの削除・改名・意味の変更
- ツールの版は別物として `tool: {name, version}` に出す。
  「スキーマの版」と「ツールの版」を混ぜない。
- リポジトリに JSON Schema（draft 2020-12）ファイルを同梱する
  （`schemas/count.schema.json` / `compare.schema.json`）。
  出力はテストで常にスキーマ検証にかける（ゴールデンファイルと併用）。

## 2. 共通エンベロープ

count / compare 共通の外枠:

```json
{
  "schema_version": "1.0",
  "kind": "count",
  "tool": {"name": "python-sloc-counter", "version": "0.1.0"},
  "status": "ok",
  "run": {
    "target": "src/",
    "options": {"encoding": "auto", "on_error": "strict"},
    "generated_at": "2026-11-27T08:00:00+09:00"
  },
  "summary": {},
  "files": [],
  "errors": [],
  "skipped_binary": []
}
```

- `status` は DECODE-POLICY と一致: `ok` / `partial` / `failed`。終了コードとも対応する。
- `run.options` に効いた設定をそのまま写す（再現の条件を結果自身が語る）。
- `generated_at` はメタデータであり、数値の決定性には関与しない。
  バイト単位の同一性が要る場合は生成時刻を除いて比較する旨を仕様に明記する。

## 3. count の構造

### 3.1 ファイル単位

```json
{
  "path": "src/legacy.py",
  "language": "python",
  "encoding": {
    "encoding": "cp932",
    "source": "heuristic",
    "score": 182,
    "margin": 47,
    "ambiguous": false,
    "newline": "crlf",
    "decode_replaced": false
  },
  "counts": {"total": 120, "effective": 96, "comment": 15, "blank": 9},
  "non_function_counts": {"total": 12, "effective": 10, "comment": 2, "blank": 0},
  "functions": []
}
```

- `encoding` は DECODE-POLICY の判定メタデータをそのまま埋める
  （score / margin は整数。確度を小数で出さないのは原則3による）。
- 行番号・カウントは正規化後（LF 化後）の論理行に基づく。元の文字コード・改行に依存しない。

### 3.2 「関数外」の扱い（検算可能性の要）

ファイルの行数 = 関数内行数の合計、にはならない。import・グローバル定義・
モジュール直下のコードが余る。ここを曖昧にすると summary の検算が合わず、
AI の集計と公式合計が食い違う事故になる。

→ ファイルごとに `non_function_counts` を必ず出し、
**ファイル = Σ関数 + 関数外** が常時成り立つ形にする。クラスについても同様に、
クラス直下（メソッド外）の行はクラスの `non_method_counts` として持つ案を検討する
（v1 はファイル単位までで十分という判断もありうる）。

### 3.3 関数単位

```json
{
  "key": "src/legacy.py::Klass.method#1",
  "qualified_name": "Klass.method",
  "name": "method",
  "kind": "method",
  "container": "Klass",
  "signature": "(self, path, encoding='auto')",
  "start_line": 20,
  "end_line": 45,
  "counts": {"total": 26, "effective": 20, "comment": 4, "blank": 2},
  "body_hash": "sha256:…"
}
```

- `key` は FUNCTION-IDENTITY の同一性キー。`signature` はキーではなく属性。
- `body_hash` は正規化テキストのハッシュ。比較層の同一判定の根拠を count 側からも追える。

## 4. compare の構造

```json
{
  "schema_version": "1.0",
  "kind": "compare",
  "status": "ok",
  "before": {"ref": "folder:old/", "resolved": null},
  "after":  {"ref": "git:main", "resolved": "abc1234…"},
  "summary": {
    "files_added": 1, "files_deleted": 0, "files_modified": 3,
    "files_unchanged": 10, "files_incomplete": 0,
    "functions_added": 2, "functions_deleted": 1,
    "functions_modified": 5, "functions_unchanged": 40,
    "delta": {"total": 35, "effective": 30, "comment": 4, "blank": 1}
  },
  "files": [
    {
      "path": "src/legacy.py",
      "change_type": "modified",
      "incomplete": false,
      "delta": {"total": 6, "effective": 5, "comment": 1, "blank": 0},
      "functions": [
        {
          "before_key": "src/legacy.py::Klass.method#1",
          "after_key": "src/legacy.py::Klass.method#1",
          "change_type": "modified",
          "match_stage": "exact",
          "signature_changed": true,
          "delta": {"total": 6, "effective": 5, "comment": 1, "blank": 0},
          "ambiguous_candidates": []
        }
      ]
    }
  ]
}
```

- `change_type` の enum: ファイル・関数共通で
  `added` / `deleted` / `modified` / `unchanged` / `moved` / `renamed`。
- `match_stage`（exact / signature / moved / renamed）は FUNCTION-IDENTITY の
  対応理由そのもの。「なぜ結ばれたか」を読む側が検証できる。
- Git リファレンスは `resolved` に解決したコミットハッシュを残す
  （`main` のような動く参照だけでは再現できないため）。
- 片側が読めなかったペアは `incomplete: true` とし、関数の増減には数えない
  （DECODE-POLICY 1.4 と一致）。summary の `files_incomplete` にも数える。

## 5. フィールド規約

- 名前は `snake_case` で統一。略語は使わない（`cnt` 等は禁止）。
- 欠損は「フィールドを出さない」ではなく、意味のある場合は `null` か空配列で明示する。
  例: 対応相手がない関数は compare ではなく count 側の形…ではなく、
  compare の関数要素では `before_key: null`（added）/ `after_key: null`（deleted）と明示する。
- 差分（delta）は符号付き整数。before / after の実数も併記する場面では
  `before_counts` / `after_counts` / `delta` の3点セットにする
  （delta だけだと絶対量が分からず、AI の要約が痩せる）。

## 6. テスト

- 全出力が同梱 JSON Schema で検証を通ること（CI 必須）。
- ゴールデンファイル: 既知サンプルの count 出力 JSON を期待値として固定し、
  意図しないスキーマ／数値変更を検出する。
- 検算テスト: summary = Σfiles、file = Σfunctions + non_function、を
  プロパティテストとして常時確認する。

## 7. 決定事項としてメモ v0.2 に入れる候補

1. JSON を正本とし、`schema_version` 必須。追加 = minor、削除・改名・意味変更 = major
2. JSON Schema ファイルをリポジトリに同梱し、出力を常時検証する
3. 数値は整数のみ、確度は整数スコアで表す
4. `non_function_counts` を必ず出し、合計の検算が常時成り立つ形にする
5. 配列の並びは辞書順で固定。enum は言語中立な英語コード、自然文は入れない
6. compare では before/after 実数 + delta の3点セット、match_stage と
   resolved コミットを必ず出す

## 8. CSV 出力

本家かぞえチャオ！と同様に、ファイル名・カウント結果・行数を CSV で出す。
CSV は JSON と同じ内部モデルから生成する派生形式（数値の一致が必須）だが、
「Excel で開いてそのまま集計・報告に使える」ことを CSV 側の第一用途とする。

- **形式はロング形式（1行＝1対象）**: ファイル行と、その配下の関数／ユニット行を
同じ表に混ぜ、`kind` 列で区別する。本家のように「ファイル→モジュール」の
階層を1枚の表で見る使い方に合わせる。
- **count の列**:
`category, language, path, kind, key, name, total_lines, effective_lines, comment_lines, blank_lines`
- `kind` は `file` / `function` / `unit` / `non_function`（関数外・ユニット外の行も
1行として出す。検算が CSV だけでも成り立つようにするため）
- ファイル行は `key` が空、`name` はファイル名
- **compare の列**: count の列に加えて
`status, match_stage, before_total, before_effective, after_total, after_effective, delta_total, delta_effective, lines_added, lines_deleted, lines_unchanged`
を持つ（status は added／deleted／modified／unchanged／moved／renamed）
- **文字コードは UTF-8（BOM 付き）を既定**とし、`--csv-encoding utf-8` で
BOM なしに切り替えられる。BOM 付きは日本の Excel で文字化けしないための配慮で、
本家の Shift_JIS 前提を現代化したもの。Shift_JIS 出力はしない
（対象ファイル名に CP932 外の文字があり得るため、欠落の危険がある）
- 並びは JSON と同じ辞書順（パス→キー）。ヘッダ行は英語（JSON のフィールド名と一致）

## 9. compare の行レベル内訳

本家の比較結果は「前後のステップ数と差」だけでなく、対応付いたモジュールの中で
行がどう動いたか（本家の新規／流用／修正の見方）まで数えていた。本プロジェクトでも
delta（差し引き）だけでは「+3」が「+3/-0」なのか「+10/-7」なのか区別できないため、
対応付いたペア（関数／ユニット／ファイル）には行レベルの内訳を持たせる。

- `lines_added`: After にだけある行数（正規化テキスト同士の行 diff による）
- `lines_deleted`: Before にだけある行数
- `lines_unchanged`: 両方にある行数（本家の「流用」に相当する見方ができる）
- 検算: ペアについては `before_effective = lines_unchanged + lines_deleted`、
`after_effective = lines_unchanged + lines_added` が成り立つ形にする
（行の分類は有効行ベース。total ベースの内訳は持たない）
- 追加のみ／削除のみの対象は内訳を持たず、before/after の片側が 0 になる
（status で区別できるため）
- 行 diff の同一行判定は正規化済みテキスト（デコード→LF化→行末空白除去）で行い、
文字コードや改行だけの違いは差分として数えない（不変条件と整合）
