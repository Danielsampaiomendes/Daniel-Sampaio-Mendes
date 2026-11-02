# Prompt: Storyboard e estilos de edição no Divine Studio

> O arquivo original deste prompt não chegou ao GitHub (ficou só no Mac). Esta versão foi reconstruída em 02/11/2026 a partir dos vídeos de referência que o Renato enviou: "Claude editor profissional" (@amandamoita.ia), "16 efeitos de vídeo que o Claude cria" (@ninja.automacoes) e "Carrossel 3C" (@afonsomolina). Se o original subir, comparar e ajustar.

## 1. Storyboard antes do render
- Depois do corte limpo, o app monta o "Storyboard · Edição": estilo, duração, número de cenas e de momentos, data.
- Aviso fixo: "Nada foi renderizado ainda. Cada quadro abaixo é a edição real naquele instante. Responda **aprovado** ou diga o código e o que mudar: `4B: troca o título por "..."`, `7: tira`, `2A: entra mais cedo`."
- Régua com os momentos numerados; cartões "Cena N · início a fim" com a fala, o texto e os quadros. Toque no quadro amplia.
- Com tudo aprovado ("TUDO APROVADO. FINALIZA."), o app exporta a final.
- Implementado em: `divine_studio/storyboard.py`, `render.quadros_em` (mesma composição do render), `python3 -m divine_studio storyboard <pasta> [--responder "..."]`, aba Storyboard do painel, `config/storyboard.yaml`.

## 2. Estilos de edição ("skills")
- Referência: /reel-glow (legenda glow + gráficos), /reel-papel (objetos de papel, tíquete e revista), /reel-prova (apps aparecendo + caixas de texto), /reel-telao (telão atrás de você), /reel-garrafal (letras garrafais e B-roll), /reels-kelsey (título de revista), /reels-nick (logos em tela dividida), /skill-iphone (logo em neon + iPhone 3D).
- No app: `estilo_edicao:` no projeto (ou por versão), `config/estilos.yaml`, seletor "Estilo de edição" no painel. Versão Divine: preto, dourado e off-white, sem logos de terceiros.

## 3. Os 16 efeitos
parede de manchetes, zoom que atravessa, vertigem, tela verde, mockup de celular, zoom digital com visor, recorte de papel, mundo de interface, órbita, quebra de moldura, rabisco tremido, texto adesivo, antes e depois (da edição), profundidade, recuo que revela, balão de comentário. Mais: parede de vídeos, "Toque em Saiba mais" com seta, tíquete de instrução, seta à mão "clica aqui", cartela "Poucos minutos depois" com timecode.
Implementado em `divine_studio/efeitos_truques.py` (todos editáveis na linha do tempo e no storyboard).

## 4. Carrossel 3C
1º C: capa com promessa clara de até 12 palavras. 2º C: CTA no meio (3º para o 4º slide): "antes de seguir, toca 2x na tela". 3º C: convite no último slide para o link da bio. Implementado em `carrossel.tres_c` e `carrossel.checar_3c`.
