'''Flask web application.'''

from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, TypeVar
from urllib.parse import urlparse

from flask import (
    Flask,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import db
from .defs import APP_NAME, AVAILABLE_THEMES, DEFAULT_THEME
from .formatting import description_html
from .mail import MailSendError, ReportFlagError, render_report_html, send_pending_report
from .settings import WorkerSettings

F = TypeVar('F', bound=Callable)
logger = logging.getLogger(__name__)


def create_app(settings: WorkerSettings | None = None) -> Flask:
    '''Create the Flask application.

    Validates the task database at startup. Raises db.DatabaseError if the
    file exists but is unusable.
    '''
    settings = settings or WorkerSettings()
    db.initialize_database()
    app = Flask(__name__)
    app.secret_key = settings.session_secret
    app.jinja_env.filters['description_html'] = description_html
    # Loaded once and mutated in-memory via settings.update(); out-of-band
    # edits to worker.conf require a restart.
    app.settings = settings  # type: ignore[attr-defined]
    logger.info('flask application created config_path=%s', settings.config_path)

    @app.context_processor
    def inject_globals() -> dict:
        globals_ = {
            'app_name': APP_NAME,
            'theme': session.get('theme', DEFAULT_THEME),
        }
        # Only authenticated pages render settings/unsent_count in the nav.
        # Skip the lookups (and a DB hit) on login and other public routes.
        if _is_authenticated():
            globals_['settings'] = current_settings()
            globals_['unsent_count'] = db.count_unsent()
        return globals_

    @app.get('/login')
    def login_get():
        if _is_authenticated():
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.post('/login')
    def login_post():
        passphrase = request.form.get('passphrase', '')
        if current_settings().verify_passphrase(passphrase):
            session.clear()
            session['authenticated'] = True
            target = request.args.get('next') or url_for('dashboard')
            logger.info('login succeeded remote_addr=%s target=%s', request.remote_addr, target)
            return redirect(_safe_redirect_target(target))
        logger.warning('login failed remote_addr=%s', request.remote_addr)
        flash('Passphrase did not match.', 'error')
        return render_template('login.html'), 401

    @app.post('/logout')
    def logout():
        session.clear()
        logger.info('logout completed remote_addr=%s', request.remote_addr)
        return redirect(url_for('login_get'))

    @app.route('/', methods=['GET', 'POST'])
    @login_required
    def dashboard():
        if request.method == 'POST':
            task_name = request.form.get('task', '').strip()
            description = request.form.get('description', '').strip()
            use_manual_date = request.form.get('manual_date') == 'on'
            work_date = request.form.get('work_date', '')
            if not task_name or not description:
                flash('Task and description are required.', 'error')
            else:
                timestamp = db.date_to_timestamp(work_date) if use_manual_date else None
                task_id = db.add_task(task_name, description, timestamp)
                logger.info(
                    'dashboard task created id=%s manual_date=%s remote_addr=%s',
                    task_id,
                    use_manual_date,
                    request.remote_addr,
                )
                flash('Work entry added.', 'success')
                return redirect(url_for('dashboard'))
        pending_tasks = db.unsent_tasks()
        logger.info(
            'dashboard loaded pending_count=%s remote_addr=%s',
            len(pending_tasks),
            request.remote_addr,
        )
        return render_template('dashboard.html', tasks=pending_tasks)

    @app.get('/tasks')
    @login_required
    def tasks():
        task_list = db.all_tasks()
        logger.info('task history loaded count=%s remote_addr=%s', len(task_list), request.remote_addr)
        return render_template('tasks.html', tasks=task_list)

    @app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_task(task_id: int):
        task = db.get_task(task_id)
        if task is None:
            logger.warning('task edit requested for missing id=%s', task_id)
            flash('Task was not found.', 'error')
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            task_name = request.form.get('task', '').strip()
            description = request.form.get('description', '').strip()
            work_date = request.form.get('work_date', '')
            if not task_name or not description or not work_date:
                flash('Date, task, and description are required.', 'error')
            else:
                db.update_task(
                    task_id,
                    task_name,
                    description,
                    db.date_to_timestamp(work_date),
                )
                logger.info('task edit saved id=%s remote_addr=%s', task_id, request.remote_addr)
                flash('Work entry updated.', 'success')
                return redirect(url_for('dashboard'))
        logger.info('task edit form loaded id=%s remote_addr=%s', task_id, request.remote_addr)
        return render_template('edit.html', task=task)

    @app.route('/tasks/<int:task_id>/delete', methods=['GET', 'POST'])
    @login_required
    def delete_task(task_id: int):
        task = db.get_task(task_id)
        if task is None:
            logger.warning('task delete requested for missing id=%s', task_id)
            flash('Task was not found.', 'error')
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            db.delete_task(task_id)
            logger.info('task delete confirmed id=%s remote_addr=%s', task_id, request.remote_addr)
            flash('Work entry deleted.', 'success')
            return redirect(url_for('dashboard'))
        logger.info('task delete form loaded id=%s remote_addr=%s', task_id, request.remote_addr)
        return render_template('delete.html', task=task)

    @app.route('/send', methods=['GET', 'POST'])
    @login_required
    def send_report():
        tasks = db.unsent_tasks()
        if not tasks:
            logger.info('report send page requested with no pending tasks')
            flash('There are no unsent entries to report.', 'warning')
            return redirect(url_for('dashboard'))
        settings = current_settings()
        if request.method == 'POST':
            try:
                logger.info('web report send requested count=%s', len(tasks))
                count = send_pending_report(settings)
            except MailSendError as exc:
                logger.error('web report send failed error=%s', exc)
                flash(str(exc), 'error')
            except ReportFlagError as exc:
                flash(
                    f'Report sent ({exc.count} entries) but the database flag '
                    f'update failed. Task IDs {exc.task_ids} are still marked '
                    f'unsent — clear via db_tool before sending again to avoid '
                    f'a duplicate email.',
                    'warning',
                )
                return redirect(url_for('dashboard'))
            else:
                logger.info('web report send completed count=%s', count)
                flash(f'Report sent with {count} entries.', 'success')
                return redirect(url_for('dashboard'))
        html = render_report_html(settings, tasks)
        logger.info('report preview rendered count=%s remote_addr=%s', len(tasks), request.remote_addr)
        return render_template('send.html', tasks=tasks, report_html=html)

    @app.route('/config', methods=['GET', 'POST'])
    @login_required
    def configure():
        field_errors: dict[str, str] = {}
        submitted: dict[str, str] | None = None
        settings = current_settings()
        if request.method == 'POST':
            form_data = request.form.to_dict()
            update_kwargs, field_errors = WorkerSettings.validate_form(
                form_data,
                existing_credentials=settings.smtp.credentials is not None,
            )
            if update_kwargs is not None:
                # Strip the password before echoing back on success path
                # (won't render, but defensive).
                settings.update(**update_kwargs)
                logger.info('configuration updated from web remote_addr=%s', request.remote_addr)
                flash('Configuration updated.', 'success')
                return redirect(url_for('configure'))
            # Echo back submitted values minus the password.
            submitted = {k: v for k, v in form_data.items() if k != 'smtp_password'}
            logger.warning(
                'configuration update rejected fields=%s',
                sorted(field_errors.keys()),
            )
        return render_template(
            'config.html',
            settings=settings,
            submitted=submitted,
            field_errors=field_errors,
        )

    @app.route('/theme', methods=['GET', 'POST'])
    @login_required
    def theme():
        if request.method == 'POST':
            selected = request.form.get('theme', DEFAULT_THEME)
            if selected in AVAILABLE_THEMES:
                session['theme'] = selected
                logger.info('theme updated theme=%s remote_addr=%s', selected, request.remote_addr)
                flash('Theme updated.', 'success')
            return redirect(url_for('theme'))
        return render_template('theme.html', themes=AVAILABLE_THEMES)

    return app


def login_required(func: F) -> F:
    '''Require an authenticated local session.'''
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _is_authenticated():
            return redirect(url_for('login_get', next=request.full_path.rstrip('?')))
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def current_settings() -> WorkerSettings:
    '''Return the WorkerSettings singleton bound to the running Flask app.

    Web /config updates mutate this in place via settings.update(); out-of-band
    edits to worker.conf require a service restart to take effect.
    '''
    return current_app.settings  # type: ignore[attr-defined,no-any-return]


def _is_authenticated() -> bool:
    # Session invalidation on passphrase change is handled by rotating the
    # session_secret in worker.conf, which invalidates all existing cookies.
    return session.get('authenticated') is True


def _safe_redirect_target(target: str) -> str:
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return url_for('dashboard')
    if not target.startswith('/'):
        return url_for('dashboard')
    return target
