
from app.rag.chunker import LegalChunker

def test_chunker():

    chunker = LegalChunker()

    chunks = chunker.split_document(
        "Artigo 1 Teste Artigo 2 Outro"
    )

    assert len(chunks) >= 2
