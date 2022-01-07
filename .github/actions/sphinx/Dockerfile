FROM sphinxdoc/sphinx-latexpdf:4.3.2

COPY ./docs /docs

#RUN ls -R

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_INPUT=1

COPY ./.github/actions/sphinx/docs-requirements.txt /docs-requirements.txt
RUN pip3 install -r /docs-requirements.txt

CMD ["make", "-C", "docs", "html"]

