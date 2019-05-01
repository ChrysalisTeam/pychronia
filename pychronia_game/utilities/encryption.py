# -*- coding: utf-8 -*-



import os, sys
from Crypto.Cipher import AES

from django.conf import settings

# secret key usable only for data exchanges internal to process
_instance_secret_key = settings.SECRET_KEY[0:32].encode("utf8")  # ELSE os.urandom(32)

if len(_instance_secret_key) != 32:
    raise ValueError("Crypto needs a django secret key >= 32 chars long")
_default_iv = b"\0" * 16


def hash(password, salt=_instance_secret_key, length=32):
    """
    Returns an hexadecimal string of the wanted length.
    """
    assert 0 < length <= 128, length
    assert isinstance(salt, bytes), salt
    import hashlib

    if isinstance(password, str):
        password = password.encode("utf8")

    if length > 64:  # hexa format doubles the length of the hash
        hasher = hashlib.sha512
    else:
        hasher = hashlib.sha256
    hashable = salt + password
    return hasher(hashable).hexdigest()[0:length]


def bytes_encrypt(value, key=_instance_secret_key, iv=_default_iv):
    """
    Returns a lowercase hexadecimal string (length unknown) with the encrypted value.
    """
    assert not isinstance(value, str)
    padded_key = hash(key, length=32)
    encryptor = AES.new(padded_key, AES.MODE_CFB, IV=iv)  # no padding neeeded thus
    return encryptor.encrypt(value).encode("hex").lower()


def bytes_decrypt(value, key=_instance_secret_key, iv=_default_iv):
    """
    Returns a byte string (length unknown) with the decrypted value.
    """
    assert not isinstance(value, str)
    padded_key = hash(key, length=32)
    decryptor = AES.new(padded_key, AES.MODE_CFB, IV=iv)  # no padding neeeded thus
    return decryptor.decrypt(value.decode("hex"))


def unicode_encrypt(value, key=_instance_secret_key, iv=_default_iv):
    value = value.encode("utf8")
    return bytes_encrypt(value, key=key, iv=iv)


def unicode_decrypt(value, key=_instance_secret_key, iv=_default_iv):
    res = bytes_decrypt(value, key=key, iv=iv)
    return res.decode("utf8")
