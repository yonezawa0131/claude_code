# orchestrator — マルチモデル・オーケストレーター

「Fable 5 実践ガイド」([検証結果](../notes/fable5-guide-review.md))の設計思想から
使える部分だけを抽出し、**実在の API・実在のモデル・実在の価格**で実装した
自己改善型タスク実行基盤。公式 Anthropic SDK(`AsyncAnthropic`)を基盤にする。

## アーキテクチャ

```
Task ──▶ Router ──────▶ ExecutionLoop ──▶ Provider (AsyncAnthropic)
          │  ▲              │  ▲
          │  │ 学習         │  │ 検証(実行者と別モデル)
          ▼  │              ▼  │
        MemoryStore    VerificationEngine
        (episodes.json)      │
                             ▼
                       StateManager (STATE.md + state.json / コスト上限)
```

| モジュール | 役割 |
|---|---|
| `models.py` | モデルカタログと価格(実在の値のみ。出典と日付を明記) |
| `router.py` | 複雑度・種別・予算・過去実績からモデルを選択 |
| `providers.py` | Provider 抽象 + AnthropicProvider 実装 |
| `verification.py` | 別モデル(Haiku)による品質検証。structured outputs で JSON 保証 |
| `loop.py` | 実行 → 検証 → 改善指示注入 → 再試行(最大3回)→ エスカレーション |
| `memory.py` | エピソード記憶。成功実績が Router の次回判断に反映される |
| `state.py` | チェックポイント・再開・コスト上限強制(STATE.md 出力) |

## ルーティング表

| 複雑度 | モデル | 単価 (in/out per MTok) | effort |
|---|---|---|---|
| TRIVIAL / SIMPLE | claude-haiku-4-5 | $1 / $5 | — |
| MODERATE | claude-sonnet-5 | $3 / $15 | medium |
| COMPLEX | claude-opus-4-8 | $5 / $25 | high |
| CRITICAL | claude-opus-4-8 | $5 / $25 | xhigh |
| `required_quality="maximum"` 明示時のみ | claude-fable-5 | $10 / $50 | xhigh |

- 検証タスクは常に Haiku(実行者と検証者を分離する原則も兼ねる)
- 予算超過見積り時は自動で安いティアへダウングレード
- 同種タスクで成功率90%以上の実績(3件以上)があるモデルは既定より優先
- claude-fable-5 で安全分類器が拒否した場合はフォールバックせず
  `ModelRefusedError` → ExecutionLoop がエスカレーションとして扱う

## 使い方

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# デモ(キー未設定ならルーティング判断のみのドライラン)
python3 examples/run_task.py "競合3社のSNS戦略を分析して" --budget 0.50
```

```python
from orchestrator import (
    AnthropicProvider, ExecutionLoop, MemoryStore,
    Router, StateManager, Task, VerificationEngine,
)

memory = MemoryStore()
provider = AnthropicProvider()
loop = ExecutionLoop(
    provider=provider,
    router=Router(memory),
    verifier=VerificationEngine(provider),
    state=StateManager("session_001", goal="...", budget_usd=5.0),
    memory=memory,
)
result = await loop.run(Task(description="...", budget_usd=1.0))
```

## テスト

API キー不要。Provider をフェイクに差し替えて全ロジックを検証する。

```bash
pip install pytest pytest-asyncio
python3 -m pytest -q   # 18 passed
```

## 設計上の判断

- **架空モデルを持ち込まない**: ガイドにあった `gpt-5.5` / `codex-2026` /
  `claude-opus-5` 等は実在しないため不採用。他社モデルが必要になったら
  `Provider` プロトコルの実装を1つ足せばよい(Router のカタログ登録も忘れずに)。
- **検証者は実行者と別モデル**: 同一モデルは同じバイアスを持つため。
  検証は structured outputs で JSON スキーマを強制し、パース失敗をなくす。
- **失敗も記録する**: エスカレーションした試行もエピソード記憶に残り、
  Router がそのモデルを避ける材料になる。
- **コスト上限はソフトではなくハード**: `StateManager.track_cost()` が
  上限到達で `CostLimitExceeded` を送出し、処理を止める。
- **価格は `models.py` の1箇所のみ**: 改定時はカタログだけ更新する
  (2026-06-24 時点の公式ドキュメントの値)。
