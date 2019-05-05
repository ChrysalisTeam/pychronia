# -*- coding: utf-8 -*-



import os, sys
import binascii

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


def get_padded_key(key):
    return hash(key, length=32).encode("utf8")


def bytes_encrypt(value, key=_instance_secret_key, iv=_default_iv):
    """
    Encrypts a bytes string.

    Returns a lowercase hexadecimal bytes string (length unknown).
    """
    assert isinstance(value, bytes)
    padded_key = get_padded_key(key)
    encryptor = AES.new(padded_key, AES.MODE_CFB, IV=iv)  # no padding neeeded thus
    encrypted = encryptor.encrypt(value)
    hexdata = binascii.hexlify(encrypted)
    assert hexdata.lower() == hexdata, hexdata
    return hexdata


def bytes_decrypt(value, key=_instance_secret_key, iv=_default_iv):
    """
    Decrypts an hexadecimal bytes string.

    Returns a byte string (length unknown) with the decrypted value.
    """
    assert isinstance(value, bytes)
    padded_key = get_padded_key(key)
    decryptor = AES.new(padded_key, AES.MODE_CFB, IV=iv)  # no padding neeeded thus
    encrypted = binascii.unhexlify(value)
    decrypted = decryptor.decrypt(encrypted)
    return decrypted


def unicode_encrypt(value, key=_instance_secret_key, iv=_default_iv):
    """Turns any str into an encrypted hewxadecimal str."""
    value = value.encode("utf8")
    encrypted_hex_bytes = bytes_encrypt(value, key=key, iv=iv)
    return encrypted_hex_bytes.decode("ascii", "strict")


def unicode_decrypt(value, key=_instance_secret_key, iv=_default_iv):
    """Turns back an encrypted hexadeximal str into the original str."""
    encrypted_hex_str = value.encode("ascii", "strict")
    res = bytes_decrypt(encrypted_hex_str, key=key, iv=iv)
    return res.decode("utf8")
