#!/usr/bin/env bash
set -e

INSTALL_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/plaky"
SCRIPT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/plaky_cli.py"

echo "🚀 Instalando Plaky CLI..."

# 1. Asegurar directorios
mkdir -p "${INSTALL_DIR}"
mkdir -p "${CONFIG_DIR}"

# 2. Configurar archivo de credenciales si no existe
if [ ! -f "${CONFIG_DIR}/config.env" ]; then
    echo "⚙️ Creando plantilla de configuración en ${CONFIG_DIR}/config.env..."
    cat << 'ENVEOF' > "${CONFIG_DIR}/config.env"
# Configuración global para Plaky CLI
PLAKY_API_KEY=""
PLAKY_SPACE_ID="222146"
PLAKY_USER_ID="494741"
ENVEOF
    echo "⚠️ Recuerda agregar tu PLAKY_API_KEY en ${CONFIG_DIR}/config.env si no usas .env local."
fi

# 3. Crear ejecutable wrapper en ~/.local/bin/plaky
cat << WRAPPEREOF > "${INSTALL_DIR}/plaky"
#!/usr/bin/env bash
python3 "${SCRIPT_SRC}" "\$@"
WRAPPEREOF

chmod +x "${INSTALL_DIR}/plaky"
chmod +x "${SCRIPT_SRC}"

echo "✅ Plaky CLI instalado con éxito en ${INSTALL_DIR}/plaky"
echo "💡 Ahora puedes ejecutar 'plaky' desde cualquier parte de tu terminal."
