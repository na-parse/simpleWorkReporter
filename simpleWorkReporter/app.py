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
from flask import (
    Flask, 
    render_template, 
    request, 
    flash, 
    redirect, 
    url_for,
    session
)
from urllib.parse import urlparse, urlunparse
from pathlib import Path
from datetime import datetime
from ssl import SSLError
import time
import os

from . import defs
from . import syslog
from .config import LoadSwrSettings, UpdateResult
from .tasks import TaskDatabase
from .errors import *
from .devtools import vardump

class SimpleWorkReporter():
    def __init__(self, config_path: Path = None, db_path: Path = None):
        self.app = Flask(__name__)
        self.app.secret_key = os.urandom(24)  # Required for flash messages
        self.settings = LoadSwrSettings(config_path=config_path)
        self.task_db = TaskDatabase(db_path=db_path)
        self.new_service_port = None # Used if port update requires restart
        self._set_routes()
    
    def _set_routes(self):
        # Add before_request handler for global port change detection
        @self.app.before_request
        def before_requests_handler():
            # Server Restart Required Redirect
            if (
                self.new_service_port 
                and request.endpoint != 'www_restart' 
                and not request.path.startswith('/static/')
            ):
                # If port change is pending and user is not already on restart page, redirect
                return redirect(url_for('www_restart'))
            # Authentication check and redirect
            if (
                request.endpoint not in defs.ALLOWED_ENDPOINTS_WITHOUT_AUTH and
                not request.path.startswith('/static/') and
                not session.get('authenticated')
            ):
                # Missing authentication
                next_url = request.url
                if [True for s in ['/update','/submit'] if s in next_url]:
                    # Don't set next_url for form sumissions, use index instead
                    next_url = url_for('www_index')
                return redirect(url_for('www_login', next=next_url))
        
        @self.app.route('/')
        def www_index():
            page_title = f"Daily Tasks"
            tasks = self.task_db.get_unsent_tasks()
            return render_template(
                'index.html', 
                page_title=page_title, 
                page_index=True,
                tasks=tasks,
                settings=dict(self.settings)
            )

        @self.app.route('/config')
        def www_config():
            page_title = f"Configuration"
            return render_template(
                'config.html', 
                page_title=page_title,
                page_config=True,
                settings=dict(self.settings)
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
            if result == UpdateResult.NEW_SERVICE_PORT:
                # Service Port has been updated -- Redirect to restart
                self.new_service_port = True
                flash("Configuration updated - New service port requires server restart", "success")
                return redirect(url_for('www_restart'))
            elif result == UpdateResult.UPDATED:
                # Configuration updated (non-service port) -- Redirect to index
                flash("Configuration successfully updated.", "success")
                return redirect(url_for('www_index'))
            elif result == UpdateResult.FAILURE:
                # Error - Set a flash message containing 'message' as an error
                flash(f"Configuration update failed: {message}", "error")
                return redirect(url_for('www_config'))
            else:
                # Unexpected application state
                raise swrInternalError()
        
        
        @self.app.route('/task/<id>')
        @self.app.route('/task/delete/<id>')
        def www_task(id=id):
            delete_confirm = 'task/delete' in request.url
            task_action = "Edit" if not delete_confirm else "Delete"

            page_title = f"{task_action} Task {id}"
            task = self.task_db.get_task(id)
            if not task:
                flash(f'Task ID {id} does not exist.','warning')
                return redirect(url_for('www_index'))
            
            return render_template(
                'task.html', 
                page_title=page_title, 
                page_task=True, 
                action=task_action,
                id=id,
                task=task,
                delete_confirm=delete_confirm,
                settings=dict(self.settings)
            )

        @self.app.route('/submit/task', methods=['POST'])
        def www_submit_task():
            ''' Task Add/Update/Delete workflow '''
            is_new = request.form.get('newTask','') == 'newTask'
            is_delete = request.form.get('deleteTask','') == 'confirmed'

            # Extract form data and validate required forms filled out
            try:
                taskId = request.form.get('taskId',None)
                taskType = request.form['taskType']
                taskSubType = request.form['taskSubType']
                description = request.form['description']
                date = request.form.get('workDate',None)
            except Exception as e:
                flash(
                    f'Expected Task value for "{e.args[0]}" was not found.'
                    f' Unable to process.','error'
                )
                return redirect(url_for('www_index'))

            if is_new:
                result, message = self.task_db.add_task(
                    taskType, taskSubType, description, date
                )
                if not result:
                    flash(f'New task submission failed: {message}','error')
                else:
                    # flash(f'New task submitted successfully.','success')
                    # Dont really need to add a flash, they'll see the new task
                    pass
            elif is_delete:
                if self.task_db.delete_task(taskId):
                    flash(f'Successfully deleted task {taskId}','success')
                else:
                    flash(f'An issue occrred while deleting task {taskId}','warning')  
            else:
                # Edit Existing Task
                result, message = self.task_db.edit_task(
                    taskId,taskType,taskSubType,description,date
                )
                if not result:
                    flash(f'Task edit failed: {message}','error')
                else:
                    flash(f'Task {taskId} successfully updated.','success')

            # Send back to home page regardless of outcome
            return redirect(url_for('www_index'))


        @self.app.route('/send')
        def www_send_report():
            ''' 
            Email the report - Confirmation and interactive window
            '''
            page_title = "Send Daily Report"
            return render_template('send.html',
                page_title=page_title,
                settings=dict(self.settings)
            )

        @self.app.route('/login', methods=['GET','POST'])
        def www_login():
            if request.method == "POST":
                password = request.form.get('password','')
                if self.settings.is_pass_valid(password):
                    session['authenticated'] = True
                    session.permanent = True # Use PERMANENT_SESSION_LIFETIME
                    flash('Login successful.', 'success')
                    next_url = request.args.get('next') or url_for('www_index')
                    return redirect(next_url)
                else:
                    flash('Invalid password.', 'error')
            return render_template('login.html', page_title="Login")                
            
            page_title = "Login"
            return render_template('login.html',
                page_title=page_title,
                settings=dict(self.settings)
            )
        
        @self.app.route('/logout')
        def www_logout():
            session.pop('authenticated', None)
            flash('You have been logged out.', 'info')
            return redirect(url_for('www_login'))

        @self.app.route('/send/y')
        def www_send_report_confirmed():
            '''
            Actually send the report
            '''
            return "Sending report"

        @self.app.route('/restart')
        def www_restart():
            # Build the new target URL after service restart based on new port value
            current_url = request.url
            parsed_url = urlparse(current_url)
            scheme = parsed_url.scheme
            hostname = parsed_url.netloc.split(':')[0]  # Remove current port if present
            
            # Create new URL with the new port
            new_netloc = f"{hostname}:{self.settings.service_port}"
            
            # Rebuild the URL with the same path but new port
            new_url = urlunparse((scheme,new_netloc,'/','','',''))
            page_title = "Service Restart Required"
            new_port = self.settings.service_port
            return render_template('restart.html', page_title=page_title, new_url=new_url)

    
    def run(self):
        ssl_context = _check_for_ssl_context()
        try:
            self.app.run(
                host='0.0.0.0', 
                port=self.settings.service_port,
                ssl_context=ssl_context,
                debug=True)
        except SSLError:
            print(
                f'ERROR: There is an issue with the SSL cert and key files:\n'
                f'{", ".join([str(x) for x in ssl_context])}\n'
                f'Run setupService.py for assistance regenerating corrupt SSL files.'
            )
            exit(1)


def _check_for_ssl_context():
    '''
    Checks current environment to determine if it the web service should
    run as an HTTP service or use SSL.  We are skipping support for adhoc
    mode due to the extra library dependecy and will advise users how to
    create self-signed keys instead during setup.
    '''
    ssl_context = None # set default result
    if (
        os.path.isfile(defs.SSL_CERT_FILE)
        and os.path.isfile(defs.SSL_KEY_FILE)
    ):
        ssl_context = (defs.SSL_CERT_FILE, defs.SSL_KEY_FILE)
    # Print a warning message about HTTP mode if no SSL context set
    if ssl_context is None:
        print(
            f'WARNING: SSL mode is highly recommended due to network scanning and '
            f'security expectations in working environments. \n'
            f'Please run setupService.py if you need assistance creating SSL keys '
            f'for the {defs.PACKAGE_NAME} package.\n'
            f'Continuing in HTTP mode...'
        )
    return ssl_context
