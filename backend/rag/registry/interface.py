from abc import ABC, abstractmethod

from backend.rag.registry.models import DocumentRecord


class DocumentRegistry(ABC):
    @abstractmethod
    def create_document(self, record: DocumentRecord) -> None:
        ...

    @abstractmethod
    def get_document(self, document_id: str) -> DocumentRecord | None:
        ...

    @abstractmethod
    def list_documents(self) -> list[DocumentRecord]:
        ...

    @abstractmethod
    def update_document(self, document_id: str, **fields) -> None:
        ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        ...
