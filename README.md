# simpleWorkReporter

Initial development is still underway.  

## Dev Roadmap
- Finalize TaskDatabase methods: Still require delete_task()
  - Skipping tooling around sent task view/manipulation for a later post-initial cycle
- First run configuration wizard
  - If no config exists, I want to launch a wizard before starting the app
  - Debating building into simpleWorkReport/config.py or a standalone service script similar to startService.py called simpleSetup.py
- Mailer handling
  - Planning still nebulous

## About simpleWorkReporter

Makes the daily work task/activity reporting process easier.

Start a flask WebServer, enter your tasks into the webpage as they come up over the day.

Setup the mailer process as desired and you and your manager will get a nice report.

## Installation

### From Repo to Working Application

Steps here

### Configuring the Service

Configuration needs to be setup before the service can start.  Required elements include
- TCP Port for WebService to listen on (deconflict with other services)
- SMTP relay target
- Worker Name, Email
- Manager Name, Email



#### Linux / Cron

Use Cron maybe

#### Windows / Task Scheduler

Use Task Scheduler

## Starting Up 

How to start it.  You know

## Anything Else

Goes here
