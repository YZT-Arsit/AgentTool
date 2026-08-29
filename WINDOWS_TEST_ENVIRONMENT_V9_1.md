# Windows Test Environment V9.1

The allowed system interpreter was configured because Windows Application
Control blocked execution of the copied `.venv/Scripts/python.exe` (WinError
4551). No policy bypass was attempted.

Validated environment:

```text
Python: 3.13.14
cryptography: 50.0.1
numpy: 2.5.2
scikit-learn: 1.9.0
scipy: 1.18.1
pytest: 9.1.1
OpenAI Agents SDK: local editable 0.22.0
Microsoft Agent Framework core: local editable 1.15.0
```

Recreate the Python dependencies from the repository root with:

```powershell
python -m pip install -r requirements-windows-tests.txt
```

Run the suite with a repository-local pytest temporary directory because the
default user temporary root is not readable under the current host policy:

```powershell
python -m pytest -q --basetemp=.tmp_pytest/v91_windows
```

Result on 2026-08-29:

```text
217 passed, 2 skipped in 37.70s
```

Both skips are explicit `NOT_COMPLETED_ENVIRONMENT` cases where Windows
Application Control blocks the local Pacer executable. They are not dependency,
collection, or assertion failures. Timing privacy remains OPEN / NOT TESTED.
