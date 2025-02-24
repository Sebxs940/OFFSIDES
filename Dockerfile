FROM python:3.11-slim

WORKDIR /app  # 📌 Define el directorio de trabajo en /app
COPY . /app   # 📌 Copia todos los archivos del proyecto

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "offsides.py"]  # 📌 Asegúrate de que la ruta sea correcta
