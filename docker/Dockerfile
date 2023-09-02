#/######   Dockerfile for Archivy from the Source on Debian  ########
#                                                                   #
#####################################################################
#        CONTAINERISED ARCHIVY BUILT ON TOP OF DEBIAN LINUX         #
#        Main intension - to run/test dev version in docker         #
#                                                                   #
# This Dockerfile does the following:                               #
#                                                                   #
#    1. Starts with a base image of Python3.11 built on Debian      #
#       Bookworm Slim                                               #
#    2. Installs deps for archivy and SSR extensions.               #
#    3. Installs Archivy using sources of this repo.                #
#    4. Creates a non-root user account and group which will be     #
#       used to run run Archivy, creates the directory which        #
#       Archivy uses to store its data.                             #
#    5. The ownership of all copied files is set to                 #
#       archivy user and group.                                     #
#    6. Creates a mount point so that external volumes can be       #
#       mounted/attached to it. Useful for data persistence.        #
#    6. Setups wrapper to run draw.io headless.                     #
#    7. Exposes port 5000 on the container.                         #
#    8. Runs archivy                                                #
#####################################################################

# NOTE: docker section is based on
#       https://github.com/archivy/archivy-docker

# NOTE: draw.io related commands are taken from 
#       https://github.com/rlespinasse/docker-drawio-desktop-headless

FROM python:3.11-slim-bookworm

# Archivy version
ARG VERSION

# ARG values for injecting metadata during build time
# NOTE: When using ARGS in a multi-stage build, remember to redeclare
#       them for the stage that needs to use it. ARGs last only for the
#       lifetime of the stage that they're declared in.
ARG BUILD_DATE
ARG VCS_REF

ARG TARGETARCH=amd64
ENV DRAWIO_VERSION "21.6.8"


RUN \
      set -e; \
      echo "selected arch: ${TARGETARCH}"; \
      apt-get update \
  &&  DEBIAN_FRONTEND=noninteractive apt-get install -y \
  #  --no-install-recommends \
# Install mandatory apps
      ripgrep \
# Install optional apps
      pandoc \
      libreoffice \
      librsvg2-bin \
      wget \
      curl \
      git \
# Symbolator requirements pack
      gcc \
      pkg-config \
      libcairo2-dev \
      libgirepository1.0-dev \
      libsdl-pango-dev \
# Install draw.io apps
      xvfb \
      wget \
      libgbm1 \
      libasound2 \
# Fonts
      fonts-liberation fonts-arphic-ukai fonts-arphic-uming fonts-noto fonts-noto-cjk fonts-ipafont-mincho fonts-ipafont-gothic fonts-unfonts-core \
  &&  wget -O /opt/drawio.deb -q https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/drawio-${TARGETARCH}-${DRAWIO_VERSION}.deb \
  &&  apt-get install -y /opt/drawio.deb \
  &&  rm -rf /opt/drawio.deb \
  &&  rm -rf /var/lib/apt/lists/* \
  &&  python3 -m pip install \
        setuptools \
  &&  mkdir /opt/archivy \
  &&  mkdir /opt/drawio-desktop

# Download Y4S
RUN   mkdir /opt/y4s && cd /opt/y4s \
  &&  wget https://raw.githubusercontent.com/Godhart/yaml4hdelk/main/operators.py \
  &&  wget https://raw.githubusercontent.com/Godhart/yaml4hdelk/main/yaml4schm_defs.py \
  &&  wget https://raw.githubusercontent.com/Godhart/yaml4hdelk/main/yaml4schm.py

ENV YES_PATH=/opt/y4s

# Preinstall requirements to avoid global rebuilds on code change
COPY requirements.txt /opt/
RUN    python3 -m pip install -r /opt/requirements.txt \
    # Symbolator is a tricky thing...
    && python3 -m pip install setuptools==57.5.0 \
    && python3 -m pip install symbolator \
    && python3 -m pip install -U setuptools

RUN \
    # Creating non-root user and group for running Archivy
    addgroup --system --gid 1000 archivy \
    && adduser --home /archivy --comment "User account for running Archivy" \
    --shell /sbin/nologin --system --disabled-password --gid 1000 -uid 1000 archivy \
    # Creating directory in which Archivy's files will be stored
    # (If this directory isn't created, Archivy exits with a "permission denied" error)
    && mkdir -p /archivy/data \
    && mkdir -p /archivy/.local/share/archivy \
    # Changing ownership of all files in user's home directory
    && chown -R archivy:archivy /archivy

# Copy drawio wrapper
COPY --chown=archivy:archivy drawio-runner/ /opt/drawio-desktop/
RUN    chmod +x /opt/drawio-desktop/entrypoint.sh \
    && chmod +x /opt/drawio-desktop/runner.sh \
    && chmod +x /opt/drawio-desktop/runner_wrapper.sh \
    && chmod +w /opt/drawio-desktop/unwanted-security-warnings.txt \
    && chmod +w /opt/drawio-desktop/unwanted-update-logs.txt \
    && chown archivy:archivy /opt/drawio-desktop \
    && ln -s /opt/drawio-desktop/entrypoint.sh /usr/local/bin/draw.io \
    ;

# Copying pre-generated config.yml from host
COPY --chown=archivy:archivy docker/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh
COPY --chown=archivy:archivy docker/config.yml /archivy/.local/share/archivy/config.yml

# Install archivy from the source
COPY ./ /opt/archivy/
RUN cd /opt/archivy && python3 /opt/archivy/setup.py install \
    && rm -rf /opt/archivy

# Run as user 'archivy'
USER archivy

# Exposing port 5000
EXPOSE 5000

# System call signal that will be sent to the container to exit
STOPSIGNAL SIGTERM

ENTRYPOINT ["entrypoint.sh"]

# The 'run' CMD is required by the 'entrypoint.sh' script to set up the Archivy server. 
# Any command given to the 'docker container run' will override the CMD below.
CMD ["run"]

ENV ELECTRON_DISABLE_SECURITY_WARNINGS "true"
ENV DRAWIO_DISABLE_UPDATE "true"
ENV DRAWIO_DESKTOP_COMMAND_TIMEOUT "10s"
ENV DRAWIO_DESKTOP_EXECUTABLE_PATH "/opt/drawio/drawio"
ENV DRAWIO_DESKTOP_SOURCE_FOLDER "/opt/drawio-desktop"
ENV DRAWIO_DESKTOP_RUNNER_COMMAND_LINE "/opt/drawio-desktop/runner.sh"
ENV XVFB_DISPLAY ":42"
ENV XVFB_OPTIONS ""
ENV ELECTRON_ENABLE_LOGGING "false"

# Labels
LABEL org.opencontainers.image.vendor="Godhart" \
      org.opencontainers.image.authors="https://github.com/godhart" \
      org.opencontainers.image.title="Archivy with Godhart's Flavor" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.url="https://github.com/godhart/archivy" \
      org.label-schema.vcs-url="https://github.com/archivy/archivy-docker" \
      org.opencontainers.image.documentation="https://github.com/godhart/archivy/" \
      org.opencontainers.image.source="https://github.com/godhart/archivy/blob/main/Dockerfile" \
      org.opencontainers.image.description="Archivy is a self-hosted knowledge repository that \
      allows you to safely preserve useful content that contributes to your knowledge bank." \
      org.opencontainers.image.created=$BUILD_DATE \
      org.label-schema.build-date=$BUILD_DATE \
      org.opencontainers.image.revision=$VCS_REF \
      org.label-schema.vcs-ref=$VCS_REF \
      org.opencontainers.image.version=$VERSION \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0" \
      software.author.repository="https://github.com/godhart/archivy" \
      software.release.version=$VERSION
