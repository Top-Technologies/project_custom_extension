from odoo import api, fields, models

class TaskLog(models.Model):
    _name = 'project.task.log'
    _description = 'Task Daily Log'
    _order = 'date desc, id desc'

    task_id = fields.Many2one('project.task', string='Task', required=True, ondelete='cascade')
    project_id = fields.Many2one('project.project', related='task_id.project_id', string='Project', store=True, readonly=True)
    task_user_ids = fields.Many2many('res.users', compute='_compute_task_user_ids', string='Task Assigned Users')

    @api.depends('task_id.user_ids')
    def _compute_task_user_ids(self):
        for log in self:
            log.task_user_ids = log.task_id.user_ids
    user_id = fields.Many2one('res.users', string='Logged By', default=lambda self: self.env.user, required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    description = fields.Text(string='Daily Task Performed', required=True)
