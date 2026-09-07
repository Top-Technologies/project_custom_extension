from odoo import api, fields, models
from odoo.exceptions import ValidationError

class Task(models.Model):
    _inherit = 'project.task'

    daily_log_ids = fields.One2many('project.task.log', 'task_id', string='Daily Logs')

    quantification_type = fields.Selection([
        ('quantified', 'Quantified'),
        ('not_quantified', 'Not Quantified')
    ], string='Quantification Type', default='not_quantified')
    start_date = fields.Date(string='Start Date')
    completed_date = fields.Date(string='Completed Date')
    end_date = fields.Date(string='Planned End Date', help='Planned end date for the task')
    target_no = fields.Float(string='Target No', compute='_compute_quantification_totals', store=True, readonly=False)
    actual_no = fields.Float(string='Actual No', compute='_compute_quantification_totals', store=True, readonly=False)
    variation_no = fields.Float(string='Variation', compute='_compute_variation_no', store=True)

    is_delayed = fields.Boolean(string='Is Delayed', compute='_compute_is_delayed', search='_search_is_delayed')
    is_at_risk = fields.Boolean(string='Is At Risk', compute='_compute_is_at_risk', search='_search_is_at_risk')
    has_quantified_subtasks = fields.Boolean(compute='_compute_has_quantified_subtasks', store=True)
    is_project_manager = fields.Boolean(compute='_compute_is_project_manager')
    is_admin_user = fields.Boolean(compute='_compute_is_admin_user')
    is_client_project = fields.Boolean(compute='_compute_is_client_project')
    is_start_date_readonly = fields.Boolean(compute='_compute_date_readonly_flags')
    is_end_date_readonly = fields.Boolean(compute='_compute_date_readonly_flags')
    is_deadline_readonly = fields.Boolean(compute='_compute_date_readonly_flags')
    is_top_status_readonly = fields.Boolean(compute='_compute_date_readonly_flags')

    @api.depends_context('uid')
    def _compute_is_admin_user(self):
        is_admin = self.env.user.has_group('base.group_system') or self.env.is_admin()
        for task in self:
            task.is_admin_user = is_admin

    @api.depends('project_id', 'project_id.x_project_type')
    def _compute_is_client_project(self):
        for task in self:
            task.is_client_project = task.project_id and getattr(task.project_id, 'x_project_type', False) == 'client'

    @api.depends_context('uid')
    @api.depends('start_date', 'end_date', 'date_deadline', 'parent_id', 'project_id', 'project_id.x_project_type')
    def _compute_date_readonly_flags(self):
        is_admin = self.env.user.has_group('base.group_system') or self.env.is_admin()
        for task in self:
            is_client = task.project_id and getattr(task.project_id, 'x_project_type', False) == 'client'
            if is_client and not is_admin:
                origin = task._origin
                task.is_start_date_readonly = bool(origin.start_date)
                task.is_end_date_readonly = bool(origin.end_date)
                task.is_deadline_readonly = bool(origin.date_deadline)
                task.is_top_status_readonly = not task.parent_id
            else:
                task.is_start_date_readonly = False
                task.is_end_date_readonly = False
                task.is_deadline_readonly = False
                task.is_top_status_readonly = False

    @api.depends_context('uid')
    def _compute_is_project_manager(self):
        is_manager = self.env.user.has_group('project.group_project_manager') or self.env.is_admin()
        for task in self:
            task.is_project_manager = is_manager

    @api.onchange('state')
    def _onchange_state_auto_completed_date(self):
        if self.state == '1_done' and not self.completed_date:
            self.completed_date = fields.Date.context_today(self)

    @api.depends('child_ids.quantification_type')
    def _compute_has_quantified_subtasks(self):
        for task in self:
            task.has_quantified_subtasks = any(child.quantification_type == 'quantified' for child in task.child_ids)

    @api.depends('child_ids.target_no', 'child_ids.actual_no', 'child_ids.quantification_type')
    def _compute_quantification_totals(self):
        for task in self:
            if task.child_ids:
                quantified_children = task.child_ids.filtered(lambda c: c.quantification_type == 'quantified')
                if quantified_children:
                    task.target_no = sum((c.target_no or 0.0) for c in quantified_children)
                    task.actual_no = sum((c.actual_no or 0.0) for c in quantified_children)

    @api.depends('date_deadline', 'state')
    def _compute_is_delayed(self):
        today = fields.Datetime.now()
        for task in self:
            task.is_delayed = not task.is_closed and task.date_deadline and task.date_deadline < today

    def _search_is_delayed(self, operator, value):
        today = fields.Datetime.now()
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('is_closed', '=', False), ('date_deadline', '<', today)]
        return ['|', ('is_closed', '=', True), ('date_deadline', '>=', today)]

    @api.depends('priority', 'state')
    def _compute_is_at_risk(self):
        for task in self:
            task.is_at_risk = task.priority == '1' and not task.is_closed

    def _search_is_at_risk(self, operator, value):
        from odoo.addons.project.models.project_task import CLOSED_STATES
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('priority', '=', '1'), ('state', 'not in', list(CLOSED_STATES.keys()))]
        return ['|', ('priority', '!=', '1'), ('state', 'in', list(CLOSED_STATES.keys()))]

    @api.depends('target_no', 'actual_no')
    def _compute_variation_no(self):
        for task in self:
            task.variation_no = (task.target_no or 0.0) - (task.actual_no or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state') == '1_done' and 'completed_date' not in vals:
                vals['completed_date'] = fields.Date.context_today(self)
        return super().create(vals_list)

    def write(self, vals):
        is_admin = self.env.user.has_group('base.group_system') or self.env.is_admin()

        # Check date locking & top status restrictions for non-admin users on Client Projects
        for task in self:
            is_client = task.project_id and getattr(task.project_id, 'x_project_type', False) == 'client'
            if is_client and not is_admin:
                origin = task._origin
                # 1. Date Field Locking
                if 'start_date' in vals and origin.start_date:
                    raise ValidationError("Start Date is locked and can only be modified by an Administrator for Client projects.")
                if 'end_date' in vals and origin.end_date:
                    raise ValidationError("End Date is locked and can only be modified by an Administrator for Client projects.")
                if 'date_deadline' in vals and origin.date_deadline:
                    raise ValidationError("Deadline is locked and can only be modified by an Administrator for Client projects.")

                # 2. Top Status Restriction
                if not task.parent_id and ('state' in vals or 'stage_id' in vals):
                    raise ValidationError("The status of top-level tasks on Client projects can only be modified by an Administrator.")

        # 3. Auto-fill completion date when state changes to done
        if vals.get('state') == '1_done' and 'completed_date' not in vals:
            vals['completed_date'] = fields.Date.context_today(self)
        elif 'stage_id' in vals and 'completed_date' not in vals:
            stage = self.env['project.task.type'].browse(vals['stage_id'])
            if stage.name == 'Done' or stage.fold:
                vals['completed_date'] = fields.Date.context_today(self)

        return super(Task, self).write(vals)


