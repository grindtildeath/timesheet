# Copyright 2018-2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
{
    'name': 'HR Timesheet Rounded',
    'version': '11.0.1.0.0',
    'author': 'Camptocamp',
    'license': 'AGPL-3',
    'category': 'Generic',
    'website': 'http://www.camptocamp.com',
    'depends': [
        'project',
        'hr_expense',
        'hr_timesheet',
        'hr_timesheet_attendance',
        'sale_timesheet',
    ],
    'data': [
        # Views
        'views/account_analytic_line.xml',
        'views/project_project.xml',
        'views/project_task.xml',
    ],
    'installable': True,
}
