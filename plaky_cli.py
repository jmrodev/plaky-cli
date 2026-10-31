#!/usr/bin/env python3
"""
Plaky API Helper — Herramienta CLI para gestionar tareas en Plaky.
"""
import urllib.request
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
SPACE_ID = 222146

if not API_KEY:
    print("❌ PLAKY_API_KEY no encontrado. Verificá el .env en la raíz del proyecto.")
    sys.exit(1)

BOARDS = {
    "sababook": {
        "board_id": 276809,
        "backlog": 936975,
        "sprint_1": 936976,
        "sprint_2": 1016376,
        "done": 1016574,
    },
    "edutrack": {
        "board_id": 276810,
        "backlog": 936981,
        "sprint_1": 936982,
        "sprint_2": 1016377,
        "done": 1008842,
    },
}


def _request(method, url, payload=None):
    """Realiza una petición HTTP a la API de Plaky."""
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ HTTP {e.code}: {body}")
        return None


def _board_cfg(board_name):
    cfg = BOARDS.get(board_name.lower())
    if not cfg:
        print(f"Tablero desconocido: '{board_name}'. Usar: {', '.join(BOARDS)}")
    return cfg


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


# ── READ ────────────────────────────────────────────────────────────────────

def list_items(board_name, search=None):
    """Lista todos los ítems de un tablero. Filtra por texto si se pasa `search`."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    items = _fetch_all_items(cfg["board_id"])
    if search:
        items = [i for i in items if search.lower() in i["title"].lower()]
    if not items:
        print("Sin resultados.")
        return
    for item in items:
        status = next((f["value"] for f in item["fields"] if f["key"] == "status-1"), "-")
        print(f"  [{item['id']}] {item['title']}  (status={status}, comments={item['commentCount']})")


def list_unassigned(board_name, group_filter=None):
    """Lista las tarjetas que no tienen desarrollador asignado (Owner vacío).
    Permite filtrar opcionalmente por grupo/sprint (ej. 'Sprint 3', 'Backlog').
    """
    cfg = _board_cfg(board_name)
    if not cfg:
        return []

    # Obtiene nombres de los grupos del tablero
    board_data = _request("GET", f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}")
    group_names = {g["id"]: g["title"] for g in board_data.get("groups", [])} if board_data else {}

    # Obtiene items (con paginación)
    items = _fetch_all_items(cfg["board_id"])
    status_map = {"1": "Done", "2": "In Progress", "3": "Review", "4": "Stuck", "5": "For Refinement", "6": "Ready", "0": "None"}

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
                status_val = f.get("value", "0")

        if not assigned:
            st_text = status_map.get(status_val, status_val)
            unassigned.append({"id": item["id"], "title": item["title"], "group": gname, "status": st_text})

    print(f"\n📋 Tarjetas sin asignar en '{board_name}'" + (f" (filtro: {group_filter})" if group_filter else "") + f" — Total: {len(unassigned)}")
    if not unassigned:
        print("  🎉 Todas las tarjetas tienen un desarrollador asignado.")
    else:
        for u in unassigned:
            print(f"  [{u['group']}] ID:{u['id']} | Estado: {u['status']:<11} | {u['title']}")

    return unassigned


def get_item(board_name, item_id):
    """Muestra el detalle de un ítem por su ID."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}/items/{item_id}"
    item = _request("GET", url)
    if item is None:
        return
    print(f"\n📋 {item['title']}")
    print(f"   ID       : {item['id']}")
    print(f"   Creado   : {item['createdAt'][:10]}")
    print(f"   Comentarios: {item['commentCount']}")
    for field in item.get("fields", []):
        print(f"   {field['title']}: {field['value']}")


def get_comments(board_name, item_id):
    """Muestra los comentarios de un ítem."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}/items/{item_id}/comments"
    comments = _request("GET", url)
    if comments is None:
        return
    if not comments:
        print("Sin comentarios.")
        return
    for c in comments:
        print(f"\n  🗨  [{c.get('createdAt', '')[:10]}] {c.get('text', c)}")


# ── WRITE ───────────────────────────────────────────────────────────────────

USER_MARCELO = 494741

def create_item(board_name, title, group="sprint_2", owner_id=USER_MARCELO):
    """Crea un nuevo ítem en el tablero asignado a Marcelo por defecto en el Sprint activo más alto (sprint_2)."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}/items"
    group_id = cfg.get(group, cfg.get("sprint_2", cfg.get("sprint_1")))
    payload = {"title": title, "groupId": group_id}
    if owner_id:
        payload["assignedUserIds"] = [owner_id]
    result = _request("POST", url, payload)
    if result:
        item_id = result.get('id')
        print(f"✅ Tarea creada y asignada a Marcelo: {title} (ID: {item_id})")
        return item_id


def update_field(board_name, item_id, field_key, value):
    """Actualiza el valor de un campo específico de un ítem en Plaky."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return None
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}/items/{item_id}/fields/{field_key}"
    payload = {"value": value}
    result = _request("PATCH", url, payload)
    return result


def assign_item(board_name, item_id, user_id=USER_MARCELO):
    """Asigna un ítem a un usuario (Marcelo por defecto)."""
    val = {"users": [{"id": int(user_id)}], "teams": []}
    res = update_field(board_name, item_id, "person-1", val)
    if res:
        print(f"✅ Tarea {item_id} asignada al usuario {user_id}.")
    return res


def update_status(board_name, item_id, status_val):
    """Actualiza el campo de estado (status-1) en el tablero.
    Valores comunes:
      '1': Done
      '2': In Progress
      '3': Review
      '4': Stuck
      '5': For Refinement
      '6': Ready
    """
    res = update_field(board_name, item_id, "status-1", status_val)
    if res:
        print(f"✅ Estado de tarea {item_id} actualizado a {status_val}.")
    return res


def set_priority(board_name, item_id, priority):
    """Actualiza la prioridad (status-2) de la tarjeta.
    Valores: high (1), low (2), medium (3), none (0)
    """
    p_map = {"high": "1", "low": "2", "medium": "3", "none": "0"}
    val = p_map.get(priority.lower(), priority)
    res = update_field(board_name, item_id, "status-2", str(val))
    if res:
        print(f"✅ Prioridad de tarea {item_id} actualizada a {priority}.")
    return res


def set_story_points(board_name, item_id, points):
    """Establece los story points (number-1) de la tarjeta."""
    val = float(points) if "." in str(points) else int(points)
    res = update_field(board_name, item_id, "number-1", val)
    if res:
        print(f"✅ Story points de tarea {item_id} actualizados a {points}.")
    return res


def delete_item(board_name, item_id):
    """Elimina una tarea del tablero."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}/items/{item_id}"
    res = _request("DELETE", url)
    if res is not None:
        print(f"🗑️ Tarea {item_id} eliminada con éxito de {board_name}.")
    return res


def delete_comment(board_name, item_id, comment_id):
    """Elimina un comentario específico de una tarea."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}/items/{item_id}/comments/{comment_id}"
    res = _request("DELETE", url)
    if res is not None:
        print(f"🗑️ Comentario {comment_id} eliminado de la tarea {item_id}.")
    return res


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

    # Leer variables existentes si hay
    space_id = os.environ.get("PLAKY_SPACE_ID", "222146")
    user_id = os.environ.get("PLAKY_USER_ID", "494741")

    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("# Configuración global para Plaky CLI\n")
        f.write(f'PLAKY_API_KEY="{token}"\n')
        f.write(f'PLAKY_SPACE_ID="{space_id}"\n')
        f.write(f'PLAKY_USER_ID="{user_id}"\n')

    print(f"✅ Token guardado exitosamente en {cfg_path}")


def list_users():
    """Lista todos los usuarios del sistema con sus IDs, nombres y correos."""
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


def get_space(space_id=SPACE_ID):
    """Muestra información y configuración del espacio actual en Plaky."""
    url = f"https://api.plaky.com/v1/public/spaces/{space_id}"
    space = _request("GET", url)
    if not space:
        return
    print(f"\n🏢 Espacio: {space.get('title')} (ID: {space.get('id')})")
    print(f"   Tipo        : {space.get('kind')}")
    print(f"   Descripción : {space.get('description')}")
    print(f"   Por defecto : {space.get('defaultSpace')}")
    return space


def get_board(board_name):
    """Obtiene la configuración y estructura completa de un tablero (grupos y campos)."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}"
    board = _request("GET", url)
    if not board:
        return
    print(f"\n📊 Tablero: {board.get('title')} (ID: {board.get('id')})")
    print("\n📁 Grupos / Sprints:")
    for g in board.get("groups", []):
        print(f"   - {g.get('title'):<15} (ID: {g.get('id')})")
    print("\n🏷️ Campos configurados:")
    for f in board.get("fields", []):
        print(f"   - {f.get('name'):<15} (Key: {f.get('key'):<10} Tipo: {f.get('type')})")
    return board


def done_item(board_name, item_id):
    """Marca un ítem como Done (status 1)."""
    return update_status(board_name, item_id, "1")


def add_comment(board_name, item_id, text):
    """Agrega un comentario a un ítem en Plaky."""
    cfg = _board_cfg(board_name)
    if not cfg:
        return
    url = f"https://api.plaky.com/v1/public/spaces/{SPACE_ID}/boards/{cfg['board_id']}/items/{item_id}/comments"
    result = _request("POST", url, {"text": text})
    if result:
        print(f"✅ Comentario publicado en la tarea {item_id}.")
        return result


def set_status_comment(board_name, item_id, status_name, extra_text=""):
    """Publica un comentario formal de estado y actualiza el campo de estado en Plaky."""
    status_map = {
        "review": ("3", "🔍 IN REVIEW (Pendiente de aprobación por 2 revisores en GitHub)"),
        "stuck": ("4", "⚠️ STUCK (Trabajo detenido / Requiere desbloqueo)"),
        "refinement": ("5", "🛠 FOR REFINEMENT (En revisión y refinamiento de requerimientos)"),
        "ready": ("6", "🚀 READY FOR DEVELOPMENT (Listo para desarrollo)"),
        "done": ("1", "✅ DONE (Revisado, aprobado y completado)"),
        "progress": ("2", "⏳ IN PROGRESS (En desarrollo)")
    }
    st_info = status_map.get(status_name.lower())
    if st_info:
        st_val, header = st_info
        update_status(board_name, item_id, st_val)
    else:
        header = f"📌 ESTADO: {status_name.upper()}"

    msg = f"{header}\n{extra_text}".strip()
    return add_comment(board_name, item_id, msg)


# ── CLI ─────────────────────────────────────────────────────────────────────

USAGE = """
Uso: plaky <comando> [tablero] [args...]

Configuración y Autenticación:
  auth       [token]                    Guarda tu API Key de Plaky en ~/.config/plaky/config.env

Consultas de Sistema y Usuarios:
  users                                 Lista todos los usuarios (IDs, nombres y emails)
  space                                 Información del espacio de trabajo de Plaky

Consultas de Tablero e Ítems (READ):
  board      <tablero>                  Estructura del tablero (grupos y campos)
  list       <tablero> [texto]          Lista ítems (filtra por texto si se indica)
  unassigned <tablero> [grupo]          Lista tarjetas sin dev asignado (ej. "Sprint 1")
  get        <tablero> <item_id>        Detalle completo de un ítem
  comments   <tablero> <item_id>        Comentarios de un ítem

Acciones / Modificaciones (WRITE):
  create     <tablero> <título> [grupo] Crea un ítem asignado a Marcelo por defecto
  assign     <tablero> <item_id> [uid]  Asigna la tarjeta a un usuario (Marcelo por defecto)
  status     <tablero> <item_id> <review|stuck|refinement|ready|done|progress> [comentario/PR_link]
  priority   <tablero> <item_id> <high|medium|low|none> Establece prioridad
  points     <tablero> <item_id> <pts>  Asigna story points
  comment    <tablero> <item_id> <texto> Agrega un comentario a la tarea

Eliminación (DELETE):
  delete-item    <tablero> <item_id>    Elimina un ítem del tablero
  delete-comment <tablero> <item_id> <comment_id> Elimina un comentario

Tableros soportados: sababook, edutrack
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
    elif cmd == "space":
        get_space()
        sys.exit(0)

    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(0)

    board = sys.argv[2]

    if cmd == "board":
        get_board(board)
    elif cmd == "list":
        list_items(board, search=sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "unassigned":
        list_unassigned(board, group_filter=sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "get" and len(sys.argv) > 3:
        get_item(board, sys.argv[3])
    elif cmd == "comments" and len(sys.argv) > 3:
        get_comments(board, sys.argv[3])
    elif cmd == "create" and len(sys.argv) > 3:
        create_item(board, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "sprint_1")
    elif cmd == "assign" and len(sys.argv) > 3:
        assign_item(board, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else USER_MARCELO)
    elif cmd == "priority" and len(sys.argv) > 4:
        set_priority(board, sys.argv[3], sys.argv[4])
    elif cmd == "points" and len(sys.argv) > 4:
        set_story_points(board, sys.argv[3], sys.argv[4])
    elif cmd == "comment" and len(sys.argv) > 4:
        add_comment(board, sys.argv[3], sys.argv[4])
    elif cmd == "status" and len(sys.argv) > 4:
        set_status_comment(board, sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "")
    elif cmd == "done" and len(sys.argv) > 3:
        set_status_comment(board, sys.argv[3], "done", sys.argv[4] if len(sys.argv) > 4 else "")
    elif cmd == "delete-item" and len(sys.argv) > 3:
        delete_item(board, sys.argv[3])
    elif cmd == "delete-comment" and len(sys.argv) > 4:
        delete_comment(board, sys.argv[3], sys.argv[4])
    else:
        print(USAGE)
