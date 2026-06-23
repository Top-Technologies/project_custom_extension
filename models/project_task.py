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
    end_date = fields.Date(string='End Date', help='Planned end date for the task')
    target_no = fields.Float(string='Target No', compute='_compute_quantification_totals', store=True, readonly=False, recursive=True)
    actual_no = fields.Float(string='Actual No', compute='_compute_quantification_totals', store=True, readonly=False, recursive=True)
    variation_no = fields.Float(string='Variation', compute='_compute_variation_no', store=True)

    is_delayed = fields.Boolean(string='Is Delayed', compute='_compute_is_delayed', search='_search_is_delayed')
    is_at_risk = fields.Boolean(string='Is At Risk', compute='_compute_is_at_risk', search='_search_is_at_risk')
    has_quantified_subtasks = fields.Boolean(compute='_compute_has_quantified_subtasks', store=True)
    is_project_manager = fields.Boolean(compute='_compute_is_project_manager')

    @api.constrains('state', 'completed_date')
    def _check_completed_date(self):
        for task in self:
            if task.state == '1_done':
                if not task.completed_date:
                    raise ValidationError("Inserting a completion date is mandatory when submitting a task as done.")
                # Optional: Only check project date if the project has an end date set
                if task.project_id and task.project_id.date:
                    if task.completed_date > task.project_id.date:
                        raise ValidationError(
                            "The completed date (%s) cannot be later than the Project end date (%s)." % 
                            (task.completed_date, task.project_id.date)
                        )

    @api.depends_context('uid')
    def _compute_is_project_manager(self):
        is_manager = self.env.user.has_group('project.group_project_manager') or self.env.is_admin()
        for task in self:
            task.is_project_manager = is_manager

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
                # If there are children but none are quantified, we don't automatically reset 
                # because they might have been set manually before quantification was added to children.
            # Else (no children), values remain manual.

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

    def write(self, vals):
        # Check if deadline is being changed
        if 'date_deadline' in vals:
            is_admin_or_manager = self.env.user.has_group('project.group_project_manager') or self.env.is_admin()
            if not is_admin_or_manager:
                new_deadline = fields.Date.to_date(vals['date_deadline']) if vals['date_deadline'] else False
                for task in self:
                    # Only prevent changes if deadline was already set and is being changed
                    if task.date_deadline and task.date_deadline != new_deadline:
                        raise ValidationError("The deadline can only be changed by a Project Manager or Administrator once it has been set.")
        
        return super(Task, self).write(vals)
