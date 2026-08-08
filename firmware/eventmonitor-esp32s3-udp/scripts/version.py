# ruff: noqa: F821 - Import and env are provided by PlatformIO/SCons.
Import("env")

version_file = env.File("$PROJECT_DIR/../../VERSION").get_abspath()
with open(version_file, encoding="utf-8") as handle:
    project_version = handle.read().strip()

env.Append(CPPDEFINES=[("EVENTMONITOR_VERSION", f'\\"{project_version}\\"')])
