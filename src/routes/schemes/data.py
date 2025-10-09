from pydantic import BaseModel
from typing import Optional
class ProcessRequest(BaseModel):
    file_id: str = None
    chunk_size: Optional[int] = 512000  # Default chunk size in bytes
    overlap_size: Optional[int] = 5120  # Default overlap size in bytes
    do_reset: Optional[bool] = False
