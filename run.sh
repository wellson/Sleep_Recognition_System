#!/bin/bash

# Define colors for beautiful CLI styling
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Workspace location
WORKDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$WORKDIR" || exit 1

echo -e "${CYAN}=====================================================${NC}"
echo -e "${GREEN}    SISTEMA DE MONITORAMENTO DE SONOLENCIA (V.1.0)   ${NC}"
echo -e "${CYAN}=====================================================${NC}"

# Check if .venv exists and is valid (not moved from another directory)
recreate_venv=false
if [ ! -d ".venv" ]; then
    recreate_venv=true
else
    # Check if the virtual environment is broken (paths inside pointing to another directory)
    # A moved venv will have broken paths or its prefix won't match the new WORKDIR.
    if [ ! -f ".venv/bin/activate" ] || ! .venv/bin/python3 -c "import sys; sys.exit(0 if sys.prefix.startswith('$WORKDIR') else 1)" 2>/dev/null; then
        echo -e "${YELLOW}[AVISO] Ambiente virtual (.venv) invalido ou movido de outra pasta.${NC}"
        recreate_venv=true
    fi
fi

if [ "$recreate_venv" = true ]; then
    echo -e "${CYAN}[INFO] Recriando ambiente virtual (.venv) de forma limpa...${NC}"
    rm -rf .venv
    python3 -m venv .venv
    source .venv/bin/activate
    echo -e "${CYAN}[INFO] Instalando dependencias (isso pode levar alguns segundos)...${NC}"
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Menu display
show_menu() {
    echo ""
    echo -e "${YELLOW}Selecione uma opcao:${NC}"
    echo -e " 1) ${GREEN}Iniciar Webcam & Detector (Tempo Real)${NC}"
    echo -e " 2) ${CYAN}Gerar Dashboard Analitico (Matplotlib)${NC}"
    echo -e " 3) ${YELLOW}Sintetizar Arquivos de Audio (Alarme)${NC}"
    echo -e " 4) Sair"
    echo ""
    read -p "Opcao [1-4]: " opcao
}

while true; do
    show_menu
    case $opcao in
        1)
            echo -e "\n${GREEN}[INFO] Iniciando o detector... Ajuste sua webcam e iluminacao.${NC}"
            echo -e "${CYAN}[WEB] Dashboard em tempo real disponivel em: http://localhost:55800${NC}"
            echo -e "${YELLOW}Dica: Pressione 'q' na tela do video para sair.${NC}\n"
            python3 drowsiness_detector.py
            ;;
        2)
            echo -e "\n${CYAN}[INFO] Lendo 'drowsiness_events.csv' e compilando dados...${NC}"
            python3 analytics.py
            ;;
        3)
            echo -e "\n${YELLOW}[INFO] Recriando sintetizadores de onda senoidal...${NC}"
            python3 generate_audio.py
            ;;
        4)
            echo -e "\n${GREEN}Obrigado por usar o sistema de seguranca. Boa viagem!${NC}"
            break
            ;;
        *)
            echo -e "\n${RED}[AVISO] Opcao invalida. Digite um numero de 1 a 4.${NC}"
            ;;
    esac
done
