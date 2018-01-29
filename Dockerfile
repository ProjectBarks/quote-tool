FROM python:3
ADD . /
RUN pip install -r ./requirements.txt
RUN python ./setup.py install
EXPOSE 8000
CMD [ "python", "./main.py" ]