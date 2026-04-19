# dsci551-project

## Cockroach Cloud Setup

Follow CockroachDB documentation to set environment variable DATABASE_URL to the connection string : https://www.cockroachlabs.com/docs/stable/connect-to-the-database?filters=python

In a nutshell the process is first downloading and setting up a valid CA certificate located at `~/.postgresql/root.crt`, and then running a shell command in the form of: `export DATABASE_URL="postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=verify-full"`.

## Python Setup

Navigate to the dsci551-project directory.

In terminal run all shell commands in order:

`python3 -m venv env`

`source env/bin/activate`

`pip3 install -r requirements.txt`

## Running

In the first terminal tab run: `python3 server.py`

In another terminal tab run: `python3 drone.py`