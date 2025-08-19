import pandas as pd
from typing import List, Any, Dict
from datetime import datetime, date
from io import BytesIO

# Estados canónicos para la UI / backend
ESTADO_MAP = {
    "No iniciado": "No iniciado",
    "Informado": "En curso",                # tratar "Informado" como "En curso" si aplica
    "En curso": "En curso",
    "En procesos": "En curso",              # normalizar
    "Completado": "Implementado",           # Planner → tablero
    "Implementado": "Implementado",
    "Efectividad verificada": "Efectividad verificada",
    "No efectivo": "No efectivo",
}

# ----------------- Helpers -----------------

def _safe_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        return dt.date() if pd.notna(dt) else None
    except Exception:
        return None

def _limpiar_lista(val: Any) -> list:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    if isinstance(val, list):
        items = [str(x).strip() for x in val]
    else:
        items = [x.strip() for x in str(val).split(";")]
    return sorted({x for x in items if x})

def _norm(s: str) -> str:
    return (
        s.lower()
         .replace("\xa0", " ")
         .strip()
         .translate(str.maketrans("áéíóúñ", "aeioun"))
         .replace("°", "")
         .replace(".", "")
         .replace("-", " ")
    )

def _build_renames(cols: list[str]) -> Dict[str, str]:
    """Renombra cabeceras de Planner/canónicas a nombres canónicos de la tabla."""
    syn: Dict[str, str] = {}
    def add(canon: str, *aliases: str):
        for a in aliases + (canon,):
            syn[_norm(a)] = canon

    add("id_tarea_planner", "Id. de tarea", "id de tarea", "id tarea", "id_tarea", "id")
    add("estado", "Progreso", "Estado")
    add("fecha_creacion", "Fecha de creación", "fecha de creacion")
    add("fecha_vencimiento", "Fecha de vencimiento", "vencimiento", "due date")
    add("fecha_finalizacion", "Fecha de finalización", "fecha de finalizacion")
    add("nombre_tarea", "Nombre de la tarea", "titulo", "título")
    add("descripcion", "Descripción", "descripcion", "description")
    import pandas as pd
from typing import List, Any, Dict
from datetime import datetime, date
from io import BytesIO

# Estados canónicos para la UI / backend
ESTADO_MAP = {
    "No iniciado": "No iniciado",
    "Informado": "En curso",                # tratar "Informado" como "En curso" si aplica
    "En curso": "En curso",
    "En procesos": "En curso",              # normalizar
    "Completado": "Implementado",           # Planner → tablero
    "Implementado": "Implementado",
    "Efectividad verificada": "Efectividad verificada",
    "No efectivo": "No efectivo",
}

# ----------------- Helpers -----------------

def _limpiar_lista_vec(series: pd.Series) -> pd.Series:
    return series.astype(str).apply(lambda x: sorted(list(set([item.strip() for item in x.split(';') if item.strip()]))))

def _norm(s: str) -> str:
    return (
        s.lower()
         .replace("\xa0", " ")
         .strip()
         .translate(str.maketrans("áéíóúñ", "aeioun"))
         .replace("°", "")
         .replace(".", "")
         .replace("-", " ")
    )

def _build_renames(cols: list[str]) -> Dict[str, str]:
    """Renombra cabeceras de Planner/canónicas a nombres canónicos de la tabla."""
    syn: Dict[str, str] = {}
    def add(canon: str, *aliases: str):
        for a in aliases + (canon,):
            syn[_norm(a)] = canon

    add("id_tarea_planner", "Id. de tarea", "id de tarea", "id tarea", "id_tarea", "id")
    add("estado", "Progreso", "Estado")
    add("fecha_creacion", "Fecha de creación", "fecha de creacion")
    add("fecha_vencimiento", "Fecha de vencimiento", "vencimiento", "due date")
    add("fecha_finalizacion", "Fecha de finalización", "fecha de finalizacion")
    add("nombre_tarea", "Nombre de la tarea", "titulo", "título")
    add("descripcion", "Descripción", "descripcion", "description")
    add("colaborador", "Asignado a", "asignado a")   # 👈 clave
    add("creado_por", "Creado por")
    add("completado_por", "Completado por")
    add("etiquetas", "Etiquetas")
    add("checklist_items", "Elementos de la lista de comprobación", "elementos de la lista de comprobacion", "checklist")
    add("prioridad", "Priority", "Prioridad")
    add("nombre_tablero", "Nombre del depósito", "Nombre del deposito", "tablero")

    ren: Dict[str, str] = {}
    for c in cols:
        key = _norm(str(c))
        if key in syn:
            ren[c] = syn[key]
    return ren

# ----------------- Parser -----------------

def procesar_excel(file) -> List[dict]:
    content = file.file.read()
    df = pd.read_excel(BytesIO(content))
    df.columns = [str(c).strip().replace("\xa0", " ") for c in df.columns]

    renames = _build_renames(list(df.columns))
    if renames:
        df = df.rename(columns=renames)

    print("🧭 Columnas (renombradas si aplica):", df.columns.tolist())

    # Filter out rows with empty 'id_tarea_planner'
    df = df[df['id_tarea_planner'].notna() & (df['id_tarea_planner'].astype(str).str.strip() != '')].copy()
    df['id_tarea_planner'] = df['id_tarea_planner'].astype(str).str.strip()

    # Vectorize date parsing
    for col in ["fecha_creacion", "fecha_vencimiento", "fecha_finalizacion"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True).dt.date

    # Vectorize status mapping
    if 'estado' in df.columns:
        df['estado'] = df['estado'].astype(str).str.strip().map(ESTADO_MAP).fillna(df['estado'])

    # Vectorize collaborator
    if 'colaborador' in df.columns:
        df['colaborador'] = df['colaborador'].astype(str).str.strip().replace('', 'Sin asignar').fillna('Sin asignar')
    else:
        df['colaborador'] = 'Sin asignar'

    # Vectorize list cleaning for 'etiquetas' and 'checklist_items'
    if 'etiquetas' in df.columns:
        df['etiquetas'] = _limpiar_lista_vec(df['etiquetas'])
    else:
        df['etiquetas'] = [[]] * len(df)

    if 'checklist_items' in df.columns:
        df['checklist'] = _limpiar_lista_vec(df['checklist_items']).apply(lambda x: {'items': x} if x else None)
    else:
        df['checklist'] = [None] * len(df)

    hoy = date.today()

    # Vectorize 'cerrada' and 'vencida' calculation
    df['cerrada'] = df['estado'].isin(["Implementado", "Efectividad verificada", "No efectivo"])
    df['vencida_calc'] = ((df['fecha_vencimiento'].notna()) & (hoy > df['fecha_vencimiento']) & (~df['cerrada']))

    # Handle 'retrasada' column
    if 'retrasada' in df.columns:
        df['retrasada'] = df['retrasada'].fillna(False).astype(bool) | df['vencida_calc']
    else:
        df['retrasada'] = df['vencida_calc']

    # Select and rename columns to match the expected output dictionary structure
    # Ensure all expected keys are present, even if they are None
    output_columns = {
        "id_tarea_planner": "id_tarea_planner",
        "nombre_tarea": "nombre_tarea",
        "descripcion": "descripcion",
        "colaborador": "colaborador",
        "creado_por": "creado_por",
        "estado": "estado",
        "prioridad": "prioridad",
        "fecha_creacion": "fecha_creacion",
        "fecha_vencimiento": "fecha_vencimiento",
        "fecha_finalizacion": "fecha_finalizacion",
        "completado_por": "completado_por",
        "etiquetas": "etiquetas",
        "checklist": "checklist",
        "retrasada": "retrasada",
        "nombre_tablero": "nombre_tablero",
    }

    # Ensure all output_columns are present in df, add as None if missing
    for col_df, col_out in output_columns.items():
        if col_df not in df.columns:
            df[col_df] = None

    # Convert DataFrame to list of dictionaries
    tareas = df[list(output_columns.keys())].to_dict(orient='records')

    print("🧾 Filas construidas:", len(tareas))
    return tareas
    add("creado_por", "Creado por")
    add("completado_por", "Completado por")
    add("etiquetas", "Etiquetas")
    add("checklist_items", "Elementos de la lista de comprobación", "elementos de la lista de comprobacion", "checklist")
    add("prioridad", "Priority", "Prioridad")
    add("nombre_tablero", "Nombre del depósito", "Nombre del deposito", "tablero")

    ren: Dict[str, str] = {}
    for c in cols:
        key = _norm(str(c))
        if key in syn:
            ren[c] = syn[key]
    return ren

def _obtener_colaborador(row: pd.Series) -> str:
    v = row.get("colaborador")  # ya renombrado desde "Asignado a"
    if pd.notna(v) and str(v).strip():
        return str(v).strip()
    return "Sin asignar"

# ----------------- Parser -----------------

def procesar_excel(file) -> List[dict]:
    content = file.file.read()
    df = pd.read_excel(BytesIO(content))
    df.columns = [str(c).strip().replace("\xa0", " ") for c in df.columns]

    renames = _build_renames(list(df.columns))
    if renames:
        df = df.rename(columns=renames)

    print("🧭 Columnas (renombradas si aplica):", df.columns.tolist())

    hoy = date.today()
    tareas: List[dict] = []

    for _, row in df.iterrows():
        id_tarea = row.get("id_tarea_planner")
        if pd.isna(id_tarea) or not str(id_tarea).strip():
            continue

        estado_in = str(row.get("estado")).strip() if pd.notna(row.get("estado")) else None
        estado_tablero = ESTADO_MAP.get(estado_in, estado_in)

        fecha_creacion     = _safe_date(row.get("fecha_creacion"))
        fecha_vencimiento  = _safe_date(row.get("fecha_vencimiento"))
        fecha_finalizacion = _safe_date(row.get("fecha_finalizacion"))

        etiquetas = _limpiar_lista(row.get("etiquetas"))
        checklist_items = _limpiar_lista(row.get("checklist_items"))

        cerrada = estado_tablero in ("Implementado", "Efectividad verificada", "No efectivo")
        vencida = bool(fecha_vencimiento and (hoy > fecha_vencimiento) and not cerrada)

        # ⚠️ SOLO columnas que existen en la tabla
        tareas.append({
            "id_tarea_planner": str(id_tarea).strip(),
            "nombre_tarea": row.get("nombre_tarea"),
            "descripcion": row.get("descripcion"),
            "colaborador": _obtener_colaborador(row),
            "creado_por": row.get("creado_por"),
            "estado": estado_tablero,
            "prioridad": row.get("prioridad"),
            "fecha_creacion": fecha_creacion,
            "fecha_vencimiento": fecha_vencimiento,
            "fecha_finalizacion": fecha_finalizacion,
            "completado_por": row.get("completado_por"),
            "etiquetas": etiquetas,
            "checklist": {"items": checklist_items} if checklist_items else None,
            "retrasada": bool(row.get("retrasada")) if pd.notna(row.get("retrasada")) else vencida,
            "nombre_tablero": row.get("nombre_tablero"),
        })

    print("🧾 Filas construidas:", len(tareas))
    return tareas
