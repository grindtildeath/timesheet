# Copyright 2018-2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields
from odoo.tests.common import SavepointCase


class TestRounded(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.aal_model = cls.env['account.analytic.line']
        cls.sale_order_model = cls.env['sale.order']
        cls.aaa_model = cls.env['account.analytic.account']
        cls.sale_order_line_model = cls.env['sale.order.line']
        cls.project_task_model = cls.env['project.task']
        cls.project_project_model = cls.env['project.project']

        cls.today = fields.Date.today()

        invoicing_factor = 200

        cls.analytic_account = cls.aaa_model.create({'name': 'Analytic aa'})

        cls.project = cls.project_project_model.with_context(
            jira_no_default_binding=True
        ).create({
            'name': "Project Test",
            'timesheet_rounding_granularity': 0.25,
            'timesheet_rounding_method': 'UP',
            'timesheet_invoicing_factor': invoicing_factor,
        })

        cls.product = cls.env['product.product'].create({
            'name': "Service delivered, create task in global project",
            'standard_price': 30,
            'list_price': 90,
            'type': 'service',
            'invoice_policy': 'delivery',
            'uom_id': cls.env.ref('uom.product_uom_hour').id,
            'uom_po_id': cls.env.ref('uom.product_uom_hour').id,
            'default_code': 'SERV-DELI2',
            'service_type': 'timesheet',
            'service_tracking': 'task_global_project',
            'project_id': cls.project.id,
            'taxes_id': False,
        })

        cls.product_expense = cls.env['product.product'].create({
            'name': "Service delivered, EXPENSE",
            'can_be_expensed': True,
            'standard_price': 30,
            'list_price': 90,
            'type': 'service',
            'invoice_policy': 'order',
            'uom_id': cls.env.ref('uom.product_uom_hour').id,
            'uom_po_id': cls.env.ref('uom.product_uom_hour').id,
        })

        cls.sale_order = cls.sale_order_model.create({
            'partner_id': cls.env.ref('base.main_partner').id,
            'picking_policy': 'direct',
            'pricelist_id': cls.env.ref('product.list0').id,
            'analytic_account_id': cls.project.analytic_account_id.id,
        })

        product_line = {
            'name': cls.product.name,
            'order_id': cls.sale_order.id,
            'product_id': cls.product.id,
            'product_uom_qty': 3,
            'product_uom': cls.product.uom_id.id,
            'price_unit': cls.product.list_price
        }

        cls.order_line = cls.sale_order_line_model.create(product_line)
        # action_confirm create the project for us
        cls.sale_order.with_context(connector_no_export=True).action_confirm()

        cls.task = cls.project_task_model.search([
            ('sale_line_id', '=', cls.order_line.id)
        ])

    def create_analytic_line(self, **kw):
        values = {
            'project_id': self.project.id,
            'date': self.today,
            'unit_amount': 0,
            'unit_amount_rounded': 0,
            'task_id': self.task.id,
        }
        values.update(kw)
        line = self.aal_model.create(values)
        return line

    def test_analytic_line_create(self):
        line = self.create_analytic_line(unit_amount=1)
        self.assertEqual(line.unit_amount_rounded, 2.0)

    def test_analytic_line_create_and_update_amount_rounded(self):
        line = self.create_analytic_line(unit_amount=2)
        self.assertEqual(line.unit_amount_rounded, 4.0)
        line.unit_amount_rounded = 5.0
        self.assertEqual(line.unit_amount_rounded, 5.0)

    def test_analytic_line_create_and_update_amount(self):
        line = self.create_analytic_line(unit_amount=2)
        self.assertEqual(line.unit_amount_rounded, 4.0)
        line.unit_amount = 5.0
        line._onchange_unit_amount()
        self.assertEqual(line.unit_amount_rounded, 10.0)

    def test_analytic_line_read_group(self):
        """Test of the read group with an without timesheet_rounding context
        - without context the unit_amount should be the inital
        - with the context the value of unit_amount should be replace by the
          unit_amount_rounded
        """
        line = self.create_analytic_line(unit_amount=1)
        domain = [('project_id', '=', self.project.id)]
        fields = ['so_line', 'unit_amount', 'product_uom_id']
        groupby = ['product_uom_id', 'so_line']

        data_ctx_f = line.with_context(timesheet_rounding=False).read_group(
            domain, fields, groupby,
            offset=0, limit=None, orderby=False, lazy=False
        )
        self.assertEqual(data_ctx_f[0]['unit_amount'], 1.0)

        data_ctx_t = line.with_context(timesheet_rounding=True).read_group(
            domain, fields, groupby,
            offset=0, limit=None, orderby=False, lazy=False
        )
        self.assertEqual(data_ctx_t[0]['unit_amount'], 2.0)

    def test_sale_order_qty_1(self):
        """ Test on the SO qty : Ordered, Delivered, invoice and to Invoiced
        amount=1
        should be rounded to 2 by the invoicing_factor
        """
        self.create_analytic_line(unit_amount=1)
        self.assertAlmostEqual(self.sale_order.order_line.qty_delivered, 2.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_to_invoice, 2.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_invoiced, 0)

    def test_sale_order_qty_2(self):
        """ Test on the SO qty : Ordered, Delivered, invoice and to Invoiced
        amount=1 and amount_rounded=4
        """
        self.create_analytic_line(unit_amount=1, unit_amount_rounded=4)

        self.assertAlmostEqual(self.sale_order.order_line.qty_delivered, 4.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_to_invoice, 4.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_invoiced, 0)

    def test_sale_order_qty_3(self):
        """ Test on the SO qty : Ordered, Delivered, invoice and to Invoiced
        amount=0.9
        should be rounded to 2 by the invoicing_factor with the project
        timesheet variable :
        'timesheet_rounding_granularity': 0.25,
        'timesheet_rounding_method': 'UP',
        'timesheet_invoicing_factor': 200
        """
        self.create_analytic_line(unit_amount=0.9)
        self.assertAlmostEqual(self.sale_order.order_line.qty_delivered, 2.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_to_invoice, 2.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_invoiced, 0)

    def test_sale_order_qty_4(self):
        """ Test on the SO qty : Ordered, Delivered, invoice and to Invoiced
        amount=0.9
        should be rounded to 2 by the invoicing_factor with the project
        timesheet variable :
        'timesheet_rounding_granularity': 0.25,
        'timesheet_rounding_method': 'UP',
        'timesheet_invoicing_factor': 400
        """
        self.project.timesheet_invoicing_factor = 400
        self.create_analytic_line(unit_amount=1.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_delivered, 4.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_to_invoice, 4.0)
        self.assertAlmostEqual(self.sale_order.order_line.qty_invoiced, 0)

    def test_calc_rounded_amount_method(self):
        """ Test on the SO qty : Ordered, Delivered, invoice and to Invoiced.
        """
        aal = self.aal_model

        granularity = 0.25
        rounding_method = 'UP'
        factor = 200
        amount = 1
        self.assertEqual(
            aal._calc_rounded_amount(
                granularity, rounding_method, factor, amount
            ), 2)

        granularity = 0.0
        rounding_method = 'UP'
        factor = 200
        amount = 1
        self.assertEqual(
            aal._calc_rounded_amount(
                granularity, rounding_method, factor, amount
            ), 2
        )

        granularity = 0.25
        rounding_method = 'UP'
        factor = 100
        amount = 1.0
        self.assertEqual(
            aal._calc_rounded_amount(
                granularity, rounding_method, factor, amount
            ), 1
        )

        granularity = 0.25
        rounding_method = 'UP'
        factor = 200
        amount = 0.9
        self.assertEqual(
            aal._calc_rounded_amount(
                granularity, rounding_method, factor, amount
            ), 2
        )

        granularity = 1.0
        rounding_method = 'UP'
        factor = 200
        amount = 0.6
        self.assertEqual(
            aal._calc_rounded_amount(
                granularity, rounding_method, factor, amount
            ), 2
        )

        granularity = 0.25
        rounding_method = 'HALF_UP'
        factor = 200
        amount = 1.01
        self.assertEqual(
            aal._calc_rounded_amount(
                granularity, rounding_method, factor, amount
            ), 2
        )

    def test_read(self):
        """ Test read groupe override in account_anaytic_line
        if line:
            contain any project -> nothing to override
            the product is a expense -> nothing to override
            the context is not timesheet_rounding -> nothing to override
        else:
            Check the unit_amount should be the rounded one
        """
        load = '_classic_read'
        fields = None

        # context = False + project_id - product_expense
        line = self.create_analytic_line(unit_amount=1)
        unit_amount_ret = line.read(fields, load)[0]['unit_amount']
        self.assertEqual(unit_amount_ret, 1)

        # context = True - project - product_expense
        line = self.create_analytic_line(
            unit_amount=1,
            project_id=False,
            account_id=self.analytic_account.id
        )
        unit_amount_ret = line.with_context(
            timesheet_rounding=True
        ).read(fields, load)[0]['unit_amount']
        self.assertEqual(unit_amount_ret, 1)

        # context = True + project_id + product_expense
        line = self.create_analytic_line(
            unit_amount=1,
            product_id=self.product_expense.id
        )
        unit_amount_ret = line.with_context(
            timesheet_rounding=True
        ).read(fields, load)[0]['unit_amount']
        self.assertEqual(unit_amount_ret, 1)

        # context = True + project_id - product_expense
        line = self.create_analytic_line(unit_amount=1)
        unit_amount_ret = line.with_context(
            timesheet_rounding=True
        ).read(fields, load)[0]['unit_amount']
        self.assertEqual(unit_amount_ret, 2)
