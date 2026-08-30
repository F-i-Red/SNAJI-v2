"""
Pacote da aplicação SNAJI.

Carrega o ficheiro .env para o ambiente do processo logo no primeiro import.

Porquê: parte da configuração é lida pelas definições da aplicação
(pydantic-settings) e parte é lida directamente do ambiente com os.getenv —
motor de recuperação, reescrita, embeddings, limitador de pedidos. Sem este
carregamento, as variáveis SNAJI_* escritas no .env nunca chegavam a esses
módulos e o sistema corria silenciosamente com os valores por omissão, dando
a impressão de que a configuração não tinha efeito.

Valores já definidos no ambiente do sistema têm precedência sobre o .env
(override=False), para que seja possível sobrepor pontualmente em testes.
"""
from pathlib import Path

try:
    from dotenv import load_dotenv

    # backend/app/__init__.py → backend/.env
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.is_file():
        load_dotenv(_env, override=False)
except Exception:  # nunca impedir o arranque por causa disto
    pass
