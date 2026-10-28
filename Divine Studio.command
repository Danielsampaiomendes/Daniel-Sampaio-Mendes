#!/bin/bash
# Abre o painel do Divine Studio com dois cliques (Mac).
# Na primeira vez: botão direito > Abrir (o macOS pede confirmação para arquivos baixados).

cd "$(dirname "$0")" || exit 1
PORTA=8765
URL="http://127.0.0.1:$PORTA"

echo "Divine Studio"
echo "-------------"

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
if [ -z "$(ls Biblioteca_Fontes/ttf/*.ttf 2>/dev/null)" ]; then
  echo "Baixando as fontes (só na primeira vez)..."
  bash Biblioteca_Fontes/baixar_fontes.sh
fi

# Já aberto? Só mostra no navegador.
if curl -s -o /dev/null "$URL/api/projetos"; then
  echo "O painel já está aberto. Abrindo no navegador."
  open "$URL"
  exit 0
fi

echo "Abrindo o painel em $URL"
echo "Deixe esta janela aberta enquanto usa. Para fechar o app: Ctrl + C (ou feche esta janela)."
echo
python3 -m divine_studio painel --porta "$PORTA"
