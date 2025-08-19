import os, json, time, math
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Faltan SUPABASE_URL / SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Solo columnas que EXISTEN en la tabla
COMPARE_FIELDS = [
    "nombre_tarea","descripcion","colaborador","creado_por",
    "estado","prioridad",
    "fecha_creacion","fecha_vencimiento","fecha_finalizacion",
    "completado_por","etiquetas","checklist",
    "retrasada","nombre_tablero",
]

SAFE_ORDER_COLUMNS = {
    "fecha_creacion","fecha_vencimiento","fecha_finalizacion",
    "prioridad","estado","colaborador","nombre_tablero"
}

def _retry(callable_):
    delay = 0.5
    for i in range(4):
        try:
            return callable_()
        except Exception:
            if i == 3:
                raise
            time.sleep(delay)
            delay *= 2

def _normalize(obj):
    if isinstance(obj, list):
        return sorted([_normalize(x) for x in obj], key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in sorted(obj.items())}
    return obj

def _sanitize_json(v):
    """Convierte NaN/±Infinity en None y limpia diccionarios/listas recursivamente."""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, list):
        out = []
        for x in v:
            sx = _sanitize_json(x)
            # mantenemos None en listas solo si se quiere; acá los filtramos
            if sx is not None:
                out.append(sx)
        return out
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            sx = _sanitize_json(x)
            out[k] = sx  
        return out
    return v  

def _coerce_types(t: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(t)

    # listas
    et = out.get("etiquetas")
    if isinstance(et, str):
        et = [x.strip() for x in et.split(";") if x.strip()]
    out["etiquetas"] = et or []

    # checklist -> None si vacío
    cl = out.get("checklist")
    if not cl or (isinstance(cl, dict) and not cl.get("items")):
        out["checklist"] = None

    # fechas a ISO (YYYY-MM-DD)
    for k in ("fecha_creacion","fecha_vencimiento","fecha_finalizacion"):
        v = out.get(k)
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()

    # 🚿 sanitizar NaN/Infinity en TODO el payload
    for k, v in list(out.items()):
        out[k] = _sanitize_json(v)

    return out

def _payload_for_hash(t: Dict[str, Any]) -> Dict[str, Any]:
    # Solo campos comparables
    return {k: _normalize(t.get(k)) for k in COMPARE_FIELDS}

def _equal_rows(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return json.dumps(_payload_for_hash(a), sort_keys=True, ensure_ascii=False, default=str) == \
           json.dumps(_payload_for_hash(b), sort_keys=True, ensure_ascii=False, default=str)

def _chunks(lst, n=500):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def insertar_tareas(tareas: List[dict]) -> Tuple[int,int]:
    if not tareas:
        return (0,0)

    # normalizo tipos + sanitizo
    tareas = [_coerce_types(t) for t in tareas]

    # IDs únicos
    ids = list({t["id_tarea_planner"] for t in tareas if t.get("id_tarea_planner")})
    if not ids:
        return (0,0)

    # Traer existentes con TODAS las columnas comparables
    campos_select = "id,id_tarea_planner," + ",".join(COMPARE_FIELDS)
    existentes: Dict[str, Any] = {}
    for chunk in _chunks(ids, 400):
        res = _retry(lambda: supabase.table("tareas")
                     .select(campos_select)
                     .in_("id_tarea_planner", chunk)
                     .execute())
        for r in (res.data or []):
            existentes[r["id_tarea_planner"]] = r

    insertadas, actualizadas = 0, 0
    a_upsert: List[dict] = []

    for nueva in tareas:
        id_ = nueva["id_tarea_planner"]
        actual = existentes.get(id_)

        if not actual:
            insertadas += 1
            a_upsert.append(nueva)
            continue

        # comparar contenido (sin row_hash)
        if _equal_rows(nueva, actual):
            continue  

        upd = dict(nueva)
        upd["id"] = actual["id"]  
        actualizadas += 1
        a_upsert.append(upd)

    if not a_upsert:
        return (insertadas, actualizadas)

    for chunk in _chunks(a_upsert, 500):
        _retry(lambda: supabase.table("tareas")
               .upsert(chunk, on_conflict="id_tarea_planner")
               .execute())

    return (insertadas, actualizadas)

# -------- filtros / facetas (ajustado a columnas existentes) --------

def filtrar_tareas(
    estado: Optional[str]=None, prioridad: Optional[str]=None, colaborador: Optional[str]=None, tablero: Optional[str]=None,
    desde: Optional[str]=None, hasta: Optional[str]=None, q: Optional[str]=None, order_by: str="fecha_creacion",
    order_dir: str="desc", limit: int=100, offset: int=0,
    vencida: Optional[bool]=None,   
    vencimiento_desde: Optional[str]=None, vencimiento_hasta: Optional[str]=None,
    finalizacion_desde: Optional[str]=None, finalizacion_hasta: Optional[str]=None,
):
    def _split(v):
        return [x.strip() for x in v.split(",") if x.strip()] if v else None

    estados = _split(estado)
    prioridades = _split(prioridad)
    colaboradores = _split(colaborador)

    count_q = supabase.table("tareas").select("id", count="exact")
    qy = supabase.table("tareas").select("*")

    if estados: count_q = count_q.in_("estado", estados); qy = qy.in_("estado", estados)
    if prioridades: count_q = count_q.in_("prioridad", prioridades); qy = qy.in_("prioridad", prioridades)
    if colaboradores: count_q = count_q.in_("colaborador", colaboradores); qy = qy.in_("colaborador", colaboradores)
    if tablero: count_q = count_q.eq("nombre_tablero", tablero); qy = qy.eq("nombre_tablero", tablero)

    if desde: count_q = count_q.gte("fecha_creacion", desde); qy = qy.gte("fecha_creacion", desde)
    if hasta: count_q = count_q.lte("fecha_creacion", hasta); qy = qy.lte("fecha_creacion", hasta)

    estados = _split(estado)
    prioridades = _split(prioridad)
    colaboradores = _split(colaborador)

    qy = supabase.table("tareas").select("*", count="exact")

    if estados: qy = qy.in_("estado", estados)
    if prioridades: qy = qy.in_("prioridad", prioridades)
    if colaboradores: qy = qy.in_("colaborador", colaboradores)
    if tablero: qy = qy.eq("nombre_tablero", tablero)

    if desde: qy = qy.gte("fecha_creacion", desde)
    if hasta: qy = qy.lte("fecha_creacion", hasta)

    if vencimiento_desde: qy = qy.gte("fecha_vencimiento", vencimiento_desde)
    if vencimiento_hasta: qy = qy.lte("fecha_vencimiento", vencimiento_hasta)
    if finalizacion_desde: qy = qy.gte("fecha_finalizacion", finalizacion_desde)
    if finalizacion_hasta: qy = qy.lte("fecha_finalizacion", finalizacion_hasta)

    if q:
        like = f"%{q}%"
        qy = qy.or_(f"nombre_tarea.ilike.{like},descripcion.ilike.{like}")

    if order_by not in SAFE_ORDER_COLUMNS:
        order_by = "fecha_creacion"

    limit = max(1, min(1000, int(limit)))
    offset = max(0, int(offset))

    qy = qy.order(order_by, desc=(order_dir.lower() == "desc")).range(offset, offset + limit - 1)

    res = _retry(qy.execute)
    data = res.data or []
    total = res.count or 0
    return data, total


    if q:
        like = f"%{q}%"
        count_q = count_q.or_(f"nombre_tarea.ilike.{like},descripcion.ilike.{like}")
        qy = qy.or_(f"nombre_tarea.ilike.{like},descripcion.ilike.{like}")

    if order_by not in SAFE_ORDER_COLUMNS:
        order_by = "fecha_creacion"

    limit = max(1, min(1000, int(limit)))
    offset = max(0, int(offset))

    qy = qy.order(order_by, desc=(order_dir.lower() == "desc")).range(offset, offset + limit - 1)

    total = _retry(count_q.execute).count or 0
    data = _retry(qy.execute).data or []
    return data, total

def obtener_facetas() -> Dict[str, list]:
    cols = ["estado","prioridad","colaborador","nombre_tablero","etiquetas"]
    results: Dict[str, list] = {c: [] for c in cols}

    # Fetch all relevant columns in a single query
    res = _retry(lambda: supabase.table("tareas").select(",".join(cols)).execute())

    for row in res.data or []:
        for c in cols:
            v = row.get(c)
            if isinstance(v, list):
                results[c].extend(v)
            elif v is not None:
                results[c].append(v)

    # Process and sort unique values for each facet
    for c in cols:
        results[c] = sorted({str(x).strip() for x in results[c] if str(x).strip()})

    return results
