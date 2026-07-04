from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document
from backend.schemas.document import DocumentCreate, DocumentUpdate


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, data: DocumentCreate) -> Document:
        document = Document(
            filename=data.filename,
            file_type=data.file_type,
            file_size=data.file_size,
            file_hash=data.file_hash,
            strategy=data.strategy,
            meta=data.meta,
        )
        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)
        return document

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def list(self, limit: int = 50, offset: int = 0) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update(self, document_id: UUID, data: DocumentUpdate) -> Document | None:
        fields = data.model_dump(exclude_unset=True)
        if not fields:
            return await self.get_by_id(document_id)
        await self._session.execute(
            update(Document).where(Document.id == document_id).values(**fields)
        )
        await self._session.commit()
        return await self.get_by_id(document_id)

    async def delete(self, document_id: UUID) -> bool:
        result = await self._session.execute(
            delete(Document).where(Document.id == document_id)
        )
        await self._session.commit()
        return result.rowcount > 0
