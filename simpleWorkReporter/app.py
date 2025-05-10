#!/usr/bin/python3
'''
simpleWorkReporter - app.py
--
Primary application definition.  Defines the package's application as
the SimpleWorkReporter() class to provide the top level application entry
point and flow control.  

Usage:
    from simpleWorkReporter import SimpleWorkReporter
    my_app = SimpleWorkReporter()
    my_app.run()
'''

# Flask specific imports (maybe I should just import flask?
from flask import Flask, render_template, request, flash, redirect, url_for
from .config import LoadSwrSettings
from .errors import *


class SimpleWorkReporter():
    def __init__(self, port: int = 5051):
        self.app = Flask(__name__)
        self.settings = LoadSwrSettings()
        self._set_routes()
    
    def _set_routes(self):
        @self.app.route('/')
        def www_index():
            page_title = f"Daily Tasks"
            return render_template('index.html', page_title=page_title, page_index=True)
        
        @self.app.route('/config')
        def www_config():
            page_title = f"Configuration"
            return render_template(
                'config.html', 
                page_title=page_title,
                service_port = self.settings.service_port,
                worker_name = self.settings.worker_name,
                worker_email = self.settings.worker_email,
                manager_name = self.settings.manager_name,
                manager_email = self.settings.manager_email,
                smtp = self.settings.smtp,
                page_config=True
            )
        
        @self.app.route('/update/config', methods=['POST'])
        def www_update_config():
            result, message = self.settings.update_config(
                service_port = request.form.get('servicePort'),
                worker_name = request.form.get('workerName'),
                worker_email = request.form.get('workerEmail'),
                manager_name = request.form.get('managerName'),
                manager_email = request.form.get('managerEmail'),
                smtp = request.form.get('smtpServer')
            )
            if result == self.settings.UpdateResult.NEW_SERVICE_PORT:
                # Service Port has been updated -- Redirect to restart.html
                self.new_service_port = True
                # TODO #
                ''' I need to setup a flask.flash message setup to report messages
                    back to the user after submission, but I would also like to 
                    come up with some way to detect globally that a new service_port
                    was defined and always redirect the user to a 'restart.html'
                    page until the app is restarted completely. '''
                pass
            elif result == self.settings.UpdateResult.UPDATED:
                # Worked normally, regular update message
                # TODO #
                ''' Here the update worked normally and I'd like to set a flash message
                    and redirect the user back to index.html '''
                pass
            elif result == self.settings.UpdateResult.FAILURE:
                # Error - Set a flash message containing 'message' as an error
                # TODO #
                ''' Return to config page with the error message '''
            else:
                # Unexpected application state
                raise swrInternalError()
        
        
        @self.app.route('/task/<id>')
        def www_task(id=id):
            page_title = f"Edit Item {id}"
            return render_template('task.html', page_title=page_title, page_task=True)
        
        @self.app.route('/send')
        def www_send_report():
            ''' 
            Email the report - Confirmation and interactive window
            '''
            return "Are you sure you want to send?"
        
        @self.app.route('/send/y')
        def www_send_report_confirmed():
            '''
            Actually send the report
            '''
            return "Sending report"


        
    
    def run(self):
        self.app.run(host='0.0.0.0', port=self.settings.service_port,debug=True)
        


# app = Flask(__name__)

# @app.route("/")
# def index():
#   return render_template('index.html')

# if __name__ == '__main__':
