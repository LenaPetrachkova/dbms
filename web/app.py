from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core.database import Database, TableExistsError, TableNotFoundError
from core.table import SchemaValidationError
from storage.json_backend import JsonStorageBackend

app = FastAPI(title="Mini DBMS")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

STORAGE_PATH = Path(tempfile.gettempdir()) / "mini_dbms_web_database.json"

if STORAGE_PATH.exists():
    database = JsonStorageBackend.load(STORAGE_PATH)
else:
    database = Database(name="default")
    JsonStorageBackend.save(database, STORAGE_PATH)


def persist_database() -> None:
    JsonStorageBackend.save(database, STORAGE_PATH)


class CreateTableRequest(BaseModel):
    name: str
    schema: dict[str, object]


class AddRowRequest(BaseModel):
    row: dict[str, object]


@app.post("/tables")
def create_table(request: CreateTableRequest) -> dict[str, object]:
    try:
        table = database.create_table(request.name, request.schema)
        persist_database()
    except (SchemaValidationError, TableExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"name": table.name, "schema": request.schema}


@app.post("/tables/{table_name}/rows")
def add_row(table_name: str, request: AddRowRequest) -> dict[str, object]:
    try:
        table = database.get_table(table_name)
        inserted = table.insert(request.row)
        persist_database()
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # ValidationError
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return inserted


@app.put("/tables/{table_name}/rows/{row_id}")
def update_row(table_name: str, row_id: str, request: AddRowRequest) -> dict[str, object]:
    try:
        table = database.get_table(table_name)
        updated = table.update(row_id, request.row)
        persist_database()
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return updated


@app.delete("/tables/{table_name}/rows/{row_id}")
def delete_row(table_name: str, row_id: str) -> dict[str, str]:
    try:
        table = database.get_table(table_name)
        table.delete(row_id)
        persist_database()
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted", "row_id": row_id}


@app.post("/tables/{table_name}/rows/sort")
def sort_rows(table_name: str, column: str, descending: bool = False) -> dict[str, str]:
    try:
        table = database.get_table(table_name)
        table.sort_by(column, reverse=descending)
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "sorted", "column": column, "descending": descending}


@app.get("/tables/{table_name}")
def get_table(table_name: str) -> dict[str, object]:
    try:
        table = database.get_table(table_name)
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return table.to_dict()


@app.post("/storage/save")
def save_database(path: str) -> dict[str, str]:
    JsonStorageBackend.save(database, path)
    return {"status": "saved", "path": path}


@app.post("/storage/load")
def load_database(path: str) -> dict[str, str]:
    global database
    database = JsonStorageBackend.load(path)
    return {"status": "loaded", "path": path}


# HTML pages
@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "db_name": database.name, "tables": database.tables},
    )


@app.get("/database/new")
def redirect_new_get() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)


@app.post("/database/new")
def new_database(name: str = Form(...)) -> RedirectResponse:
    global database
    database = Database(name=name)
    persist_database()
    return RedirectResponse(url="/", status_code=303)


@app.get("/database/upload")
def redirect_upload_get() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)


@app.post("/database/upload")
async def upload_database(file: UploadFile = File(...)) -> RedirectResponse:
    global database
    content = await file.read()
    try:
        payload = json.loads(content)
        database = Database.from_dict(payload)
        persist_database()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid database file: {exc}")
    return RedirectResponse(url="/", status_code=303)


@app.get("/database/download")
def download_database() -> FileResponse:
    persist_database()
    filename = f"{database.name or 'database'}.json"
    return FileResponse(STORAGE_PATH, media_type="application/json", filename=filename)


@app.post("/tables/{table_name}/delete")
def delete_table(table_name: str) -> RedirectResponse:
    try:
        database.drop_table(table_name)
        persist_database()
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RedirectResponse(url="/", status_code=303)


@app.get("/tables/create")
def redirect_tables_create() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)


@app.post("/tables/create")
def create_table_form(
    request: Request,
    name: str = Form(...),
    schema_fields: str = Form(...),
) -> HTMLResponse:
    schema: dict[str, object] = {}
    for line in schema_fields.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) < 2:
            continue
        field_name, type_name = parts[0].strip(), parts[1].strip()
        if type_name == "stringInvl":
            min_value = parts[2].strip() if len(parts) > 2 else None
            max_value = parts[3].strip() if len(parts) > 3 else None
            schema[field_name] = {
                "type": "stringInvl",
                "config": {
                    "base_type": {"type": "string", "config": {}},
                    "min_value": min_value or None,
                    "max_value": max_value or None,
                },
            }
        else:
            schema[field_name] = type_name
    try:
        database.create_table(name, schema)
        persist_database()
    except Exception as exc:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "db_name": database.name,
                "tables": database.tables,
                "error": str(exc),
            },
            status_code=400,
        )
    return RedirectResponse(url="/", status_code=303)


@app.get("/tables/{table_name}/view", response_class=HTMLResponse)
def view_table_page(table_name: str, request: Request) -> HTMLResponse:
    try:
        table = database.get_table(table_name)
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return templates.TemplateResponse(
        "table.html",
        {
            "request": request,
            "table": table.to_dict(),
            "columns": list(table.schema.keys()),
        },
    )


@app.post("/tables/{table_name}/rows/add", response_class=HTMLResponse)
async def add_row_form(
    table_name: str,
    request: Request,
) -> HTMLResponse:
    form = await request.form()
    try:
        table = database.get_table(table_name)
        raw_data: dict[str, object] = {}
        for key, value in form.multi_items():
            if key.startswith("upload_"):
                column = key[len("upload_") :]
                if hasattr(value, "read"):
                    try:
                        content_bytes = await value.read()
                        if content_bytes:
                            raw_data[column] = content_bytes.decode("utf-8")
                    except Exception:
                        pass
            elif key.startswith("field_"):
                column = key[len("field_") :]
                if value:
                    raw_data[column] = value

        clean_data: dict[str, object] = {}
        for column, field_type in table.schema.items():
            if column not in raw_data:
                raise HTTPException(status_code=400, detail=f"Missing required field '{column}'")
            value = raw_data[column]
            try:
                if field_type.type_name == "integer":
                    clean_data[column] = int(value)
                elif field_type.type_name == "real":
                    clean_data[column] = float(value)
                else:
                    clean_data[column] = value
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"Invalid value for '{column}': {exc}") from exc

        table.insert(clean_data)
        persist_database()
    except Exception as exc:
        return templates.TemplateResponse(
            "table.html",
            {
                "request": request,
                "table": table.to_dict(),
                "columns": list(table.schema.keys()),
                "error": str(exc),
            },
            status_code=400,
        )
    return RedirectResponse(url=f"/tables/{table_name}/view", status_code=303)


@app.post("/tables/{table_name}/rows/{row_id}/edit", response_class=HTMLResponse)
async def edit_row_form(
    table_name: str,
    row_id: str,
    request: Request,
) -> HTMLResponse:
    form = await request.form()
    try:
        table = database.get_table(table_name)
        raw_data: dict[str, object] = {}
        for key, value in form.multi_items():
            if key.startswith("upload_"):
                column = key[len("upload_") :]
                if hasattr(value, "read"):
                    try:
                        content_bytes = await value.read()
                        if content_bytes:
                            raw_data[column] = content_bytes.decode("utf-8")
                    except Exception:
                        pass
            elif key.startswith("field_"):
                column = key[len("field_") :]
                if value:
                    raw_data[column] = value

        clean_data: dict[str, object] = {}
        for column, field_type in table.schema.items():
            if column not in raw_data:
                continue
            if column in raw_data:
                value = raw_data[column]
                try:
                    if field_type.type_name == "integer":
                        clean_data[column] = int(value)
                    elif field_type.type_name == "real":
                        clean_data[column] = float(value)
                    else:
                        clean_data[column] = value
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid value for '{column}': {exc}") from exc

        if clean_data:
            table.update(row_id, clean_data)
            persist_database()
    except Exception as exc:
        return templates.TemplateResponse(
            "table.html",
            {
                "request": request,
                "table": table.to_dict(),
                "columns": list(table.schema.keys()),
                "error": str(exc),
            },
            status_code=400,
        )
    return RedirectResponse(url=f"/tables/{table_name}/view", status_code=303)


@app.post("/tables/{table_name}/rows/{row_id}/delete", response_class=HTMLResponse)
def delete_row_form(table_name: str, row_id: str) -> HTMLResponse:
    try:
        table = database.get_table(table_name)
        table.delete(row_id)
        persist_database()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/tables/{table_name}/view", status_code=303)


@app.post("/tables/{table_name}/rows/sort/form", response_class=HTMLResponse)
def sort_rows_form(table_name: str, column: str = Form(...), descending: bool = Form(False)) -> HTMLResponse:
    try:
        table = database.get_table(table_name)
        table.sort_by(column, reverse=descending)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/tables/{table_name}/view", status_code=303)


@app.get("/tables/{table_name}/rows/{row_id}/html/{column}/preview", response_class=HTMLResponse)
def preview_html_field(table_name: str, row_id: str, column: str) -> HTMLResponse:
    try:
        table = database.get_table(table_name)
        row = next((r for r in table.rows if r.get("_id") == row_id), None)
        if not row:
            raise HTTPException(status_code=404, detail="Row not found")
        html_content = row.get(column, "")
        return HTMLResponse(content=html_content)
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/tables/{table_name}/rows/{row_id}/html/{column}/download")
def download_html_field(table_name: str, row_id: str, column: str) -> FileResponse:
    try:
        table = database.get_table(table_name)
        row = next((r for r in table.rows if r.get("_id") == row_id), None)
        if not row:
            raise HTTPException(status_code=404, detail="Row not found")
        html_content = row.get(column, "")
        tmp_path = Path(tempfile.gettempdir()) / f"dbms_export_{row_id}_{column}.html"
        tmp_path.write_text(html_content, encoding="utf-8")
        return FileResponse(tmp_path, media_type="text/html", filename=f"{column}.html")
    except TableNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

