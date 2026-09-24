FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY pudubot2_sim ./pudubot2_sim
RUN pip install --no-cache-dir .

COPY configs ./configs

EXPOSE 7896

CMD ["python", "-m", "pudubot2_sim", "--config", "configs/config.yaml"]
