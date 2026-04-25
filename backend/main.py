from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import load_settings
from .schemas import (
    AbstractionRunsResponse,
    AbstractionStatusResponse,
    BeliefListResponse,
    BrowserCaptureRequest,
    BulkNoiseLabelRequest,
    BulkNoiseLabelResponse,
    CleanupRequest,
    CleanupResponse,
    CollectionsResponse,
    ExportResponse,
    ForgetRequest,
    ForgetResponse,
    HealthResponse,
    NoiseLabelRequest,
    OpenCaptureRequest,
    OpenCaptureResponse,
    PinRequest,
    PrivacySettings,
    RecentResponse,
    RefreshRequest,
    RefreshResponse,
    SearchRequest,
    SearchResponse,
    StatsResponse,
    StoragePolicy,
    StorageStatsResponse,
    TodoCreateRequest,
    TodoItem,
    TodoListResponse,
    TodoUpdateRequest,
    RunAbstractionResponse,
    UserModelResponse,
    WeeklyDigestResponse,
)
from .security import require_api_key
from .service import (
    insert_browser_capture,
    cleanup_storage,
    create_todo,
    delete_todo,
    export_data,
    forget_captures,
    get_privacy_settings,
    get_storage_policy,
    log_search_click,
    list_todos,
    open_capture,
    recent,
    refresh_index,
    save_privacy_settings,
    save_storage_policy,
    search,
    smart_collections,
    stats,
    storage_stats,
    update_capture_pin,
    update_capture_noise_label,
    update_capture_noise_labels,
    update_todo,
    weekly_digest,
)
from .user_model_service import (
    abstraction_runs,
    abstraction_status,
    delete_belief,
    latest_user_model,
    list_beliefs,
    trigger_abstraction_background,
)


settings = load_settings()
_index_task: Optional[asyncio.Task] = None

app = FastAPI(
    title="MemoryOS Backend",
    version="0.1.0",
    description="Local FastAPI service for MemoryOS search, stats, and capture ingest.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-MemoryOS-API-Key"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, api_key_enabled=settings.api_key_enabled)


@app.post("/search", response_model=SearchResponse, dependencies=[Depends(require_api_key)])
def search_endpoint(request: SearchRequest) -> SearchResponse:
    try:
        response = search(request.query, request.top_k, request.candidate_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    results = response["results"]
    return SearchResponse(
        query=request.query,
        count=len(results),
        candidate_count=response["candidate_count"],
        elapsed_ms=response["elapsed_ms"],
        index_backend=response["index_backend"],
        reranker=response["reranker"],
        results=results,
    )


@app.get("/recent", response_model=RecentResponse, dependencies=[Depends(require_api_key)])
def recent_endpoint(
    limit: int = Query(default=50, ge=1, le=500),
    app_name: Optional[str] = None,
    source_type: Optional[str] = None,
) -> RecentResponse:
    results = recent(limit=limit, app_name=app_name, source_type=source_type)
    return RecentResponse(count=len(results), results=results)


@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(require_api_key)])
def stats_endpoint() -> StatsResponse:
    return StatsResponse(**stats())


@app.post("/refresh-index", response_model=RefreshResponse, dependencies=[Depends(require_api_key)])
def refresh_index_endpoint(request: RefreshRequest) -> RefreshResponse:
    if request.backend not in {"auto", "sentence", "tfidf"}:
        raise HTTPException(status_code=422, detail="backend must be one of: auto, sentence, tfidf")
    try:
        count, artifact_path, backend_name = refresh_index(
            backend=request.backend,
            model=request.model,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RefreshResponse(indexed_count=count, artifact_path=artifact_path, backend=backend_name)


@app.post("/capture/browser", dependencies=[Depends(require_api_key)])
def capture_browser_endpoint(request: BrowserCaptureRequest) -> Response:
    insert_browser_capture(
        url=request.url,
        title=request.title,
        content=request.content,
        timestamp=request.timestamp,
    )
    return Response(status_code=204)


@app.post("/click", dependencies=[Depends(require_api_key)])
def click_endpoint(
    query: str,
    capture_id: int,
    rank: Optional[int] = None,
    dwell_ms: Optional[int] = Query(default=None, ge=0),
) -> Response:
    log_search_click(query=query, capture_id=capture_id, rank=rank, dwell_ms=dwell_ms)
    return Response(status_code=204)


@app.post("/open", response_model=OpenCaptureResponse, dependencies=[Depends(require_api_key)])
def open_capture_endpoint(request: OpenCaptureRequest) -> OpenCaptureResponse:
    try:
        target = open_capture(request.capture_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not open capture: {exc}") from exc
    return OpenCaptureResponse(opened=True, target=target)


@app.patch("/captures/{capture_id}/noise", dependencies=[Depends(require_api_key)])
def label_capture_endpoint(capture_id: int, request: NoiseLabelRequest) -> Response:
    try:
        found = update_capture_noise_label(capture_id, request.is_noise)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=404, detail="Capture not found.")
    return Response(status_code=204)


@app.patch("/captures/noise/bulk", response_model=BulkNoiseLabelResponse, dependencies=[Depends(require_api_key)])
def bulk_label_capture_endpoint(request: BulkNoiseLabelRequest) -> BulkNoiseLabelResponse:
    try:
        updated = update_capture_noise_labels(request.capture_ids, request.is_noise)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BulkNoiseLabelResponse(updated_count=updated)


@app.patch("/captures/{capture_id}/pin", dependencies=[Depends(require_api_key)])
def pin_capture_endpoint(capture_id: int, request: PinRequest) -> Response:
    found = update_capture_pin(capture_id, request.is_pinned)
    if not found:
        raise HTTPException(status_code=404, detail="Capture not found.")
    return Response(status_code=204)


@app.get("/collections", response_model=CollectionsResponse, dependencies=[Depends(require_api_key)])
def collections_endpoint() -> CollectionsResponse:
    collections = smart_collections()
    return CollectionsResponse(count=len(collections), collections=collections)


@app.get("/digest/weekly", response_model=WeeklyDigestResponse, dependencies=[Depends(require_api_key)])
def weekly_digest_endpoint() -> WeeklyDigestResponse:
    return WeeklyDigestResponse(**weekly_digest())


@app.get("/todos", response_model=TodoListResponse, dependencies=[Depends(require_api_key)])
def todos_endpoint(status: Optional[str] = None) -> TodoListResponse:
    if status is not None and status not in {"open", "done"}:
        raise HTTPException(status_code=422, detail="status must be open or done")
    todos = list_todos(status=status)
    return TodoListResponse(count=len(todos), todos=todos)


@app.post("/todos", response_model=TodoItem, dependencies=[Depends(require_api_key)])
def create_todo_endpoint(request: TodoCreateRequest) -> TodoItem:
    return create_todo(
        title=request.title,
        notes=request.notes,
        priority=request.priority,
        due_at=request.due_at,
        source_capture_id=request.source_capture_id,
    )


@app.patch("/todos/{todo_id}", response_model=TodoItem, dependencies=[Depends(require_api_key)])
def update_todo_endpoint(todo_id: int, request: TodoUpdateRequest) -> TodoItem:
    try:
        todo = update_todo(
            todo_id,
            title=request.title,
            notes=request.notes,
            status=request.status,
            priority=request.priority,
            due_at=request.due_at,
            source_capture_id=request.source_capture_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found.")
    return todo


@app.delete("/todos/{todo_id}", dependencies=[Depends(require_api_key)])
def delete_todo_endpoint(todo_id: int, confirm: bool = False) -> Response:
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true before deleting a todo.")
    if not delete_todo(todo_id):
        raise HTTPException(status_code=404, detail="Todo not found.")
    return Response(status_code=204)


@app.get("/user-model", response_model=UserModelResponse, dependencies=[Depends(require_api_key)])
def user_model_endpoint() -> UserModelResponse:
    model = latest_user_model()
    if not model:
        return UserModelResponse(status="no_model", message="Run abstraction engine first")
    return UserModelResponse(**model)


@app.get("/beliefs", response_model=BeliefListResponse, dependencies=[Depends(require_api_key)])
def beliefs_endpoint(
    belief_type: Optional[str] = None,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
) -> BeliefListResponse:
    try:
        beliefs = list_beliefs(belief_type=belief_type, min_confidence=min_confidence, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BeliefListResponse(count=len(beliefs), beliefs=beliefs)


@app.delete("/beliefs/{topic}", dependencies=[Depends(require_api_key)])
def delete_belief_endpoint(topic: str, confirm: bool = False) -> Response:
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true before deleting a belief.")
    if not delete_belief(topic):
        raise HTTPException(status_code=404, detail="Belief not found.")
    return Response(status_code=204)


@app.post("/run-abstraction", response_model=RunAbstractionResponse, dependencies=[Depends(require_api_key)])
def run_abstraction_endpoint() -> RunAbstractionResponse:
    started = trigger_abstraction_background()
    if not started:
        return RunAbstractionResponse(status="already_running", message="Abstraction engine is already running.")
    return RunAbstractionResponse(status="started", message="Abstraction engine running in background.")


@app.get("/abstraction-runs", response_model=AbstractionRunsResponse, dependencies=[Depends(require_api_key)])
def abstraction_runs_endpoint(limit: int = Query(default=10, ge=1, le=100)) -> AbstractionRunsResponse:
    runs = abstraction_runs(limit=limit)
    return AbstractionRunsResponse(count=len(runs), runs=runs)


@app.get("/abstraction-status", response_model=AbstractionStatusResponse, dependencies=[Depends(require_api_key)])
def abstraction_status_endpoint() -> AbstractionStatusResponse:
    return AbstractionStatusResponse(**abstraction_status())


@app.get("/privacy", response_model=PrivacySettings, dependencies=[Depends(require_api_key)])
def privacy_endpoint() -> PrivacySettings:
    return get_privacy_settings()


@app.put("/privacy", response_model=PrivacySettings, dependencies=[Depends(require_api_key)])
def update_privacy_endpoint(request: PrivacySettings) -> PrivacySettings:
    return save_privacy_settings(request)


@app.get("/storage", response_model=StorageStatsResponse, dependencies=[Depends(require_api_key)])
def storage_endpoint() -> StorageStatsResponse:
    return StorageStatsResponse(**storage_stats())


@app.get("/storage-policy", response_model=StoragePolicy, dependencies=[Depends(require_api_key)])
def storage_policy_endpoint() -> StoragePolicy:
    return get_storage_policy()


@app.put("/storage-policy", response_model=StoragePolicy, dependencies=[Depends(require_api_key)])
def update_storage_policy_endpoint(request: StoragePolicy) -> StoragePolicy:
    return save_storage_policy(request)


@app.post("/cleanup", response_model=CleanupResponse, dependencies=[Depends(require_api_key)])
def cleanup_endpoint(request: CleanupRequest) -> CleanupResponse:
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true before cleanup.")
    return cleanup_storage(
        delete_noise=request.delete_noise,
        delete_duplicates=request.delete_duplicates,
        apply_retention=request.apply_retention,
        enforce_size_cap=request.enforce_size_cap,
        rotate_logs=request.rotate_logs,
        rebuild_index=request.rebuild_index,
    )


@app.get("/export", response_model=ExportResponse, dependencies=[Depends(require_api_key)])
def export_endpoint() -> ExportResponse:
    return ExportResponse(**export_data())


@app.post("/forget", response_model=ForgetResponse, dependencies=[Depends(require_api_key)])
def forget_endpoint(request: ForgetRequest) -> ForgetResponse:
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true before deleting captures.")
    try:
        deleted = forget_captures(
            from_timestamp=request.from_timestamp,
            to_timestamp=request.to_timestamp,
            app_name=request.app_name,
            source_type=request.source_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ForgetResponse(deleted_count=deleted)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


async def _background_index_loop() -> None:
    interval = settings.index_interval_seconds
    while interval > 0:
        await asyncio.sleep(interval)
        try:
            cleanup_storage(rebuild_index=False)
            refresh_index(
                backend=settings.index_backend,
                model=settings.index_model,
                limit=None,
            )
        except Exception:
            pass


@app.on_event("startup")
async def start_background_indexer() -> None:
    global _index_task
    if settings.index_interval_seconds > 0 and _index_task is None:
        _index_task = asyncio.create_task(_background_index_loop())


@app.on_event("shutdown")
async def stop_background_indexer() -> None:
    global _index_task
    if _index_task is None:
        return
    _index_task.cancel()
    with suppress(asyncio.CancelledError):
        await _index_task
    _index_task = None


if __name__ == "__main__":
    run()
