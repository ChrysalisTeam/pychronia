# -*- coding: utf-8 -*-



import os, sys
from Crypto.Cipher import AES

from django.conf import settings

_instance_secret_key = settings.SECRET_KEY[
                       0:32]  # ELSE os.urandom(32) # secret key usable only for data exchanges internal to process
if len(_instance_secret_key) != 32:
    raise ValueError("Crypto needs a django secret key >= 32 chars long")
_default_iv = b"\0" * 16


def hash(password, salt=_instance_secret_key, length=32):
    """
    Returns an hexadecimal string of the wanted length.
    """
    assert 0 < length <= 128
    import hashlib
    if length > 64:  # hexa format doubles the length of the hash
        hasher = hashlib.sha512
    else:
        hasher = hashlib.sha256
    return hasher(salt + password).hexdigest()[0:length]


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
