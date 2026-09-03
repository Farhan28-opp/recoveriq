from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {
        "service": "RecoverIQ",
        "status": "ok",
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "recoveriq-api",
    }
