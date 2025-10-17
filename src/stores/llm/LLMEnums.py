from enum import Enum

class LLMEnums(str, Enum):
    OPENAI = "OPENAI"
    AZURE = "AZURE"
    ANTHROPIC = "ANTHROPIC"
    COHERE = "COHERE"


class OPENAIEnums(str, Enum):
    SYSTEM = "system"
    USER="user"
    ASSISTANT="assistant"

class CohereEums(str, Enum):
    SYSTEM = "SYSTEM"
    USER="USER"
    ASSISTANT="CHATBOT"
    DOCUMENT="search_document"
    QUERY="search_query"

class DocumentTypeEums(str, Enum):
    DOCUMENT = "document"
    QUERY="query"
