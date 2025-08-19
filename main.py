# main.py
import os
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from services.excel_service import procesar_excel
from services.supabase_service import insertar_tareas, filtrar_tareas, obtener_facetas

load_dotenv()

app = FastAPI(title="API Cambios de Ingeniería")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ En prod: poné tu dominio (p.ej. ["https://app.tudominio.com"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-tareas")
async def upload_tareas(file: UploadFile = File(...)):
    print("📤 Archivo recibido:", file.filename)
    tareas = procesar_excel(file)
    print(f"🗂️ Tareas procesadas: {len(tareas)}")

    insertadas, actualizadas = insertar_tareas(tareas)
    tareas_cargadas = (insertadas or 0) + (actualizadas or 0)  # 👈 suma para el front

    return {
        "status": "ok",
        "procesadas": len(tareas),
        "insertadas": insertadas,
        "actualizadas": actualizadas,
        "tareas_cargadas": tareas_cargadas,  # 👈 clave que espera el front
    }

@app.get("/tareas-filtradas")
def obtener_tareas(
    response: Response,
    estado: Optional[str] = Query(None, description="CSV. Ej: Implementado,Efectividad verificada"),
    prioridad: Optional[str] = Query(None, description="CSV"),
    colaborador: Optional[str] = Query(None, description="CSV"),
    tablero: Optional[str] = Query(None),
    desde: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_creacion >=)"),
    hasta: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_creacion <=)"),
    q: Optional[str] = Query(None, description="busca en nombre/descripcion"),
    order_by: str = Query("fecha_creacion"),
    order_dir: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    # extras
    vencida: Optional[bool] = Query(None),  # ⚠️ si tu tabla no tiene 'vencida', lo ignora el servicio
    vencimiento_desde: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_vencimiento >=)"),
    vencimiento_hasta: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_vencimiento <=)"),
    finalizacion_desde: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_finalizacion >=)"),
    finalizacion_hasta: Optional[str] = Query(None, description="YYYY-MM-DD (fecha_finalizacion <=)"),
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
