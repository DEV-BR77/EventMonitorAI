# Release Checklist

- [ ] All credentials and personal recordings are removed
- [ ] `python scripts/check_project.py` succeeds
- [ ] `pytest` succeeds
- [ ] ESP32 firmware builds with a local `secrets.h`
- [ ] Backend starts and `/health` responds successfully
- [ ] AudioLab starts and imports a test package
- [ ] README, changelog and release notes match the version
- [ ] Working tree is clean
- [ ] Tag uses the format `vMAJOR.MINOR.PATCH`
