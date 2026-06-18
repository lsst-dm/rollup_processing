ARG STACK_TAG="w_latest"
FROM ghcr.io/lsst/scipipe:al9-${STACK_TAG}

USER root
RUN <<EOT
  # Fix the bash-completion bug in gdalinfo
  sed -i "s/_gdal-config/_gdal_config/g" \
    /opt/lsst/software/stack/conda/envs/lsst-scipipe-*/share/bash-completion/completions/gdalinfo
EOT
RUN groupadd -g 1126 -o gu \
    && useradd -u 48045 -g 1126 rubinppb
USER rubinppb
