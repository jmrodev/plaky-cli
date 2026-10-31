# 📌 Plaky CLI

CLI oficial independiente en Python para interactuar con la **API Pública de Plaky** (`https://api.plaky.com/v1/public`).

---

## 🚀 Instalación rápida

```bash
git clone https://github.com/jmrodev/plaky-cli.git
cd plaky-cli
./install.sh
```

El instalador:
1. Crea el binario ejecutable en `~/.local/bin/plaky`.
2. Genera la carpeta de configuración global en `~/.config/plaky/config.env`.

---

## ⚙️ Configuración

Puedes configurar tus credenciales de dos maneras:
1. **Global:** En `~/.config/plaky/config.env`
   ```env
   PLAKY_API_KEY="tu_api_key_aqui"
   PLAKY_SPACE_ID="222146"
   ```
2. **Local por proyecto:** En el archivo `.env` del directorio donde estés parado.

---

## 📖 Uso

```bash
# Consultar usuarios y espacio
plaky users
plaky space

# Ver tablero y listar tareas
plaky board sababook
plaky list sababook [filtro]
plaky unassigned sababook [grupo]
plaky get sababook <item_id>
plaky comments sababook <item_id>

# Crear y modificar
plaky create sababook "SAB-XX Tarea nueva" [sprint_1|sprint_2|backlog]
plaky assign sababook <item_id> [user_id]
plaky status sababook <item_id> <review|progress|stuck|refinement|ready|done> [comentario/PRs]
plaky priority sababook <item_id> <high|medium|low|none>
plaky points sababook <item_id> <pts>
plaky comment sababook <item_id> "Texto"

# Eliminar
plaky delete-item sababook <item_id>
plaky delete-comment sababook <item_id> <comment_id>
```
