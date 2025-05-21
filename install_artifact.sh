#!/bin/bash

yum update -y
yum install git -y

git clone https://github.com/ifirdavs/aws-cloudx-project ./project
cd ./project

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn main:app --host 0.0.0.0 --port 8000