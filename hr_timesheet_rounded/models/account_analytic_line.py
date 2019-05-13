# Copyright 2018-2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import api, fields, models
from odoo.tools.float_utils import float_round


class AccountAnalyticLine(models.Model):

    _inherit = 'account.analytic.line'

    unit_amount_rounded = fields.Float(
        string="Quantity rounded",
        default=0.0,
    )

    @api.onchange('unit_amount')
    def _onchange_unit_amount(self):
        self.with_context(force_compute=1)._update_unit_amount_rounded()

    @api.depends(
        'unit_amount',
        # TODO do we want to update a.a.l when project settings change ?
        # We could do it for non confirmed lines.
    )
    def _update_unit_amount_rounded(self):
        force_compute = self.env.context.get('force_compute')
        if self.env.context.get('grid_adjust'):
            # force_compute if the timesheet is change in the grid view
            force_compute = True

        for rec in self:
            # If we don't have project we do nothing
            if not rec.project_id:
                continue
            # If it a Expense line we do nothing
            if rec.product_id and \
                    not rec.product_id.product_tmpl_id.can_be_expensed:
                continue
            if rec.unit_amount_rounded and not force_compute:
                continue
            rec.unit_amount_rounded = self._calc_rounded_amount(
                rec.project_id.timesheet_rounding_granularity,
                rec.project_id.timesheet_rounding_method,
                rec.project_id.timesheet_invoicing_factor,
                rec.unit_amount,
            )

    @staticmethod
    def _calc_rounded_amount(granularity, rounding_method, factor, amount):
        factor = factor / 100.0
        if granularity:
            unit_amount_rounded = float_round(
                amount * factor,
                precision_rounding=granularity,
                rounding_method=rounding_method
            )
        else:
            unit_amount_rounded = amount * factor
        return unit_amount_rounded

    @api.multi
    def _sale_determine_order_line(self):
        return super(
            AccountAnalyticLine, self.with_context(timesheet_rounding=True)
        )._sale_determine_order_line()

    ####################################################
    # ORM Overrides
    ####################################################
    @api.multi
    def write(self, vals):
        res = super().write(vals)

        # Allow manual customisation of the value
        if not vals.get('unit_amount_rounded'):
            self._update_unit_amount_rounded()
            self._sale_determine_order_line()
        return res

    @api.model
    def create(self, vals):
        rec = super().create(vals)

        if not vals.get('unit_amount_rounded'):
            rec.with_context(force_compute=1)._update_unit_amount_rounded()
        return rec

    @api.model
    def read_group(self, domain, fields, groupby, offset=0,
                   limit=None, orderby=False, lazy=False):
        """ Replace the value of unit_amount by unit_amount_rounded.
        Only when the context timesheet_rounding is True
        we change the value of unit_amount in the
        sale_order_line._analytic_compute_delivered_quantity method
        """
        ctx_ts_rounded = self.env.context.get('timesheet_rounding')
        if ctx_ts_rounded:
            # To add the unit_amount_rounded value on read_group
            fields.append('unit_amount_rounded')
        res = super(AccountAnalyticLine, self).read_group(
            domain, fields, groupby, offset=offset,
            limit=limit, orderby=orderby, lazy=lazy
        )
        if ctx_ts_rounded:
            # To set the unit_amount_rounded value insted of unit_amount
            for rec in res:
                rec['unit_amount'] = rec['unit_amount_rounded']
        return res

    def read(self, fields=None, load='_classic_read'):
        """ Replace the value of unit_amount by unit_amount_rounded.
        Only when the context timesheet_rounding is True
        we change the value of unit_amount in the
        account_anaytic_line._sale_determine_order_line method
        """
        ctx_ts_rounded = self.env.context.get('timesheet_rounding')
        fields_local = fields[:] if fields else []
        if ctx_ts_rounded and 'unit_amount' in fields_local:
            if 'unit_amount_rounded' not in fields_local:
                # To add the unit_amount_rounded value on read
                fields_local.append('unit_amount_rounded')
            if 'project_id' not in fields_local:
                fields_local.append('project_id')
            if 'product_id' not in fields_local:
                fields_local.append('product_id')
        res = super(AccountAnalyticLine, self).read(fields_local, load=load)
        if ctx_ts_rounded:
            # To set the unit_amount_rounded value insted of unit_amount
            for rec in res:
                product_model = self.env['product.product']
                is_expense = False
                product_rec = rec.get('product_id')
                if product_rec:
                    product_id = product_rec
                    if load == '_classic_read':
                        # the classic_read return one tuple like : (id, name)
                        product_id = product_rec[0]
                    product = product_model.browse(product_id)
                    is_expense = product.product_tmpl_id.can_be_expensed
                rounded = 'unit_amount_rounded' in rec
                # Check if the product is a not a expenses
                # and corresponding to one project and unit_amount_rounded is
                # present
                if rec['project_id'] and not is_expense and rounded:
                    rec['unit_amount'] = rec['unit_amount_rounded']
        return res
