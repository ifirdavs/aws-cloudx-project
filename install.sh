#!/bin/bash

yum update -y

mkdir ~/project
aws s3 cp s3://firdavsbekbucket1/project/ ~/project --recursive
cd ~/project

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn main:app --host 0.0.0.0 --port 8000