FROM python:3.11-slim

WORKDIR /app  # 📌 Crea y define el directorio antes de copiar los archivos
COPY . /app   # 📌 Copia todos los archivos al contenedor

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "offsides.py"]
