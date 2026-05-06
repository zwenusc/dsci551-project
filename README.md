# dsci551-project

## Cockroach Cloud Setup

Following CockroachDB documentation: https://www.cockroachlabs.com/docs/stable/connect-to-the-database?filters=python

1. Download the valid CA certificate.

2. Run the command to export DATABASE_URL in the form of:

`export DATABASE_URL="postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=verify-full"`.

DSCI 551 instructors: please find in the final report the exact commands to run (verbatim) with pre-setup certificate and connection string.

## Python Setup

Navigate to the dsci551-project directory.

In terminal run all shell commands in order:

`python3 -m venv env`

`source env/bin/activate`

`pip3 install -r requirements.txt`

## Running

(Run `source env/bin/activate` for each tab)

In the first terminal tab run: `python3 server.py`

In another terminal tab run: `python3 drone.py`