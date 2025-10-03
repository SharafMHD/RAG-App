from pydantic import BaseModel
from typing import Optional
class ProcessRequest(BaseModel):
    file_id: str
    chunk_size: Optional[int] = 100  # Default chunk size in bytes
    overlap_size: Optional[int] = 20  # Default overlap size in bytes
    do_reset: Optional[bool] = False
