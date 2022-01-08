FROM python:slim
LABEL maintainer="OpenShot Developers <https://github.com/OpenShot/openshot-qt/>"

WORKDIR /
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      imagemagick \
      make \
      libcairo2 \
      librsvg2-bin \
      \
      latexmk \
      lmodern \
      fonts-freefont-otf \
      texlive-latex-recommended \
      texlive-fonts-recommended \
      texlive-luatex \
      texlive-xetex \
      xindy \
      tex-gyre \
 && apt-get autoremove \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
#      graphviz \
#      texlive-latex-extra \
#      texlive-fonts-extra \

COPY ./requirements.txt requirements.txt

RUN python3 -m pip install --no-cache-dir -U pip
RUN python3 -m pip install --no-cache-dir -r requirements.txt

CMD ["make", "-C", "docs", "latexpdf"]
