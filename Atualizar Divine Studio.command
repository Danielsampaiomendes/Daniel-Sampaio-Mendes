#!/bin/bash
# Atualiza o Divine Studio pelo GitHub e abre o painel (funciona mesmo numa pasta antiga, sem git).
# Uso: dois cliques. Na primeira vez: botão direito > Abrir.
cd "$(dirname "$0")" || exit 1
PASTA="$PWD"
TMP="$(mktemp -d)"
echo "Divine Studio: baixando a versão nova..."
if git clone -q -b claude/ola-8lmaep --depth 1 https://github.com/Danielsampaiomendes/Daniel-Sampaio-Mendes.git "$TMP/ds"; then
  python3 "$TMP/ds/divine_studio/atualizar.py" "$PASTA"
else
  echo "Não consegui baixar do GitHub (sem internet ou sem login no git)."
  read -r -p "Enter para fechar."
fi
