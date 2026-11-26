FROM python:3.12-slim

WORKDIR /src
COPY pyproject.toml README.md ./
COPY kazoe ./kazoe
COPY schemas ./schemas
RUN pip install --no-cache-dir .

WORKDIR /work
ENTRYPOINT ["kazoe"]
CMD ["--help"]
