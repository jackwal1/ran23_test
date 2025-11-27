# Use an official Python runtime as a parent image
FROM dishwireless.jfrog.io/docker-dev/python:3.11.11-bullseye
ARG JFROG_USER
ARG JFROG_PASSWORD

USER root

COPY . /home/pythonuser

WORKDIR /home/pythonuser

RUN echo "deb [trusted=yes] https://$JFROG_USER:$JFROG_PASSWORD@dishwireless.jfrog.io/artifactory/dev-debian-remote bullseye main contrib non-free\ndeb [trusted=yes] https://$JFROG_USER:$JFROG_PASSWORD@dishwireless.jfrog.io/artifactory/dev-debian-remote bullseye-updates main contrib non-free\ndeb [trusted=yes] https://$JFROG_USER:$JFROG_PASSWORD@dishwireless.jfrog.io/artifactory/debian-security-remote bullseye-security main contrib non-free\ndeb [trusted=yes] https://$JFROG_USER:$JFROG_PASSWORD@dishwireless.jfrog.io/artifactory/dev-debian-remote bullseye-backports main contrib non-free" > /etc/apt/sources.list \
    && echo "[global]\n" \
         "index-url = https://${JFROG_USER}:${JFROG_PASSWORD}@dishwireless.jfrog.io/artifactory/api/pypi/dev-pypi/simple\n" \
         "extra-index-url = https://${JFROG_USER}:${JFROG_PASSWORD}@dishwireless.jfrog.io/artifactory/api/pypi/pypi_pytorch_cpu/simple\n" \
    > /etc/pip.conf \
    && apt-get update -y && apt-get upgrade -y \
    && apt-get install libreoffice -y \
    && useradd -ms /bin/bash pythonuser \
    && pip3 install torch==2.1.0+cpu --index-url https://${JFROG_USER}:${JFROG_PASSWORD}@dishwireless.jfrog.io/artifactory/api/pypi/pypi_pytorch_cpu/simple/ \
    && pip3 install --no-cache-dir -r requirements.txt \
    && chown pythonuser:pythonuser -R  /home/pythonuser


EXPOSE 8000
USER pythonuser
RUN chmod 777 -R * 

ENTRYPOINT ["python3"]
CMD ["main.py"]