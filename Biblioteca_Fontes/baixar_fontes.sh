#!/bin/bash
# Baixa todas as fontes do banco de combinações Divine (Google Fonts, licença OFL) para ./ttf
cd "$(dirname "$0")"; mkdir -p ttf
R=https://raw.githubusercontent.com/google/fonts/main/ofl
while read dir file; do
  out="ttf/$(echo "$file" | sed 's/%5B/[/;s/%5D/]/')"
  [ -s "$out" ] || curl -sf -o "$out" "$R/$dir/$file" || echo "FALHOU $dir/$file"
done <<'LIST'
instrumentserif InstrumentSerif-Regular.ttf
instrumentserif InstrumentSerif-Italic.ttf
caveat Caveat%5Bwght%5D.ttf
bodonimoda BodoniModa%5Bopsz,wght%5D.ttf
jost Jost%5Bwght%5D.ttf
playfairdisplay PlayfairDisplay%5Bwght%5D.ttf
playfairdisplay PlayfairDisplay-Italic%5Bwght%5D.ttf
poppins Poppins-Light.ttf
poppins Poppins-Medium.ttf
dmserifdisplay DMSerifDisplay-Regular.ttf
lora Lora-Italic%5Bwght%5D.ttf
italiana Italiana-Regular.ttf
mrssaintdelafield MrsSaintDelafield-Regular.ttf
fraunces Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf
manrope Manrope%5Bwght%5D.ttf
gloock Gloock-Regular.ttf
courierprime CourierPrime-Regular.ttf
bebasneue BebasNeue-Regular.ttf
pinyonscript PinyonScript-Regular.ttf
tenorsans TenorSans-Regular.ttf
rubik Rubik%5Bwght%5D.ttf
allura Allura-Regular.ttf
greatvibes GreatVibes-Regular.ttf
delagothicone DelaGothicOne-Regular.ttf
monsieurladoulaise MonsieurLaDoulaise-Regular.ttf
titilliumweb TitilliumWeb-Light.ttf
titilliumweb TitilliumWeb-Regular.ttf
abrilfatface AbrilFatface-Regular.ttf
unbounded Unbounded%5Bwght%5D.ttf
aguafinascript AguafinaScript-Regular.ttf
cormorantgaramond CormorantGaramond%5Bwght%5D.ttf
jura Jura%5Bwght%5D.ttf
lora Lora%5Bwght%5D.ttf
LIST
ls ttf | wc -l
