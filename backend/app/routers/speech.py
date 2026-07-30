from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.services.speech_service import speech_file, speech_marks
from app.tts import TTSNotReady

router = APIRouter(prefix="/api", tags=["speech"])


@router.get("/speech")
async def speak(
    text: str = Query(..., description="Palabra o frase a pronunciar"),
    ipa: str | None = Query(None, description="Fuerza la pronunciacion exacta en IPA"),
    slow: bool = Query(False, description="Velocidad reducida"),
) -> FileResponse:
    """Audio de referencia para una palabra que fallaste.

    `ipa` importa cuando la grafia enganya: sin el, el motor puede leer la
    palabra de una forma razonable que no es la que se esta corrigiendo.
    """
    try:
        path, media_type = await run_in_threadpool(speech_file, text, ipa=ipa, slow=slow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TTSNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return FileResponse(
        path,
        media_type=media_type,
        # El audio es inmutable: la misma peticion siempre da el mismo archivo.
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/speech/marks")
async def marks(
    text: str = Query(..., description="Texto a sintetizar"),
    slow: bool = Query(False),
) -> dict:
    """Tiempos por palabra para el resaltado tipo karaoke.

    Los offsets apuntan al texto original, asi que el lector resalta sobre los
    mismos caracteres que ya tiene renderizados. Sintetiza si no esta en cache,
    y la peticion de audio posterior reutiliza ese mismo archivo.
    """
    try:
        data = await run_in_threadpool(speech_marks, text, slow=slow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TTSNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"marks": data}
