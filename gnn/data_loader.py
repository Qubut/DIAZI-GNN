import json
from returns.result import safe
from returns.future import future_safe
from returns.pointfree import bind_result
from returns.pipeline import pipe
from pathlib import Path
import aiofiles
from typing import Any


@future_safe
async def read_file(path: Path) -> str:
    async with aiofiles.open(path, "r") as f:
        contents = await f.read()
        return contents


@safe
def parse_json(data: str) -> dict[str, Any]:
    return json.loads(data)


json_parsing_pipeline = pipe(read_file, bind_result(parse_json))
