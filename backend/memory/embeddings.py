"""
嵌入函数 — 将文本转为向量

提供:
1. SimpleEmbedding: 轻量本地嵌入（基于单词哈希，零依赖）
2. APIEmbedding: 通过 DeepSeek/OpenAI API 获取嵌入（可选）
"""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from typing import Any


class BaseEmbedding(ABC):
    """嵌入抽象"""

    dim: int = 128

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]


class SimpleEmbedding(BaseEmbedding):
    """
    轻量本地嵌入 — 基于单词哈希 + TF 归一化

    优点: 零依赖，内存小，速度快
    缺点: 语义精度有限（但足够区分话题差异）
    """

    def __init__(self, dim: int = 128):
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * self.dim

        vec = [0.0] * self.dim
        words = text.lower().split()

        for word in words:
            # 用 MD5 哈希将词映射到向量的多个位置
            h = hashlib.md5(word.encode()).hexdigest()
            # 每个词影响 3 个位置（增加碰撞鲁棒性）
            for i in range(3):
                idx = (int(h[i*8:(i+1)*8], 16) if len(h) > i*8 else int(h, 16)) % self.dim
                vec[idx] += 1.0

        # L2 归一化
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec


class APIEmbedding(BaseEmbedding):
    """
    通过 API 获取高质量嵌入

    支持 OpenAI 兼容接口（DeepSeek / OpenAI）
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.deepseek.com/v1",
        dim: int = 256,
    ):
        from openai import AsyncOpenAI
        self.dim = dim
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def embed(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * self.dim

        resp = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return resp.data[0].embedding
