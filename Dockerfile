FROM python:3.12-slim

WORKDIR /src
COPY pyproject.toml README.md ./
COPY python_sloc_counter ./python_sloc_counter
COPY schemas ./schemas
RUN pip install --no-cache-dir .

WORKDIR /work
ENTRYPOINT ["python-sloc-counter"]
CMD ["--help"]
