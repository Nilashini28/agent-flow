# Minimal, hardened image used for sandboxed tool execution containers.
FROM python:3.11-slim

RUN useradd --no-create-home --shell /usr/sbin/nologin sandboxuser
WORKDIR /sandbox
USER sandboxuser

# No network, no volume mounts, no persistent filesystem by default —
# these are enforced at container-run time in docker_runner.py, not here.
ENTRYPOINT ["python3"]
