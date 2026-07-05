import json

import pytest

from orchestrator.providers import Completion


class FakeProvider:
    """API を呼ばないテスト用 Provider。

    scripted に (実行者応答テキスト, 検証者スコアdict) を並べる。
    verifier からの呼び出し(output_schema あり)には JSON を返す。
    """

    def __init__(self):
        self.executor_responses: list[str] = []
        self.verifier_scores: list[dict[str, float]] = []
        self.calls: list[dict] = []

    async def complete(
        self,
        *,
        model,
        messages,
        system=None,
        max_tokens=16_000,
        effort=None,
        output_schema=None,
    ) -> Completion:
        self.calls.append(
            {
                "model": model,
                "system": system,
                "messages": messages,
                "effort": effort,
                "is_verifier": output_schema is not None,
            }
        )
        if output_schema is not None:
            scores = self.verifier_scores.pop(0)
            criteria_names = list(
                output_schema["properties"]["criteria"]["properties"].keys()
            )
            payload = {
                "criteria": {
                    name: {"score": scores.get(name, 1.0), "issues": []}
                    for name in criteria_names
                },
                "improvement_instructions": "もっと具体的に。",
            }
            text = json.dumps(payload)
        else:
            text = self.executor_responses.pop(0)
        return Completion(
            text=text,
            model=model,
            input_tokens=1000,
            output_tokens=500,
        )


@pytest.fixture
def fake_provider():
    return FakeProvider()
