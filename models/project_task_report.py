from odoo import fields, models, tools

class ReportProjectTaskUser(models.Model):
    _inherit = "report.project.task.user"

    count_completed = fields.Integer(string='Completed Tasks', readonly=True)
    count_in_progress = fields.Integer(string='In Progress Tasks', readonly=True)
    count_delayed = fields.Integer(string='Delayed Tasks', readonly=True)
    count_at_risk = fields.Integer(string='At Risk Tasks', readonly=True)
    count_cancelled = fields.Integer(string='Cancelled Tasks', readonly=True)
    count_on_hold = fields.Integer(string='On Hold Tasks', readonly=True)
    is_subtask = fields.Integer(string='Is Subtask', readonly=True)
    planned_work = fields.Float(string='Planned Work', readonly=True)
    actual_worked = fields.Float(string='Actual Worked', readonly=True)
    work_variation = fields.Float(string='Work Variation', readonly=True)
    achievement_rate = fields.Float(string='Achievement Rate', readonly=True, aggregator="avg")
    is_quantified = fields.Integer(string='Quantified Tasks', readonly=True)
    is_not_quantified = fields.Integer(string='Not Quantified Count', readonly=True)

    def _select(self):
        res = super(ReportProjectTaskUser, self)._select()
        res += """,
            CASE WHEN t.state = '1_done' THEN 1 ELSE 0 END as count_completed,
            CASE WHEN t.state = '01_in_progress' THEN 1 ELSE 0 END as count_in_progress,
            CASE WHEN t.state NOT IN ('1_done', '1_canceled') AND t.date_deadline < (now() at time zone 'UTC') THEN 1 ELSE 0 END as count_delayed,
            CASE WHEN t.priority = '1' AND t.state NOT IN ('1_done', '1_canceled') THEN 1 ELSE 0 END as count_at_risk,
            CASE WHEN t.state = '1_canceled' THEN 1 ELSE 0 END as count_cancelled,
            CASE WHEN t.state = '04_waiting_normal' THEN 1 ELSE 0 END as count_on_hold,
            CASE WHEN t.parent_id IS NOT NULL THEN 1 ELSE 0 END as is_subtask,
            CASE WHEN (SELECT 1 FROM project_task child WHERE child.parent_id = t.id LIMIT 1) IS NULL THEN t.target_no ELSE 0 END as planned_work,
            CASE WHEN (SELECT 1 FROM project_task child WHERE child.parent_id = t.id LIMIT 1) IS NULL THEN t.actual_no ELSE 0 END as actual_worked,
            CASE WHEN (SELECT 1 FROM project_task child WHERE child.parent_id = t.id LIMIT 1) IS NULL THEN t.variation_no ELSE 0 END as work_variation,
            CASE WHEN t.target_no > 0 THEN (t.actual_no / t.target_no) * 100 ELSE 0 END as achievement_rate,
            CASE WHEN t.quantification_type = 'quantified' THEN 1 ELSE 0 END as is_quantified,
            CASE WHEN t.quantification_type = 'not_quantified' THEN 1 ELSE 0 END as is_not_quantified
        """
        return res

    def _group_by(self):
        res = super(ReportProjectTaskUser, self)._group_by()
        res += """,
            t.target_no,
            t.actual_no,
            t.variation_no,
            t.quantification_type
        """
        return res
