#!/bin/bash
# Baixa todas as fontes do banco de combinações Divine (Google Fonts, licença OFL: uso comercial liberado) para ./ttf
# Só baixa o que falta: pode rodar sempre (o Divine Studio.command roda a cada abertura).
cd "$(dirname "$0")"; mkdir -p ttf
R=https://raw.githubusercontent.com/google/fonts/main/ofl
# A lista inclui, desde nov/2026, as fontes em alta: serifas editoriais de luxo, grotescas modernas,
# condensadas de impacto, scripts elegantes e manuscritas.
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
poppins Poppins-Bold.ttf
poppins Poppins-SemiBold.ttf
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
cinzel Cinzel%5Bwght%5D.ttf
dancingscript DancingScript%5Bwght%5D.ttf
cormorantgaramond CormorantGaramond-Italic%5Bwght%5D.ttf
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
youngserif YoungSerif-Regular.ttf
gildadisplay GildaDisplay-Regular.ttf
prata Prata-Regular.ttf
marcellus Marcellus-Regular.ttf
yesevaone YesevaOne-Regular.ttf
librecaslondisplay LibreCaslonDisplay-Regular.ttf
librebodoni LibreBodoni%5Bwght%5D.ttf
newsreader Newsreader%5Bopsz,wght%5D.ttf
newsreader Newsreader-Italic%5Bopsz,wght%5D.ttf
ebgaramond EBGaramond%5Bwght%5D.ttf
ebgaramond EBGaramond-Italic%5Bwght%5D.ttf
cormorant Cormorant%5Bwght%5D.ttf
playfairdisplaysc PlayfairDisplaySC-Regular.ttf
dmseriftext DMSerifText-Regular.ttf
dmserifdisplay DMSerifDisplay-Italic.ttf
rozhaone RozhaOne-Regular.ttf
instrumentsans InstrumentSans%5Bwdth,wght%5D.ttf
bricolagegrotesque BricolageGrotesque%5Bopsz,wdth,wght%5D.ttf
spacegrotesk SpaceGrotesk%5Bwght%5D.ttf
syne Syne%5Bwght%5D.ttf
geist Geist%5Bwght%5D.ttf
funneldisplay FunnelDisplay%5Bwght%5D.ttf
plusjakartasans PlusJakartaSans%5Bwght%5D.ttf
outfit Outfit%5Bwght%5D.ttf
sora Sora%5Bwght%5D.ttf
montserrat Montserrat%5Bwght%5D.ttf
inter Inter%5Bopsz,wght%5D.ttf
figtree Figtree%5Bwght%5D.ttf
urbanist Urbanist%5Bwght%5D.ttf
anton Anton-Regular.ttf
oswald Oswald%5Bwght%5D.ttf
archivoblack ArchivoBlack-Regular.ttf
leaguespartan LeagueSpartan%5Bwght%5D.ttf
bigshouldersdisplay BigShouldersDisplay%5Bwght%5D.ttf
parisienne Parisienne-Regular.ttf
alexbrush AlexBrush-Regular.ttf
italianno Italianno-Regular.ttf
imperialscript ImperialScript-Regular.ttf
corinthia Corinthia-Regular.ttf
birthstone Birthstone-Regular.ttf
ephesis Ephesis-Regular.ttf
windsong WindSong-Regular.ttf
meaculpa MeaCulpa-Regular.ttf
herrvonmuellerhoff HerrVonMuellerhoff-Regular.ttf
shadowsintolight ShadowsIntoLight.ttf
gochihand GochiHand-Regular.ttf
nanumpenscript NanumPenScript-Regular.ttf
spacemono SpaceMono-Regular.ttf
dmsans DMSans%5Bopsz,wght%5D.ttf
bodonimoda BodoniModa-Italic%5Bopsz,wght%5D.ttf
LIST
ls ttf | wc -l
