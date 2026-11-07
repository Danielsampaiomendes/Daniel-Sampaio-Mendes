#!/bin/bash
# Abre o painel do Divine Studio com dois cliques (Mac).
# Na primeira vez: botão direito > Abrir (o macOS pede confirmação para arquivos baixados).

cd "$(dirname "$0")" || exit 1
PORTA=8765
URL="http://127.0.0.1:$PORTA"

echo "Divine Studio"
echo "-------------"
echo "Pasta: $PWD"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta o Python 3. Instale em https://www.python.org/downloads/ e abra de novo."
  read -r -p "Enter para fechar."
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Falta o FFmpeg. No Terminal: brew install ffmpeg"
  read -r -p "Enter para fechar."
  exit 1
fi
if ! python3 -c "import PIL, numpy, yaml" >/dev/null 2>&1; then
  echo "Instalando as bibliotecas do Divine Studio (só na primeira vez)..."
  python3 -m pip install --user -r requirements.txt || { read -r -p "Falhou. Enter para fechar."; exit 1; }
fi

# Atualiza pelo GitHub (guarda em _arquivo/ qualquer arquivo seu que fosse trocado) e reinstala o que mudou.
if [ "$1" != "--sem-atualizar" ]; then
  python3 divine_studio/atualizar.py --sem-painel || echo "  (seguindo com a versão que já está no Mac)"
fi

# Fontes: baixa só as que faltam (as novas de cada atualização entram sozinhas)
bash Biblioteca_Fontes/baixar_fontes.sh >/dev/null 2>&1 || echo "  (sem internet para as fontes novas; seguindo com as que já estão no Mac)"

# Painel antigo aberto? Fecha, senão ele continua rodando o código velho.
PIDS=$(lsof -ti tcp:$PORTA -sTCP:LISTEN 2>/dev/null)
if [ -n "$PIDS" ]; then
  echo "Fechando o painel antigo para abrir a versão nova..."
  kill $PIDS 2>/dev/null
  sleep 1
fi

echo "Versão: $(git log -1 --format='%cd · %h' --date=format:'%d/%m %H:%M' 2>/dev/null || echo 'sem atualização automática')"
echo "Abrindo o painel em $URL"
echo "Deixe esta janela aberta enquanto usa. Para fechar o app: Ctrl + C (ou feche esta janela)."
echo
exec python3 -m divine_studio painel --porta "$PORTA"
