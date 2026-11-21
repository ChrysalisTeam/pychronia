from django.conf import settings

# secret key usable only for data exchanges internal to process
_instance_secret_key = settings.SECRET_KEY[0:32].encode("utf8")  # ELSE os.urandom(32)

if len(_instance_secret_key) != 32:
    raise ValueError("Crypto needs a django secret key >= 32 chars long")


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
