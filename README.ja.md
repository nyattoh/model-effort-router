# model-effort-router

[English](README.md) | 日本語

「model-effort-router」は、入力された依頼から候補となるタスクDAGを選び、
各タスクへ利用可能な(model, effort)の組み合わせを割り当てます。
Python 3.11+、標準ライブラリのみで動作するライブラリ／CLIです。

このルーターは、どのAIオーケストレーターからも利用できるように、
モデル一覧、effort値、能力、タスク要件、実行層を呼び出し側から受け取ります。
ルーター自身は計画を選択するだけで、モデルプロバイダーを呼び出したり、
タスクを実行したりしません。

## 状態と範囲

- **Alpha:** 入出力契約は小さく、1.0までに変更される可能性があります。
- **ベンチマーク非掲載:** JevまたはTypeSafeの性能比較・ベンチマークは公開しません。
- **TypeSafe連携は非公式:** TypeSafeとの提携、承認、サポートを意味しません。
- Choice応答形式は
  [TypeSafe公式Choice仕様](https://docs.typesafe.ai/primitives/choice)に基づきます。
  公開された合成データでライブ互換性を検証済みですが、実際のホストdispatchと
  プロバイダー能力の検出は呼び出し側の責務です。

## 入力契約

CLIへJSONを渡します。

~~~
{
  "request": "サービスへ監査ログを追加する",
  "constraints": {
    "language": "Python",
    "public_api": "stable"
  },
  "candidates": [
    {
      "id": "small-change",
      "description": "分離された変更を実装してテストする",
      "tasks": [
        {
          "id": "implement",
          "description": "監査ログを実装する",
          "depends_on": [],
          "requirements": ["python"],
          "allowed_pairs": [
            {"model": "gpt-5.6-terra", "effort": "high"}
          ]
        }
      ]
    }
  ],
  "models": [
    {
      "id": "gpt-5.6-terra",
      "provider": "openai",
      "efforts": ["low", "medium", "high"],
      "capabilities": ["python"],
      "description": "一般的な実装モデル"
    }
  ],
  "max_parallel": 1
}
~~~

constraints、タスクのrequirementsとallowed_pairs、モデルのcapabilitiesと
descriptionは省略できます。constraintsはJSONオブジェクトです。
候補内のタスクはdepends_onによるDAGを構成し、依存先は同じ候補内のタスクIDで
指定します。allowed_pairsは{ "model": "...", "effort": "..." }形式です。

~~~powershell
python -m pip install -e .
python -m model_effort_router examples/request.json
~~~

ルーターは次の2段階で選択します。

1. 分解候補を選択する
2. 選択した候補の各タスクへ、許可されたmodel／effortを割り当てる

返されるJSONは外部スケジューラーに渡せます。depends_onとmax_parallelの
強制、および実際のタスク実行はスケジューラーが担当します。

## Portable agent skill

プロバイダーに依存しないスキルは
[skill/model-effort-router/SKILL.md](skill/model-effort-router/SKILL.md)にあります。
エージェントホストから直接読み込むか、skill/model-effort-routerディレクトリ全体を
ホストのスキルディレクトリへコピーしてください。references/とexamples/への
相対リンクを保つため、ディレクトリ構造は維持してください。

Codex、Claude、Gemini、汎用オーケストレーター向けの対応例は
[references/adapters.md](skill/model-effort-router/references/adapters.md)に分離しています。
中核ワークフローとJSON契約は特定プロバイダーに依存しません。

## トークン削減の測定

再現可能なfixtureで、workerごとの2種類のpayload方針を比較します。
benchmark用の依存を導入して、保存済み結果を再生成できます。

~~~powershell
python -m pip install -e ".[benchmark]"
python scripts/measure_token_reduction.py examples/request.json --json-out docs/token-reduction-results.json --svg-out docs/token-reduction.svg
~~~

![推定dispatch contextトークン削減](docs/token-reduction.svg)

OpenAI tiktoken 0.12.0の参照encodingによる測定結果です。

- cl100k_base: **1,277から295トークン（76.90%削減）**
- o200k_base: **1,326から300トークン（77.38%削減）**

baselineは全request、全候補、全model定義を各workerへ繰り返します。handoff側は
request、制約、選択タスク、選択assignmentだけを渡します。system prompt、tool
schema、provider wrapper、実行結果、retry、cache効果は含みません。したがって、
これはpayload simulationであり、実セッション使用量、課金、品質、latency、
モデル性能の主張ではありません。詳細は
[tiktoken](https://github.com/openai/tiktoken)と
[測定結果JSON](docs/token-reduction-results.json)を参照してください。

## Checkpoint gate

workerは、依存タスクを解放する前や外部作用の前に、証拠付きのcheckpointを
提出できます。routerはJevへ次のアクションとリスク分類を尋ね、両方がconfidence
policyを通過した場合だけ続行を許可します。それ以外はhuman_reviewです。

~~~powershell
python -m model_effort_router examples/checkpoint.json --checkpoint --dry-run
~~~

統合ホストではPython APIのreview_checkpointを使えます。checkpointには証拠と
不確実性を含めますが、Chain-of-thoughtは含めません。

## APIキー設定

Jev-backed modeのcredential contractは環境変数TYPESAFE_API_KEYだけです。
library、skill、pluginはキーを保存・表示しません。

現在のprocessからキーが見えているか、値を表示せず確認できます。

~~~powershell
python -m model_effort_router --check-api-key
~~~

PowerShellで一時的に設定する場合:

~~~powershell
$jevApiKey = Read-Host "TypeSafe API key" -MaskInput
try {
  $env:TYPESAFE_API_KEY = $jevApiKey
  python -m model_effort_router examples/request.json
} finally {
  Remove-Item Env:\TYPESAFE_API_KEY -ErrorAction SilentlyContinue
  $jevApiKey = $null
}
~~~

POSIX shellの場合:

~~~bash
read -rsp "TypeSafe API key: " TYPESAFE_API_KEY
export TYPESAFE_API_KEY
python -m model_effort_router examples/request.json
unset TYPESAFE_API_KEY
~~~

CI、container、agent hostでは、各platformのsecret storeから同じ環境変数を
注入してください。Bitwarden Secrets Managerではbws runを利用できます。
Codex pluginはhost processの環境だけを継承し、pluginのinstallだけではキーを
設定しません。.env、JSON、plugin manifest、skill、logへキーを保存しないでください。

## Jevモードとプライバシー

TYPESAFE_API_KEYがない場合は**framework-only／dry-runモード**です。
分解と割当のChoice payloadを出力し、外部通信は行いません。Jevが呼ばれたとは
扱いません。

TYPESAFE_API_KEYがあり、--dry-runを指定しない場合は、TypeSafeへ最小限の
ルーティング状態を送ります。1回目で分解候補を選び、confidence policyを通過した
場合に2回目でタスクごとのmodel／effortを選びます。キーがあっても通信を止める
場合は--dry-runを使ってください。

キーを入力JSON、ソースコード、ログへ書き込まないでください。認証情報、個人情報、
非公開ソース、リポジトリ全体などをTypeSafeへ送らないでください。

不明、不正、または不完全な応答はfail closedで扱います。推測で選択せず、
エラーまたはneeds_reviewとして返します。

既定のconfidence閾値0.5は保守的な設定値であり、校正済みの正確性を示すものでは
ありません。閾値未満の選択はneeds_reviewとなり、割当は返されません。

## 開発

~~~powershell
python -m unittest discover -s tests -v
~~~

貢献方法は[CONTRIBUTING.md](CONTRIBUTING.md)、セキュリティ報告は
[SECURITY.md](SECURITY.md)を参照してください。

## ライセンス

[Apache-2.0](LICENSE)で公開しています。
