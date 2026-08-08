# ruff: noqa: F821 - Import and env are provided by PlatformIO/SCons.
Import("env")

version_file = env.File("$PROJECT_DIR/../../VERSION").get_abspath()
with open(version_file, encoding="utf-8") as handle:
    project_version = handle.read().strip()

major, minor, patch = (int(value) for value in project_version.split("-", 1)[0].split("."))
version_code = ((major & 0x0F) << 12) | ((minor & 0x3F) << 6) | (patch & 0x3F)
env.Append(
    CPPDEFINES=[
        ("EVENTMONITOR_VERSION", f'\\"{project_version}\\"'),
        ("EVENTMONITOR_VERSION_CODE", version_code),
    ]
)
