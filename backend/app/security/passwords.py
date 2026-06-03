"""
Gestor de palavras-passe do SNAJI.
Usa Argon2 — o algoritmo recomendado actualmente para passwords.
Mais seguro que bcrypt e sem o limite de 72 bytes.
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def criar_hash(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("A palavra-passe deve ter pelo menos 8 caracteres.")
    return _ph.hash(password)


def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        return _ph.verify(hash_guardado, password)
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False
