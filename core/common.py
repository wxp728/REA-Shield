"""Anti-REA core 公共工具：路径、Schema 校验、run_id、JSON IO。"""
from __future__ import annotations

import datetime as _dt
import json
import os
import random

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_ROOT, "schemas")
POLICY_DIR = os.path.join(REPO_ROOT, "policies")

SCHEMA_VERSION = "1.0"


def load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


def validate(obj: dict, schema_name: str) -> None:
    """按 schemas/<name> 校验；失败抛 jsonschema.ValidationError。"""
    import jsonschema

    schema = load_schema(schema_name)
    jsonschema.validate(instance=obj, schema=schema)


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def new_run_id(seed: int | None = None) -> str:
    rnd = random.Random(seed)
    return "run-%s-%04d" % (_dt.datetime.now().strftime("%Y%m%d"), rnd.randint(0, 9999))


def write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_yaml(path: str, obj: dict) -> None:
    import yaml

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(obj, fh, allow_unicode=True, sort_keys=False)


def read_yaml(path: str) -> dict:
    import yaml

    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
