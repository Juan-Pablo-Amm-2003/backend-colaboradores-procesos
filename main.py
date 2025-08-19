import os
import logging
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from services.excel_service import procesar_excel
from services.supabase_service import insertar_tareas, filtrar_tareas, obtener_facetas

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

def get_origins_from_env() -> List[str]:
    raw = os.getenv("FRONT_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:5173"]

app = FastAPI(title="API Cambios de Ingeniería")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_origins_from_env(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-tareas")
async def upload_tareas(file: UploadFile = File(...)):
    logger.info("📤 Archivo recibido: %s", file.filename)
    tareas = procesar_excel(file)
    logger.info("🗂️ Tareas procesadas: %d", len(tareas))

    insertadas, actualizadas = insertar_tareas(tareas)
    tareas_cargadas = (insertadas or 0) + (actualizadas or 0)

    return {
        "status": "ok",
        "procesadas": len(tareas),
        "insertadas": insertadas,
        "actualizadas": actualizadas,
        "tareas_cargadas": tareas_cargadas,
    }

@app.get("/tareas-filtradas")
def obtener_tareas(
    response: Response,
    estado: Optional[str] = Query(None, description="CSV. Ej: Implementado,Efectividad verificada"),
    prioridad: Optional[str] = Query(None, description="CSV"),
    colaborador: Optional[str] = Query(None, description="CSV"),
    tablero: Optional[str] = Query(None),
    desde: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_creacion >=)", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hasta: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_creacion <=)", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    q: Optional[str] = Query(None, description="busca en nombre/descripcion"),
    order_by: str = Query("fecha_creacion"),
    order_dir: str = Query("desc", pattern=r"^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    # extras
    vencida: Optional[bool] = Query(None),
    vencimiento_desde: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_vencimiento >=)", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    vencimiento_hasta: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_vencimiento <=)", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    finalizacion_desde: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_finalizacion >=)", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    finalizacion_hasta: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_finalizacion <=)", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    data, total = filtrar_tareas(
        estado=estado,
        prioridad=prioridad,
        colaborador=colaborador,
        tablero=tablero,
        desde=desde,
        hasta=hasta,
        q=q,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
        offset=offset,
        vencida=vencida,
        vencimiento_desde=vencimiento_desde,
        vencimiento_hasta=vencimiento_hasta,
        finalizacion_desde=finalizacion_desde,
        finalizacion_hasta=finalizacion_hasta,
    )
    response.headers["X-Total-Count"] = str(total)
    return {"status": "ok", "total": total, "data": data}

@app.get("/facetas")
def facetas():
    return {"status": "ok", "data": obtener_facetas()}
