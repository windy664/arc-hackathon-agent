# Generation Templates

Reusable templates for Clone Agent application generation.

This repository stores copyable project templates. A generation runner can clone
or pull this repository, select one template by its `template.yaml`, and copy
the template directory's project files into the target project before agents
start implementing requirements. Do not copy `template.yaml` itself.

## Templates

| ID | Type | Stack |
|---|---|---|
| `web-react-fastapi` | Web application | Vite + React + TypeScript frontend, FastAPI backend |
| `web-react-express` | Web application | Vite + React frontend, Express + SQLite backend |
| `mobile-android-java` | Mobile application | Android + Java + Gradle |
| `cli-python` | Command-line application | Python + argparse + unittest |

## Copy Usage

Copy all files and directories in the selected template except `template.yaml`.
For example:

```powershell
Get-ChildItem -Force .\templates\web-react-fastapi |
  Where-Object Name -ne 'template.yaml' |
  Copy-Item -Recurse -Force -Destination D:\target\generated_app\
```

After copying, generation agents should implement inside:

- `frontend/src` for web UI.
- `backend/app` for FastAPI services and tests.
- `backend/src` for Express services and persistence.
- `app/src/main` and `app/src/test` for mobile tasks.
- `app` for CLI implementation and `tests` for CLI tests.
