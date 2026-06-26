from dataclasses import dataclass, field


@dataclass
class DocumentRecord:
    id: str
    filename: str
    source_path: str
    file_type: str
    status: str
    chunk_count: int = 0
    total_pages: int = 0
    strategy: str = ""
    tags: list[str] = field(default_factory=list)
    error: str = ""
    created_at: str = ""
    updated_at: str = ""
