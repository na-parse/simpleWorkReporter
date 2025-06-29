# simpleWorkReporter

simpleWorkReporter is a simple web-app designed to streamline the regular _work summary_ email your manager asks you to send.  Yes, you're already tracking your work in the ticket system, your code check-ins are easily auditable, and they could just duck into your team stand-ups every now and again, but here we are.

## Installation

### Dependencies / Pre-requisites

simpleWorkReport requires python >= 3.9 as well as the additional `flask` and `cryptography` packages.  

```bash
python3 -m pip install flask
python3 -m pip install cryptography
```

### Clone and Setup the repository

The simpleWorkReporter repository is quick and easy to get started.  Clone the repository on the system you'd like to serve as the web-app host and make sure you know a TCP port you'd like to use ahead of time.

> [!NOTE]
> The internal SMTP mailer currently only supports non-TLS port 25.  I'm too lazy/dumb to implement TLS right now mostly due to being a noob when it comes to credential embedding and management.  It's on the roadmap.

```bash
# Clone the repo into ./simpleWorkReporter
git clone https://github.com/na-parse/simpleWorkReporter.git

# Setup the service
cd ./simpleWorkReporter
python ./setupService.py
```

## Starting your simpleWorkReporter Instance

After completing setup, start the service:

`python ./startService.py`

Because this is intended for single user use, the basic flask/Werkzeug server is used in debug mode.  You will be able to confirm your available URLs from the Werkzeug startup.

## Usage

Open a webpage to your specified host and port and start adding work tasks!

![simpleWorkReporter homepage](/simpleWorkReporter/static/images/simpleWorkReporter_home.png)

## Sending the Report - Manually

Report can be sent manually via the webapp by clicking on the _Send Daily Report_.  This loads another page allowing you to review pending tasks and the current email settings before sending the report.

Clicking _Send_ will immediately send the email.  TODO: Script performs email exchange with remote SMTP server before any response on the client side.  Need to add some 'click-once' javascript to prevent multi-submission conflicts.

## Sending the Report - CLI or Scheduled

The simpleWorkReporter package includes the script `sendReport.py` to initiate the report email from the command line.  This can be used with task schedulers such as cron to setup automatic report transmission.

Note that sendReport.py will immediately send the email without asking for confirmation.  Additionally, no stdout output is generated when it runs headless so schedulers do not generate excessive result emails.


## Dev Roadmap

- Mailer
  - Add a web-app based API for sending email to remove necessity for local system scheduler
- Appearance
  - Support for a Dark Mode for the interface


## About

This project mainly originates from my laziness.  I don't want to have an extra text document open somewhere that I constantly have to update and maintain with data and formatting, reset between sends, lose and search for.

Having a webpage open on a tab in my browser seemed easy and non-invasive, and then the natural progress of "just make a little web app to take some text fields and send it automatically" came about.

Primarily this was a reason to try and improve my python code organization skills, get some more experience with flask and jinja2 templates, and get back into a little HTML after 20 years of being out of the web game.  Add on benefits of getting some more experience with github, and keeping a mind towards building an app for 'users' rather than myself.
