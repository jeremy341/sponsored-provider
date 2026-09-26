"""Compatibility imports for existing Alibaba-specific call sites."""

from .openai_compatible import OpenAICompatibleClient


AlibabaClient = OpenAICompatibleClient
