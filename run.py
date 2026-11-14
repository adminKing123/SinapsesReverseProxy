"""Convenience launcher — runs root ``app.py``."""

if __name__ == "__main__":
    import runpy

    runpy.run_path("app.py", run_name="__main__")