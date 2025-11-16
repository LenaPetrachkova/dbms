# DBMS Lab

[![Run Tests](https://github.com/LenaPetrachkova/DBMS_lab/actions/workflows/tests.yml/badge.svg)](https://github.com/LenaPetrachkova/DBMS_lab/actions/workflows/tests.yml)

mini Database Management System with desktop and web interfaces.

## Features

- Support for multiple data types: integer, real, char, string, htmlFile, stringInvl
- Desktop GUI (Tkinter)
- Web interface (FastAPI)
- JSON-based storage
- Full CRUD operations
- Table sorting
- Data validation

## Running Tests

```bash
pytest tests/
```

## Desktop Version

```bash
python -m desktop.main
```

## Web Version

```bash
uvicorn web.app:app --reload
```

