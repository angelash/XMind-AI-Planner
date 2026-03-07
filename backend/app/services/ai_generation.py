from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1


@dataclass(frozen=True)
class AIGenerationService:
    """Deterministic text generation helpers for initial scaffolding."""

    def build_initial(self, topic: str) -> dict[str, object]:
        clean_topic = topic.strip()
        root_id = self._node_id('root', clean_topic)
        return {
            'id': root_id,
            'text': clean_topic,
            'children': [
                {
                    'id': self._node_id('overview', clean_topic),
                    'text': f'{clean_topic} 背景与目标',
                },
                {
                    'id': self._node_id('plan', clean_topic),
                    'text': f'{clean_topic} 执行路径',
                },
                {
                    'id': self._node_id('risk', clean_topic),
                    'text': f'{clean_topic} 风险与应对',
                },
            ],
        }

    def expand(self, node_text: str, *, count: int) -> list[dict[str, str]]:
        clean_text = node_text.strip()
        templates = ['定义范围', '关键动作', '验收标准', '协作分工', '里程碑']
        items: list[dict[str, str]] = []
        for index in range(count):
            suffix = templates[index % len(templates)]
            text = f'{clean_text} - {suffix}'
            items.append({'id': self._node_id(f'expand-{index}', text), 'text': text})
        return items

    def rewrite(self, text: str, instruction: str | None) -> str:
        clean_text = text.strip()
        if not instruction:
            return f'{clean_text}（已优化表达）'
        clean_instruction = instruction.strip()
        return f'{clean_text}（按要求：{clean_instruction}）'

    @staticmethod
    def _node_id(prefix: str, seed: str) -> str:
        digest = sha1(seed.encode('utf-8')).hexdigest()[:10]
        return f'node-{prefix}-{digest}'


ai_generation_service = AIGenerationService()
