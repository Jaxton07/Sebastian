# llm — LLM Provider 抽象层

## 职责

将不同 LLM 服务商的 SDK 差异封装在 Provider 内部，向上暴露统一的流式事件接口（`LLMStreamEvent`）。多轮工具调用循环由 `AgentLoop` 驱动，Provider 只负责单次 API 调用。

## 关键文件

| 文件 | 职责 |
|---|---|
| `provider.py` | `LLMProvider` 抽象基类；定义 `stream()` 接口和 `message_format` 属性 |
| `anthropic.py` | Anthropic SDK 适配，处理 thinking block、tool_use streaming |
| `openai_compat.py` | OpenAI `/v1/chat/completions` 适配，兼容 DeepSeek-R1 等第三方模型 |
| `registry.py` | DB 驱动的 Provider 注册表，支持运行时切换；无配置时回退到环境变量 Anthropic |

## message_format

`LLMProvider.message_format` 决定 `AgentLoop` 如何构建对话历史：

| 值 | 适用 Provider | assistant 消息格式 | tool result 格式 |
|---|---|---|---|
| `"anthropic"` | `AnthropicProvider` | `content: [block...]` | `role:user` 内嵌 `tool_result` block |
| `"openai"` | `OpenAICompatProvider` | `content: null, tool_calls: [...]` | `role:tool` 独立消息 |

新增 Provider 时，**必须**声明 `message_format` 类变量。

## 公开接口

```python
from sebastian.llm.provider import LLMProvider
from sebastian.llm.registry import LLMProviderRegistry

# 获取当前默认 Provider（DB 优先，回退 env）
provider, model = await registry.get_default_with_model()

# 直接实例化（测试或脚本用）
from sebastian.llm.anthropic import AnthropicProvider
from sebastian.llm.openai_compat import OpenAICompatProvider

provider = AnthropicProvider(api_key="sk-ant-...")
provider = OpenAICompatProvider(api_key="...", base_url="...", thinking_format="reasoning_content")
```

## OpenAI 兼容的 thinking_format

`OpenAICompatProvider` 通过 `thinking_format` 参数支持不同推理模型：

| 值 | 适用场景 |
|---|---|
| `None`（默认） | 标准 GPT 模型，无 thinking |
| `"reasoning_content"` | DeepSeek-R1：`delta.reasoning_content` 字段 |
| `"think_tags"` | llama.cpp 等：响应文本内嵌 `<think>...</think>` |

## 常见任务入口

- **新增 Provider**（如 Google Gemini）→ 继承 `LLMProvider`，声明 `message_format`，在 `registry.py._instantiate()` 注册 `provider_type`
- **切换默认模型** → 更新 DB 中 `is_default=True` 的 `LLMProviderRecord`，或修改 `settings.sebastian_model`
- **调试 Provider 输出** → 在 `provider.stream()` 加日志，事件流由 `AgentLoop` 消费
