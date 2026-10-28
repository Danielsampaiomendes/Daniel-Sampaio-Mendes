"""Templates de vídeo. Cada um expõe montar(projeto, versao, combo, duracao_base, W, H, sfx_abertura,
sfx_fechamento, sfx_transicao) e, quando precisa, preparar(projeto), tamanho_base(projeto, W, H) e
extras(projeto, W, H) (outros vídeos decodificados junto, como a referência do React)."""
from . import daniel, divine, george, pessoal, react, tv

TEMPLATES = {"divine": divine, "daniel": daniel, "george": george, "tv": tv, "react": react, "pessoal": pessoal}
