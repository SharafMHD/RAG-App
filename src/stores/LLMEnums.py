from enum import Enum

class LLMEnums(str, Enum):
    OPENAI = "openai"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    AI21 = "ai21"
    CUSTOM = "custom"

class OPENAIEnums(str, Enum):
    SYSTEM = "system"
    USER="user"
    ASSISTANT="assistant"