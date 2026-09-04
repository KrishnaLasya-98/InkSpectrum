from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelConfig:
    model_id: str
    provider: str
    display_name: str
    context_window: int = 8192
    rpm_limit: Optional[int] = None
    rpd_limit: Optional[int] = None
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0
    supports_free_tier: bool = False
    notes: str = ""


MODEL_CATALOG = {
    "qwen3-coder:free": ModelConfig(
        model_id="qwen3-coder:free",
        provider="anyapi",
        display_name="Qwen3 Coder (Free)",
        context_window=32768,
        rpm_limit=60,
        rpd_limit=None,
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        supports_free_tier=True,
        notes="Primary coding candidate"
    ),
    "openai/gpt-oss-120b": ModelConfig(
        model_id="openai/gpt-oss-120b",
        provider="groq",
        display_name="GPT-OSS 120B",
        context_window=8192,
        rpm_limit=30,
        rpd_limit=1000,
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
        supports_free_tier=True,
        notes="OpenAI open-source, high performance"
    ),
    "qwen3-32b": ModelConfig(
        model_id="qwen3-32b",
        provider="groq",
        display_name="Qwen3 32B",
        context_window=8192,
        rpm_limit=30,
        rpd_limit=1000,
        input_cost_per_1m=0.29,
        output_cost_per_1m=0.59,
        supports_free_tier=True,
        notes="Qwen3 32B parameter model"
    ),
    "google/gemma-4-26b-a4b-it:free": ModelConfig(
        model_id="google/gemma-4-26b-a4b-it:free",
        provider="anyapi",
        display_name="Gemma 4 26B (Free)",
        context_window=8192,
        rpm_limit=60,
        rpd_limit=None,
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        supports_free_tier=True,
        notes="Google instruction-tuned model"
    ),
    "nvidia/nemotron-nano-9b-v2:free": ModelConfig(
        model_id="nvidia/nemotron-nano-9b-v2:free",
        provider="anyapi",
        display_name="Nemotron Nano 9B (Free)",
        context_window=8192,
        rpm_limit=60,
        rpd_limit=None,
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        supports_free_tier=True,
        notes="Lightweight NVIDIA model"
    ),
    "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free": ModelConfig(
        model_id="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        provider="together",
        display_name="Llama 3.3 70B (Free)",
        context_window=8192,
        rpm_limit=60,
        rpd_limit=None,
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        supports_free_tier=True,
        notes="Backup option, Together AI free credits"
    ),
    "deepseek-v4-flash": ModelConfig(
        model_id="deepseek-v4-flash",
        provider="deepseek",
        display_name="DeepSeek V4 Flash",
        context_window=65536,
        rpm_limit=100,
        rpd_limit=None,
        input_cost_per_1m=0.44,
        output_cost_per_1m=0.22,
        supports_free_tier=False,
        notes="5M free tokens / 30 days on signup"
    ),
}
