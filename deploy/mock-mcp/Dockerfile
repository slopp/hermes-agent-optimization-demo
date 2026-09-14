# Syntax is intentionally simple so the image can be built by any approved
# container pipeline. TLS termination and public ingress stay outside this
# workload; it binds the MCP protocol only on the container port.
FROM python:3.11-slim

WORKDIR /app
RUN useradd --create-home --uid 10001 mockmcp

COPY src/ /app/src/
# The server's default fixture path is /app/fixtures/world-v1.json. Keep the
# reviewed runtime fixture in the image, never traces or credentials.
COPY fixtures/world-v1.json /app/fixtures/world-v1.json
RUN pip install --no-cache-dir 'mcp==1.28.1' \
    && chown -R mockmcp:mockmcp /app

ENV PYTHONPATH=/app/src
USER mockmcp
EXPOSE 8000

# The entrypoint refuses to start without PA_STYLE_MOCK_MCP_TOKEN. Do not bake
# a token, certificate, endpoint, or any trace artifact into this image.
ENTRYPOINT ["python", "-m", "pa_style_mock_mcp.streamable_http"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--require-bearer-token"]
