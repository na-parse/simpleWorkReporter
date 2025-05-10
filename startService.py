#!/usr/bin/python3
from simpleWorkReporter import SimpleWorkReporter

if __name__ == '__main__':
    app = SimpleWorkReporter()
    #app.run()
    print('-- update_config test ---')
    print(app.settings)
    result, message = app.settings.update_config(
        service_port = 10555,
        worker_name = 'Nathan Dawg',
        worker_email = 'na@uknowit03.net',
        manager_email = 'sysop@unit03.net',
        manager_name = 'System Operator',
        smtp = 'smtp.unit03.netnetnet'
    )
    print(f'-- debug --')
    print(result)
    print(message)
    print(app.settings)



'''
            result = self.settings.update_config(
                service_port = request.form.get('servicePort'),
                worker_name = request.form.get('workerName'),
                worker_email = request.form.get('workerEmail'),
                manager_name = request.form.get('managerName'),
                manager_email = request.form.get('managerEmail'),
                smtp = request.form.get('smtpServer')
            )

'''