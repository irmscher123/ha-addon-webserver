#!/usr/bin/env python3
"""HTTPS-Endpunkt für die Sperrseite.

Terminiert TLS auf Port 443 mit Zertifikaten, die pro Hostname (SNI) on-the-fly
von einer lokalen CA signiert werden, und leitet die Verbindung an nginx (Port 80)
weiter. nginx entscheidet dann anhand des Host-Headers: eigene Website oder Sperrseite.

Ist das CA-Zertifikat (http://<HA-IP>/ca.crt) auf einem Gerät als vertrauenswürdig
installiert, erscheint die Sperrseite ohne Zertifikatswarnung.
"""
import asyncio
import datetime
import ipaddress
import os
import re
import shutil
import ssl
import sys
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CA_DIR = os.environ.get("CA_DIR", "/data/ca")
PUBLISH_CA = os.environ.get("PUBLISH_CA", "/share/web/ca.crt")
LISTEN_PORT = int(os.environ.get("TLS_PORT", "443"))
UPSTREAM = ("127.0.0.1", int(os.environ.get("UPSTREAM_PORT", "80")))
CA_KEY = os.path.join(CA_DIR, "ca.key")
CA_CRT = os.path.join(CA_DIR, "ca.crt")
HOST_RE = re.compile(r"^[a-z0-9._-]{1,253}$")

_ctx_cache: dict[str, ssl.SSLContext] = {}
_tmp = tempfile.mkdtemp(prefix="tlsbp-")


def log(msg: str) -> None:
    print(f"[https] {msg}", flush=True)


def load_or_create_ca():
    os.makedirs(CA_DIR, exist_ok=True)
    if os.path.exists(CA_KEY) and os.path.exists(CA_CRT):
        key = serialization.load_pem_private_key(open(CA_KEY, "rb").read(), None)
        crt = x509.load_pem_x509_certificate(open(CA_CRT, "rb").read())
        return key, crt
    log("Erzeuge neue lokale CA ...")
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Heimnetz Sperrseite CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "irmscher Heimnetz"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    crt = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, key_cert_sign=True, crl_sign=True,
            content_commitment=False, key_encipherment=False, data_encipherment=False,
            key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(CA_KEY, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    os.chmod(CA_KEY, 0o600)
    with open(CA_CRT, "wb") as f:
        f.write(crt.public_bytes(serialization.Encoding.PEM))
    return key, crt


CA_KEY_OBJ, CA_CRT_OBJ = load_or_create_ca()


def make_context(hostname: str) -> ssl.SSLContext:
    key = ec.generate_private_key(ec.SECP256R1())
    try:
        san = x509.IPAddress(ipaddress.ip_address(hostname))
    except ValueError:
        san = x509.DNSName(hostname)
    now = datetime.datetime.now(datetime.timezone.utc)
    crt = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname[:64])]))
        .issuer_name(CA_CRT_OBJ.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=397))
        .add_extension(x509.SubjectAlternativeName([san]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(CA_KEY_OBJ.public_key()), critical=False)
        .sign(CA_KEY_OBJ, hashes.SHA256())
    )
    safe = re.sub(r"[^a-z0-9.-]", "_", hostname)
    cpath = os.path.join(_tmp, safe + ".crt")
    kpath = os.path.join(_tmp, safe + ".key")
    with open(cpath, "wb") as f:
        f.write(crt.public_bytes(serialization.Encoding.PEM))
        f.write(CA_CRT_OBJ.public_bytes(serialization.Encoding.PEM))
    with open(kpath, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_alpn_protocols(["http/1.1"])
    ctx.load_cert_chain(cpath, kpath)
    os.remove(kpath)
    return ctx


def context_for(hostname: str) -> ssl.SSLContext:
    ctx = _ctx_cache.get(hostname)
    if ctx is None:
        if len(_ctx_cache) > 2000:
            _ctx_cache.clear()
        ctx = make_context(hostname)
        _ctx_cache[hostname] = ctx
    return ctx


def sni_callback(sslobj, server_name, _ctx):
    if not server_name:
        return None
    name = server_name.lower().rstrip(".")
    if not HOST_RE.match(name):
        return None
    try:
        sslobj.context = context_for(name)
    except Exception as e:  # noqa: BLE001
        log(f"Zertifikat für {name} fehlgeschlagen: {e}")
    return None


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, ssl.SSLError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


async def handle(client_r, client_w):
    try:
        up_r, up_w = await asyncio.open_connection(*UPSTREAM)
    except OSError:
        client_w.close()
        return
    await asyncio.gather(pipe(client_r, up_w), pipe(up_r, client_w))


async def main():
    default_ctx = context_for("sperrseite.local")
    default_ctx.sni_callback = sni_callback
    server = await asyncio.start_server(handle, host=None, port=LISTEN_PORT, ssl=default_ctx,
                                        ssl_handshake_timeout=10)
    log(f"HTTPS-Sperrseite lauscht auf Port {LISTEN_PORT}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    if PUBLISH_CA:
        try:
            os.makedirs(os.path.dirname(PUBLISH_CA), exist_ok=True)
            shutil.copyfile(CA_CRT, PUBLISH_CA)
            log(f"CA-Zertifikat veröffentlicht: {PUBLISH_CA} (http://<HA-IP>/ca.crt)")
        except OSError as e:
            log(f"CA-Zertifikat konnte nicht veröffentlicht werden: {e}")
    try:
        asyncio.run(main())
    except OSError as e:
        log(f"Start fehlgeschlagen (Port {LISTEN_PORT} belegt?): {e}")
        sys.exit(1)
