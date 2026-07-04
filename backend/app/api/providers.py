from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.exceptions import LLMError
from backend.app.core.llm_manager import LLMManager, get_llm_manager
from backend.schemas.provider import ProviderConfig, ProviderStatus

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/status")
async def get_status(manager: LLMManager = Depends(get_llm_manager)) -> ProviderStatus:
    return ProviderStatus(
        configured=manager.is_configured(),
        provider=manager.provider,
        model=manager.model,
    )


@router.post("/configure")
async def configure_provider(
    config: ProviderConfig,
    manager: LLMManager = Depends(get_llm_manager),
) -> ProviderStatus:
    try:
        await manager.configure(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
        )
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ProviderStatus(
        configured=manager.is_configured(),
        provider=manager.provider,
        model=manager.model,
    )
