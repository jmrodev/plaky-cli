#!/usr/bin/env python3
"""
Plaky CLI — Herramienta CLI universal para la API Pública de Plaky (https://api.plaky.com/v1/public).
Soporta resolución dinámica de espacios, tableros y grupos (por ID o por nombre),
además de alias rápidos configurables.
"""
import urllib.request
import urllib.error
import json
import os
import sys

def _load_env():
    """Carga variables desde .env local, o desde ~/.config/plaky/config.env."""
    paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.expanduser("~"), ".config", "plaky", "config.env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    ]
    for env_path in paths:
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()

API_KEY = os.environ.get("PLAKY_API_KEY", "")
SPACE_ID = os.environ.get("PLAKY_SPACE_ID", "222146")
USER_DEFAULT = os.environ.get("PLAKY_USER_ID", "494741")

STATUS_MAP = {
    "1": "Done",
    "2": "In Progress",
    "3": "Review",
    "4": "Stuck",
    "5": "For Refinement",
    "6": "Ready for development",
    "0": "None"
}

PRIORITY_MAP = {
    "1": "High",
    "2": "Low",
    "3": "Medium",
    "0": "None"
}

# Cache de tableros resueltos dinámicamente
_BOARDS_CACHE = {}


def _request(method, url, payload=None):
    """Realiza una petición HTTP a la API de Plaky manejando respuestas con o sin cuerpo."""
    if not API_KEY and not (len(sys.argv) > 1 and sys.argv[1].lower() == "auth"):
        print("❌ PLAKY_API_KEY no encontrado. Ejecutá 'plaky auth <tu_api_key>' para configurarlo.")
        sys.exit(1)

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            if not content.strip():
                return {}
            return json.loads(content)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ HTTP {e.code}: {body}")
        return None


def get_all_boards():
    """Obtiene dinámicamente todos los tableros del espacio de Plaky."""
    global _BOARDS_CACHE
    if _BOARDS_CACHE:
        return _BOARDS_CACHE
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards"
    res = _request("GET", url)
    if not res:
        return []
    boards = res if isinstance(res, list) else res.get("data", res.get("boards", []))
    _BOARDS_CACHE = boards
    return boards


def resolve_board(board_input):
    """Resuelve un tablero dinámicamente: acepta ID numérico, nombre parcial o alias."""
    board_str = str(board_input).strip()
    
    # Alias conocidos por conveniencia
    alias_map = {
        "sababook": 276809,
        "edutrack": 276810,
        "crm": 276810,
        "edu": 303772
    }
    target_id = alias_map.get(board_str.lower())
    if target_id:
        board_str = str(target_id)

    # Si es numérico
    if board_str.isdigit():
        url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board_str}"
        b = _request("GET", url)
        if b:
            return b

    # Si es por búsqueda de nombre
    boards = get_all_boards()
    for b in boards:
        if board_str.lower() in b.get("title", "").lower():
            # Obtener detalle completo
            url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{b.get('id')}"
            return _request("GET", url)

    print(f"❌ Tablero no encontrado: '{board_input}'. Usá 'plaky boards' para listar los disponibles.")
    return None


def _fetch_all_items(board_id):
    """Obtiene todos los ítems de un tablero manejando paginación."""
    page = 1
    all_items = []
    while True:
        url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board_id}/items?page={page}"
        result = _request("GET", url)
        if not result:
            break
        items = result if isinstance(result, list) else result.get("data", [])
        if not items:
            break
        all_items.extend(items)
        if isinstance(result, dict) and not result.get("hasMore"):
            break
        page += 1
    return all_items


# ── CONFIG / AUTH ───────────────────────────────────────────────────────────

def set_auth(token=None):
    """Guarda o actualiza la API Key de Plaky de forma global en ~/.config/plaky/config.env."""
    if not token:
        if len(sys.argv) > 2:
            token = sys.argv[2]
        else:
            token = input("Introduce tu PLAKY_API_KEY: ").strip()

    if not token:
        print("❌ Token vacío.")
        return

    cfg_dir = os.path.join(os.path.expanduser("~"), ".config", "plaky")
    os.makedirs(cfg_dir, exist_ok=True)
    cfg_path = os.path.join(cfg_dir, "config.env")

    space_id = os.environ.get("PLAKY_SPACE_ID", "222146")
    user_id = os.environ.get("PLAKY_USER_ID", USER_DEFAULT)

    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("# Configuración global para Plaky CLI\n")
        f.write(f'PLAKY_API_KEY="{token}"\n')
        f.write(f'PLAKY_SPACE_ID="{space_id}"\n')
        f.write(f'PLAKY_USER_ID="{user_id}"\n')

    print(f"✅ Token guardado exitosamente en {cfg_path}")


# ── SISTEMA Y USUARIOS ─────────────────────────────────────────────────────

def list_users():
    """Lista todos los usuarios del workspace con sus IDs, nombres y correos."""
    url = "https://api.plaky.com/v1/public/users"
    users = _request("GET", url)
    if not users:
        print("No se pudieron obtener usuarios.")
        return []
    data = users if isinstance(users, list) else users.get("data", [])
    print(f"\n👥 Usuarios registrados en Plaky ({len(data)} usuarios):")
    print(f"   {'ID':<8} | {'Usuario / Nombre':<30} | {'Email'}")
    print("   " + "-" * 75)
    for u in data:
        name = u.get("name") or u.get("fullName") or u.get("username") or "-"
        print(f"   {u.get('id'):<8} | {name:<30} | {u.get('email', '')}")
    return data


def list_spaces():
    """Lista los espacios disponibles en la cuenta."""
    url = "https://api.plaky.com/v1/public/spaces"
    res = _request("GET", url)
    if not res:
        return []
    data = res if isinstance(res, list) else res.get("data", [])
    print(f"\n🏢 Espacios disponibles ({len(data)}):")
    for s in data:
        print(f"   - [{s.get('id')}] {s.get('title')} (Por defecto: {s.get('defaultSpace')})")
    return data


def get_space(space_id=SPACE_ID):
    """Muestra información del espacio actual de trabajo."""
    url = f"https://api.plaky.com/v1/public/spaces/{space_id}"
    space = _request("GET", url)
    if not space:
        return
    print(f"\n🏢 Espacio activo: {space.get('title')} (ID: {space.get('id')})")
    print(f"   Tipo        : {space.get('kind')}")
    print(f"   Descripción : {space.get('description')}")
    print(f"   Por defecto : {space.get('defaultSpace')}")
    return space


def list_boards():
    """Lista dinámicamente todos los tableros del espacio."""
    boards = get_all_boards()
    print(f"\n📊 Tableros disponibles en el espacio ({len(boards)}):")
    print(f"   {'ID':<10} | {'Título del Tablero'}")
    print("   " + "-" * 50)
    for b in boards:
        print(f"   {b.get('id'):<10} | {b.get('title')}")
    return boards


# ── TABLEROS E ÍTEMS (READ) ────────────────────────────────────────────────

def get_board(board_input):
    """Muestra la estructura completa de un tablero (grupos y campos)."""
    board = resolve_board(board_input)
    if not board:
        return
    print(f"\n📊 Tablero: {board.get('title')} (ID: {board.get('id')})")
    print("\n📁 Grupos / Sprints:")
    for g in board.get("groups", []):
        print(f"   - {g.get('title'):<20} (ID: {g.get('id')})")
    print("\n🏷️ Campos configurados:")
    for f in board.get("fields", []):
        print(f"   - {f.get('name'):<18} (Key: {f.get('key'):<10} Tipo: {f.get('type')})")
    return board


def list_items(board_input, search=None):
    """Lista todos los ítems de un tablero. Filtra por texto si se indica."""
    board = resolve_board(board_input)
    if not board:
        return
    items = _fetch_all_items(board.get("id"))
    if search:
        items = [i for i in items if search.lower() in i.get("title", "").lower()]
    if not items:
        print("Sin resultados.")
        return
    print(f"\n📋 Ítems en '{board.get('title')}' ({len(items)}):")
    for item in items:
        status = next((f["value"] for f in item.get("fields", []) if f["key"] == "status-1"), "-")
        st_name = STATUS_MAP.get(str(status), str(status))
        print(f"  [{item['id']}] {item['title']}  (status={st_name}, comments={item.get('commentCount', 0)})")


def list_unassigned(board_input, group_filter=None):
    """Lista las tarjetas que no tienen desarrollador asignado."""
    board = resolve_board(board_input)
    if not board:
        return []
    group_names = {g["id"]: g["title"] for g in board.get("groups", [])}
    items = _fetch_all_items(board.get("id"))

    unassigned = []
    for item in items:
        gid = item.get("group", {}).get("id") if isinstance(item.get("group"), dict) else item.get("group")
        gname = group_names.get(gid, f"Grupo {gid}")
        if group_filter and group_filter.lower() not in gname.lower():
            continue
        assigned = []
        status_val = "0"
        for f in item.get("fields", []):
            if f.get("key") == "person-1":
                val = f.get("value")
                if isinstance(val, dict):
                    assigned = val.get("assignedUsers", [])
            elif f.get("key") == "status-1":
                status_val = str(f.get("value", "0"))

        if not assigned:
            st_text = STATUS_MAP.get(status_val, status_val)
            unassigned.append({"id": item["id"], "title": item["title"], "group": gname, "status": st_text})

    print(f"\n📋 Tarjetas sin asignar en '{board.get('title')}'" + (f" (filtro: {group_filter})" if group_filter else "") + f" — Total: {len(unassigned)}")
    if not unassigned:
        print("  🎉 Todas las tarjetas tienen un desarrollador asignado.")
    else:
        for u in unassigned:
            print(f"  [{u['group']}] ID:{u['id']} | Estado: {u['status']:<15} | {u['title']}")
    return unassigned


def get_item(board_input, item_id):
    """Muestra el detalle completo de un ítem por su ID."""
    board = resolve_board(board_input)
    if not board:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board.get('id')}/items/{item_id}"
    item = _request("GET", url)
    if item is None:
        return
    print(f"\n📋 {item.get('title')}")
    print(f"   ID         : {item.get('id')}")
    print(f"   Tablero    : {board.get('title')} ({board.get('id')})")
    print(f"   Grupo ID   : {item.get('group')}")
    print(f"   Creado     : {str(item.get('createdAt', ''))[:10]}")
    print(f"   Comentarios: {item.get('commentCount', 0)}")
    for field in item.get("fields", []):
        fkey = field.get("key")
        val = field.get("value")
        if fkey == "status-1":
            val = f"{val} ({STATUS_MAP.get(str(val), 'Desconocido')})"
        elif fkey == "status-2":
            val = f"{val} ({PRIORITY_MAP.get(str(val), 'Desconocido')})"
        print(f"   {field.get('title', fkey):<15}: {val}")
    return item


def get_comments(board_input, item_id):
    """Muestra los comentarios de un ítem."""
    board = resolve_board(board_input)
    if not board:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board.get('id')}/items/{item_id}/comments"
    comments = _request("GET", url)
    if comments is None:
        return
    if not comments:
        print("Sin comentarios.")
        return
    for c in comments:
        cid = c.get('id')
        print(f"\n  🗨  [ID:{cid}] [{str(c.get('createdAt', ''))[:10]}] {c.get('text', c.get('content', ''))}")
    return comments


# ── ACCIONES Y MODIFICACIONES (WRITE) ──────────────────────────────────────

def create_item(board_input, title, group_input="sprint_1", owner_id=USER_DEFAULT):
    """Crea un nuevo ítem en un tablero en cualquier grupo/sprint."""
    board = resolve_board(board_input)
    if not board:
        return
    groups = board.get("groups", [])
    group_id = None
    
    # Resolver grupo por ID o por nombre
    if str(group_input).isdigit():
        group_id = int(group_input)
    else:
        for g in groups:
            if group_input.lower() in g.get("title", "").lower():
                group_id = g.get("id")
                break
    
    # Fallback al primer grupo
    if not group_id and groups:
        group_id = groups[0].get("id")

    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board.get('id')}/items"
    payload = {"title": title, "groupId": group_id}
    if owner_id:
        payload["assignedUserIds"] = [int(owner_id)]
    result = _request("POST", url, payload)
    if result:
        item_id = result.get('id')
        print(f"✅ Tarea creada: {title} (ID: {item_id}) en grupo {group_id}")
        return item_id


def update_field(board_input, item_id, field_key, value):
    """Actualiza el valor de un campo específico."""
    board = resolve_board(board_input)
    if not board:
        return None
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board.get('id')}/items/{item_id}/fields/{field_key}"
    payload = {"value": value}
    result = _request("PATCH", url, payload)
    return result


def assign_item(board_input, item_id, user_id=USER_DEFAULT):
    """Asigna la tarjeta a un usuario por ID."""
    val = {"users": [{"id": int(user_id)}], "teams": []}
    res = update_field(board_input, item_id, "person-1", val)
    if res:
        print(f"✅ Tarea {item_id} asignada al usuario {user_id}.")
    return res


def set_priority(board_input, item_id, priority):
    """Actualiza la prioridad (status-2) de la tarjeta."""
    p_map = {"high": "1", "low": "2", "medium": "3", "none": "0"}
    val = p_map.get(priority.lower(), priority)
    res = update_field(board_input, item_id, "status-2", str(val))
    if res:
        print(f"✅ Prioridad de tarea {item_id} actualizada a {PRIORITY_MAP.get(str(val), val)}.")
    return res


def set_story_points(board_input, item_id, points):
    """Establece los story points (number-1) de la tarjeta."""
    val = float(points) if "." in str(points) else int(points)
    res = update_field(board_input, item_id, "number-1", val)
    if res:
        print(f"✅ Story points de tarea {item_id} actualizados a {points}.")
    return res


def set_tags(board_input, item_id, tag_names_csv):
    """Asigna etiquetas/tags por nombre (ej: 'Backend,Feature' o 'Bug')."""
    board = resolve_board(board_input)
    if not board:
        return
    tag_field = next((f for f in board.get("fields", []) if f.get("type") == "TAG"), None)
    if not tag_field:
        print("❌ Este tablero no tiene un campo de tipo TAG.")
        return

    available_tags = tag_field.get("configuration", {}).get("values", [])
    tag_map = {t["title"].lower(): t["key"] for t in available_tags}
    
    selected_keys = []
    for name in tag_names_csv.split(","):
        n = name.strip().lower()
        if n in tag_map:
            selected_keys.append(tag_map[n])
        else:
            print(f"⚠️ Etiqueta '{name}' no existe en este tablero. Opciones: {', '.join(tag_map.keys())}")

    res = update_field(board_input, item_id, tag_field["key"], selected_keys)
    if res:
        print(f"✅ Etiquetas actualizadas para {item_id}: {tag_names_csv}")
    return res


def update_status(board_input, item_id, status_val):
    """Actualiza el estado visual (status-1) en el tablero."""
    res = update_field(board_input, item_id, "status-1", str(status_val))
    if res:
        print(f"✅ Estado de tarea {item_id} actualizado a {STATUS_MAP.get(str(status_val), status_val)}.")
    return res


def done_item(board_input, item_id):
    """Marca un ítem directamente como Done (status 1)."""
    return update_status(board_input, item_id, "1")


def add_comment(board_input, item_id, text):
    """Agrega un comentario a un ítem en Plaky."""
    board = resolve_board(board_input)
    if not board:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board.get('id')}/items/{item_id}/comments"
    result = _request("POST", url, {"text": text})
    if result:
        print(f"✅ Comentario publicado en la tarea {item_id}.")
        return result


def set_status_comment(board_input, item_id, status_name, extra_text=""):
    """Publica un comentario formal de estado y actualiza el campo de estado en Plaky."""
    status_dict = {
        "review": ("3", "🔍 IN REVIEW (Pendiente de aprobación por 2 revisores en GitHub)"),
        "stuck": ("4", "⚠️ STUCK (Trabajo detenido / Requiere desbloqueo)"),
        "refinement": ("5", "🛠 FOR REFINEMENT (En revisión y refinamiento de requerimientos)"),
        "ready": ("6", "🚀 READY FOR DEVELOPMENT (Listo para desarrollo)"),
        "done": ("1", "✅ DONE (Revisado, aprobado y completado)"),
        "progress": ("2", "⏳ IN PROGRESS (En desarrollo)")
    }
    st_info = status_dict.get(status_name.lower())
    if st_info:
        st_val, header = st_info
        update_status(board_input, item_id, st_val)
    else:
        header = f"📌 ESTADO: {status_name.upper()}"

    msg = f"{header}\n{extra_text}".strip()
    return add_comment(board_input, item_id, msg)


# ── ELIMINACIÓN (DELETE) ────────────────────────────────────────────────────

def delete_item(board_input, item_id):
    """Elimina una tarea del tablero."""
    board = resolve_board(board_input)
    if not board:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board.get('id')}/items/{item_id}"
    res = _request("DELETE", url)
    if res is not None:
        print(f"🗑️ Tarea {item_id} eliminada con éxito de {board.get('title')}.")
    return res


def delete_comment(board_input, item_id, comment_id):
    """Elimina un comentario específico de una tarea."""
    board = resolve_board(board_input)
    if not board:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{board.get('id')}/items/{item_id}/comments/{comment_id}"
    res = _request("DELETE", url)
    if res is not None:
        print(f"🗑️ Comentario {comment_id} eliminado de la tarea {item_id}.")
    return res


# ── CLI ENTRYPOINT ──────────────────────────────────────────────────────────

USAGE = """
Uso: plaky <comando> [tablero] [args...]

Configuración y Autenticación:
  auth       [token]                     Guarda tu API Key de Plaky en ~/.config/plaky/config.env

Consultas de Sistema, Espacios y Tableros:
  spaces                                 Lista los espacios disponibles
  space      [space_id]                  Detalle del espacio activo
  boards                                 Lista todos los tableros disponibles dinámicamente
  users                                  Lista todos los usuarios (IDs, nombres y emails)

Consultas de Tablero e Ítems (READ):
  board      <tablero>                   Estructura del tablero (grupos, sprints y campos)
  list       <tablero> [texto]           Lista ítems (filtra por texto si se indica)
  unassigned <tablero> [grupo]           Lista tarjetas sin dev asignado (ej. "Sprint 1")
  get        <tablero> <item_id>         Detalle completo de un ítem
  comments   <tablero> <item_id>         Comentarios de un ítem

Acciones / Modificaciones (WRITE):
  create     <tablero> <título> [grupo]  Crea un ítem (ej. en "Backlog", "Sprint 1", etc.)
  assign     <tablero> <item_id> [uid]   Asigna la tarjeta a un usuario por ID
  status     <tablero> <item_id> <review|stuck|refinement|ready|done|progress> [comentario/PR_link]
  priority   <tablero> <item_id> <high|medium|low|none> Establece prioridad
  tags       <tablero> <item_id> <tag1,tag2> Asigna etiquetas por nombre (ej: "Backend,Feature")
  points     <tablero> <item_id> <pts>   Asigna story points
  comment    <tablero> <item_id> <texto> Agrega un comentario a la tarea

Eliminación (DELETE):
  delete-item    <tablero> <item_id>     Elimina un ítem del tablero
  delete-comment <tablero> <item_id> <comment_id> Elimina un comentario específico

Nota sobre <tablero>:
  Podés usar el ID numérico (ej. 276809, 303772), su nombre (ej. "edu", "crm")
  o los alias automáticos ("sababook", "edutrack").
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "auth":
        set_auth(sys.argv[2] if len(sys.argv) > 2 else None)
        sys.exit(0)
    elif cmd == "users":
        list_users()
        sys.exit(0)
    elif cmd == "spaces":
        list_spaces()
        sys.exit(0)
    elif cmd == "space":
        get_space(sys.argv[2] if len(sys.argv) > 2 else SPACE_ID)
        sys.exit(0)
    elif cmd == "boards":
        list_boards()
        sys.exit(0)

    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(0)

    board_arg = sys.argv[2]

    if cmd == "board":
        get_board(board_arg)
    elif cmd == "list":
        list_items(board_arg, search=sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "unassigned":
        list_unassigned(board_arg, group_filter=sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "get" and len(sys.argv) > 3:
        get_item(board_arg, sys.argv[3])
    elif cmd == "comments" and len(sys.argv) > 3:
        get_comments(board_arg, sys.argv[3])
    elif cmd == "create" and len(sys.argv) > 3:
        create_item(board_arg, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "sprint_1")
    elif cmd == "assign" and len(sys.argv) > 3:
        assign_item(board_arg, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else USER_DEFAULT)
    elif cmd == "priority" and len(sys.argv) > 4:
        set_priority(board_arg, sys.argv[3], sys.argv[4])
    elif cmd == "tags" and len(sys.argv) > 4:
        set_tags(board_arg, sys.argv[3], sys.argv[4])
    elif cmd == "points" and len(sys.argv) > 4:
        set_story_points(board_arg, sys.argv[3], sys.argv[4])
    elif cmd == "comment" and len(sys.argv) > 4:
        add_comment(board_arg, sys.argv[3], sys.argv[4])
    elif cmd == "status" and len(sys.argv) > 4:
        set_status_comment(board_arg, sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "")
    elif cmd == "done" and len(sys.argv) > 3:
        set_status_comment(board_arg, sys.argv[3], "done", sys.argv[4] if len(sys.argv) > 4 else "")
    elif cmd == "delete-item" and len(sys.argv) > 3:
        delete_item(board_arg, sys.argv[3])
    elif cmd == "delete-comment" and len(sys.argv) > 4:
        delete_comment(board_arg, sys.argv[3], sys.argv[4])
    else:
        print(USAGE)
