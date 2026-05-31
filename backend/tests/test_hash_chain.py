
from app.security.hash_chain import ImmutableHashChain

def test_hash_generation():

    chain = ImmutableHashChain()

    result = chain.hash_record("teste")

    assert len(result) > 10
