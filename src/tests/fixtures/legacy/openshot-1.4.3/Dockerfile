FROM ubuntu:12.04@sha256:18305429afa14ea462f810146ba44d4363ae76e4c8dfc38288cf73aa07485005

# The final stable 1.x release, from the official OpenShot PPA's Precise archive.
COPY openshot_1.4.3-1_all.deb /tmp/openshot.deb
RUN echo '513c9cec51856e77ec5bb3eae8b0ffc8ac6cb4ef5f92682adac31a7742be0049  /tmp/openshot.deb' | sha256sum -c - \
    && printf 'deb http://old-releases.ubuntu.com/ubuntu/ precise main universe\ndeb http://old-releases.ubuntu.com/ubuntu/ precise-updates main universe\ndeb http://old-releases.ubuntu.com/ubuntu/ precise-security main universe\n' > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && (dpkg -i /tmp/openshot.deb || DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends -f install) \
    && DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends install xvfb xauth frei0r-plugins \
    && test "$(dpkg-query -W -f='${Version}' openshot)" = '1.4.3-1' \
    && rm -rf /var/lib/apt/lists/* /tmp/openshot.deb

ENV SDL_AUDIODRIVER=dummy
WORKDIR /work/sampler
CMD ["xvfb-run", "-a", "python", "-u", "author.py"]
