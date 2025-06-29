# simpleWorkReporter Design Notes

## Purpose of simpleWorkReporter

Provide a simple interface for workers that have been asked to track and submit/email daily or weekly summaries of their work activities to a manager.  By providing off-desktop data persistence, built in formating, and mailing routines, it simplifies the (typically redundant) process of collecting and mailing these disparate acitivites.

It is lightweight, built around flask, but provides SSL (self-signed) support to ensure those pesky auditors don't ding you for an open HTTP webserver (though they'll probably still complaint about the lack of CA trust).

## app.py / SimpleWorkReporter

The application is built as the `app.py:SimpleWorkReporter` class.  Class can be invoked with a manual path to a config file and a tasks db file, though these are optional and defaults are used from the `defs.py` script normally.

```python
from simpleWorkReporter import SimpleWorkReporter
reporter = SimpleWorkReporter()
reporter.run()
```

### Normal startup via startService.py

In general, the app is intended to be started via startService.py rather than used in a script.

Any configuration errors on startup will result in a _swrConfigError_ exception, which startService.py will catch and redirect into a statement directing users to run the setupService.py script.


### Flask Server Notes / Session

The flask server's secret_key is set based on the user's _Access_ configuration key, which should be an SHA256 hash of their password + the swr salt.  

Server key is set by returning a SHA256 hash digest of the Access configuration key value as bytes.  This will ensure session cookie remains persistent as long as the same user password is set.

Password can only be set via the setupService.py script now as well.





