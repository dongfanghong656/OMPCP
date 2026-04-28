#!/usr/bin/env python
from __future__ import annotations

import base64
import ctypes
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SECURE_REF_KEY = "$secure_ref"
DEFAULT_STORE_DIRNAME = ".codex-local"
DEFAULT_STORE_FILENAME = "secure-secrets.v1.json"
DPAPI_ENTROPY = b"OCT_Research_System::local-secret-store::v1"
CRYPTPROTECT_UI_FORBIDDEN = 0x01


@dataclass(frozen=True)
class SecretBinding:
    secret_id: str
    path: tuple[str, ...]
    description: str


SECRET_BINDINGS = (
    SecretBinding("zotero.web", ("zotero", "api_key"), "Zotero Web API key"),
    SecretBinding("openai.translate", ("translation", "openai", "api_key"), "Translation OpenAI API key"),
    SecretBinding("openai.academic-qa", ("academic_qa", "openai", "api_key"), "Academic QA OpenAI API key"),
    SecretBinding("openai.question-radar", ("question_radar", "openai", "api_key"), "Question radar OpenAI API key"),
    SecretBinding(
        "openai.continuous-research",
        ("continuous_research", "openai", "api_key"),
        "Continuous research OpenAI API key",
    ),
    SecretBinding("mail.smtp-user", ("delivery", "email", "smtp_user"), "SMTP login user"),
    SecretBinding("mail.smtp-auth", ("delivery", "email", "smtp_pass"), "SMTP login password"),
)


class SecureConfigError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return resolve_secure_refs(payload, path)


def load_raw_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_secure_ref(secret_id: str) -> dict[str, str]:
    return {SECURE_REF_KEY: secret_id}


def is_secure_ref(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value.keys()) == {SECURE_REF_KEY}
        and isinstance(value.get(SECURE_REF_KEY), str)
        and bool(value[SECURE_REF_KEY].strip())
    )


def discover_workspace_root(reference_path: Path) -> Path:
    start = reference_path if reference_path.is_dir() else reference_path.parent
    for candidate in [start, *start.parents]:
        if candidate.name == "oct-research-assist":
            return candidate.parent
        if (candidate / "oct-research-assist").exists():
            return candidate
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists() and (candidate / "oct-research-assist").exists():
            return candidate
    return start


def default_secret_store_path(reference_path: Path) -> Path:
    override = os.environ.get("CODEX_LOCAL_SECRET_STORE", "").strip()
    if override:
        return Path(override)
    return discover_workspace_root(reference_path) / DEFAULT_STORE_DIRNAME / DEFAULT_STORE_FILENAME


def binding_by_secret_id(secret_id: str) -> SecretBinding | None:
    for binding in SECRET_BINDINGS:
        if binding.secret_id == secret_id:
            return binding
    return None


def all_secret_bindings() -> tuple[SecretBinding, ...]:
    return SECRET_BINDINGS


def get_value_at_path(payload: Any, path: tuple[str, ...]) -> Any:
    current = payload
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def set_value_at_path(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = payload
    for part in path[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[path[-1]] = value


def resolve_secure_refs(payload: Any, reference_path: Path, store_path: Path | None = None) -> Any:
    cached_store: LocalSecretStore | None = None

    def resolve_node(node: Any) -> Any:
        nonlocal cached_store

        if is_secure_ref(node):
            if cached_store is None:
                cached_store = LocalSecretStore(store_path or default_secret_store_path(reference_path))
            secret_id = str(node[SECURE_REF_KEY]).strip()
            return cached_store.get(secret_id, default="")

        if isinstance(node, dict):
            return {key: resolve_node(value) for key, value in node.items()}

        if isinstance(node, list):
            return [resolve_node(item) for item in node]

        return node

    return resolve_node(payload)


def migrate_config_secrets(config_path: Path, store_path: Path | None = None) -> dict[str, Any]:
    config = load_raw_json(config_path)
    if not isinstance(config, dict):
        raise SecureConfigError("Config file must contain a top-level JSON object.")

    store = LocalSecretStore(store_path or default_secret_store_path(config_path))
    stored: list[str] = []
    placeholdered: list[str] = []
    already_linked: list[str] = []

    for binding in SECRET_BINDINGS:
        current_value = get_value_at_path(config, binding.path)
        if is_secure_ref(current_value):
            already_linked.append(binding.secret_id)
            continue

        if isinstance(current_value, str) and current_value.strip():
            store.set(binding.secret_id, current_value.strip())
            stored.append(binding.secret_id)

        if current_value is not None:
            set_value_at_path(config, binding.path, make_secure_ref(binding.secret_id))
            placeholdered.append(binding.secret_id)

    save_json(config_path, config)
    return {
        "config_path": str(config_path),
        "store_path": str(store.path),
        "stored": stored,
        "placeholdered": placeholdered,
        "already_linked": already_linked,
    }


def set_secret(config_path: Path, secret_id: str, value: str, store_path: Path | None = None) -> dict[str, Any]:
    binding = binding_by_secret_id(secret_id)
    if binding is None:
        raise SecureConfigError("Unknown secret id: " + secret_id)

    config = load_raw_json(config_path)
    if not isinstance(config, dict):
        raise SecureConfigError("Config file must contain a top-level JSON object.")

    store = LocalSecretStore(store_path or default_secret_store_path(config_path))
    store.set(secret_id, value)
    set_value_at_path(config, binding.path, make_secure_ref(secret_id))
    save_json(config_path, config)
    return {
        "config_path": str(config_path),
        "store_path": str(store.path),
        "secret_id": secret_id,
        "status": "stored",
    }


def unset_secret(config_path: Path, secret_id: str, store_path: Path | None = None) -> dict[str, Any]:
    binding = binding_by_secret_id(secret_id)
    if binding is None:
        raise SecureConfigError("Unknown secret id: " + secret_id)

    store = LocalSecretStore(store_path or default_secret_store_path(config_path))
    removed = store.delete(secret_id)
    return {
        "config_path": str(config_path),
        "store_path": str(store.path),
        "secret_id": secret_id,
        "status": "removed" if removed else "missing",
    }


def secret_status(config_path: Path, store_path: Path | None = None) -> dict[str, Any]:
    config = load_raw_json(config_path)
    if not isinstance(config, dict):
        raise SecureConfigError("Config file must contain a top-level JSON object.")

    store = LocalSecretStore(store_path or default_secret_store_path(config_path))
    stored_ids = set(store.list_ids())
    configured_refs: list[str] = []
    inline_plaintext: list[str] = []
    missing_values: list[str] = []

    for binding in SECRET_BINDINGS:
        current_value = get_value_at_path(config, binding.path)
        if is_secure_ref(current_value):
            configured_refs.append(binding.secret_id)
            if binding.secret_id not in stored_ids:
                missing_values.append(binding.secret_id)
            continue

        if isinstance(current_value, str) and current_value.strip():
            inline_plaintext.append(binding.secret_id)

    return {
        "config_path": str(config_path),
        "store_path": str(store.path),
        "configured_refs": configured_refs,
        "stored_ids": sorted(stored_ids),
        "missing_values": missing_values,
        "inline_plaintext": inline_plaintext,
    }


class LocalSecretStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def list_ids(self) -> list[str]:
        payload = self._load_store()
        secrets = payload.get("secrets", {})
        return sorted(key for key in secrets.keys() if isinstance(key, str))

    def get(self, secret_id: str, default: str = "") -> str:
        payload = self._load_store()
        secret_entry = (payload.get("secrets", {}) or {}).get(secret_id)
        if not isinstance(secret_entry, dict):
            return default
        cipher_text = str(secret_entry.get("ciphertext", "")).strip()
        if not cipher_text:
            return default
        return self._decrypt(cipher_text)

    def set(self, secret_id: str, value: str) -> None:
        payload = self._load_store()
        payload.setdefault("schema_version", 1)
        payload.setdefault("store_type", "windows-dpapi-current-user")
        payload.setdefault("secrets", {})
        payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload["secrets"][secret_id] = {
            "ciphertext": self._encrypt(value),
            "updated_at": payload["updated_at"],
        }
        self._write_store(payload)

    def delete(self, secret_id: str) -> bool:
        payload = self._load_store()
        secrets = payload.get("secrets", {})
        if secret_id not in secrets:
            return False
        del secrets[secret_id]
        payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._write_store(payload)
        return True

    def _load_store(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": 1,
                "store_type": "windows-dpapi-current-user",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "secrets": {},
            }
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SecureConfigError("Local secret store must contain a JSON object.")
        payload.setdefault("secrets", {})
        return payload

    def _write_store(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _encrypt(self, value: str) -> str:
        if os.name != "nt":
            raise SecureConfigError("DPAPI-backed local secrets are only supported on Windows.")
        encrypted = _dpapi_protect(value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("ascii")

    def _decrypt(self, cipher_text: str) -> str:
        if os.name != "nt":
            raise SecureConfigError("DPAPI-backed local secrets are only supported on Windows.")
        raw = base64.b64decode(cipher_text.encode("ascii"))
        return _dpapi_unprotect(raw).decode("utf-8")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _make_blob(data: bytes) -> tuple[DATA_BLOB, Any]:
    if not data:
        return DATA_BLOB(0, None), None
    buffer = (ctypes.c_byte * len(data))(*data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _blob_bytes(blob: DATA_BLOB) -> bytes:
    if not blob.cbData or not blob.pbData:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


def _dpapi_protect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, input_buffer = _make_blob(data)
    entropy_blob, entropy_buffer = _make_blob(DPAPI_ENTROPY)
    output_blob = DATA_BLOB()
    del input_buffer
    del entropy_buffer
    result = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not result:
        raise ctypes.WinError()
    try:
        return _blob_bytes(output_blob)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, input_buffer = _make_blob(data)
    entropy_blob, entropy_buffer = _make_blob(DPAPI_ENTROPY)
    output_blob = DATA_BLOB()
    description = ctypes.c_wchar_p()
    del input_buffer
    del entropy_buffer
    result = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        ctypes.byref(description),
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not result:
        raise ctypes.WinError()
    try:
        return _blob_bytes(output_blob)
    finally:
        kernel32.LocalFree(output_blob.pbData)
        if description:
            kernel32.LocalFree(description)
