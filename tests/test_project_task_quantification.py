from datetime import timedelta
from odoo import fields
from odoo.tests.common import TransactionCase

class TestProjectTaskQuantification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestProjectTaskQuantification, cls).setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'Test Project',
            'billing_type': 'not_billable',
        })

    def test_quantification_computation(self):
        """ Test that variation_no is correctly computed. """
        task = self.env['project.task'].create({
            'name': 'Quantified Task',
            'project_id': self.project.id,
            'quantification_type': 'quantified',
            'target_no': 100.0,
            'actual_no': 30.0,
        })
        self.assertEqual(task.variation_no, 70.0, "Variation should be 70.0 (100 - 30)")

        task.actual_no = 150.0
        self.assertEqual(task.variation_no, -50.0, "Variation should be -50.0 (100 - 150)")

        task.target_no = 200.0
        self.assertEqual(task.variation_no, 50.0, "Variation should be 50.0 (200 - 150)")

    def test_default_quantification_type(self):
        """ Test the default value of quantification_type. """
        task = self.env['project.task'].create({
            'name': 'Normal Task',
            'project_id': self.project.id,
        })
        self.assertEqual(task.quantification_type, 'not_quantified', "Default quantification type should be 'not_quantified'")

    def test_reporting_view_counts(self):
        """ Test that the reporting view correctly calculates status counts. """
        # Create tasks in different states
        self.env['project.task'].create({
            'name': 'Done Task',
            'project_id': self.project.id,
            'state': '1_done',
        })
        self.env['project.task'].create({
            'name': 'Canceled Task',
            'project_id': self.project.id,
            'state': '1_canceled',
        })
        self.env['project.task'].create({
            'name': 'Waiting Task',
            'project_id': self.project.id,
            'state': '04_waiting_normal',
        })
        # Create a delayed task
        self.env['project.task'].create({
            'name': 'Delayed Task',
            'project_id': self.project.id,
            'state': '01_in_progress',
            'date_deadline': fields.Datetime.now() - timedelta(days=1),
        })
        # Create an at risk task
        self.env['project.task'].create({
            'name': 'At Risk Task',
            'project_id': self.project.id,
            'state': '01_in_progress',
            'priority': '1',
        })

        # Force refresh the view
        self.env['report.project.task.user'].init()

        # Check counts for this project
        report = self.env['report.project.task.user'].search([('project_id', '=', self.project.id)])
        
        # Note: report is a view, it returns one record per task per assignee. 
        # Since these tasks have no assigned users, we might need to check if they even appeared in the view or if we need to search specifically.
        # The standard report filters on project_id IS NOT NULL.
        
        # Let's sum up the fields in the report for our project
        completed_count = sum(report.mapped('count_completed'))
        in_progress_count = sum(report.mapped('count_in_progress'))
        on_hold_count = sum(report.mapped('count_on_hold'))
        cancelled_count = sum(report.mapped('count_cancelled'))
        delayed_count = sum(report.mapped('count_delayed'))
        at_risk_count = sum(report.mapped('count_at_risk'))

        # Standard tasks analysis report normally shows one row per user assigned. 
        # If no user is assigned, it shows one row with user_id = False.
        # However, our tasks have project_id, so they should be in the report.

        # Done Task -> count_completed=1
        self.assertGreaterEqual(completed_count, 1)
        # Waiting Task -> count_on_hold=1
        self.assertGreaterEqual(on_hold_count, 1)
        # Canceled Task -> count_cancelled=1
        self.assertGreaterEqual(cancelled_count, 1)
        # Delayed Task -> count_delayed=1
        self.assertGreaterEqual(delayed_count, 1)
        # At Risk Task -> count_at_risk=1
        self.assertGreaterEqual(at_risk_count, 1)

        # Check work analysis fields
        self.env['project.task'].create({
            'name': 'Quant Work Task',
            'project_id': self.project.id,
            'quantification_type': 'quantified',
            'target_no': 50.0,
            'actual_no': 20.0,
        })
        self.env.flush_all()
        self.env['report.project.task.user'].init()
        report = self.env['report.project.task.user'].search([('project_id', '=', self.project.id)])
        
        planned_total = sum(report.mapped('planned_work'))
        actual_total = sum(report.mapped('actual_worked'))
        variation_total = sum(report.mapped('work_variation'))

        self.assertGreaterEqual(planned_total, 50.0)
        self.assertGreaterEqual(actual_total, 20.0)
        self.assertGreaterEqual(variation_total, 30.0)

        # Check quantification counts
        quantified_count = sum(report.mapped('is_quantified'))
        not_quantified_count = sum(report.mapped('is_not_quantified'))
        
        # 'Quant Work Task' is quantified
        self.assertGreaterEqual(quantified_count, 1)
        # Other tasks created in this project are not quantified (unless specified)
        # Done Task, Canceled Task, Waiting Task, Delayed Task, At Risk Task are all default 'not_quantified'
        self.assertGreaterEqual(not_quantified_count, 5)

    def test_subtask_aggregation(self):
        """ Test that parent task totals are aggregated from subtasks. """
        parent_task = self.env['project.task'].create({
            'name': 'Parent Goal',
            'project_id': self.project.id,
            'quantification_type': 'quantified',
        })
        subtask1 = self.env['project.task'].create({
            'name': 'Subtask 1',
            'project_id': self.project.id,
            'parent_id': parent_task.id,
            'quantification_type': 'quantified',
            'target_no': 50.0,
            'actual_no': 20.0,
        })
        parent_task._compute_quantification_totals() # Manually trigger compute if not automatic in test
        self.assertEqual(parent_task.target_no, 50.0)
        self.assertEqual(parent_task.actual_no, 20.0)

        subtask2 = self.env['project.task'].create({
            'name': 'Subtask 2',
            'project_id': self.project.id,
            'parent_id': parent_task.id,
            'quantification_type': 'quantified',
            'target_no': 100.0,
            'actual_no': 30.0,
        })
        parent_task._compute_quantification_totals()
        self.assertEqual(parent_task.target_no, 150.0, "Parent target should be 150 (50 + 100)")
        self.assertEqual(parent_task.actual_no, 50.0, "Parent actual should be 50 (200 + 30)")
        self.assertEqual(parent_task.variation_no, 100.0, "Parent variation should be 100 (150 - 50)")

        # Test changing a subtask
        subtask1.actual_no = 40.0
        parent_task._compute_quantification_totals()
        self.assertEqual(parent_task.actual_no, 70.0, "Parent actual should be 70 (40 + 30)")

    def test_locked_fields(self):
        """ Test that start_date, end_date, and date_deadline cannot be changed by normal users once set. """
        # Create a regular user
        group_user = self.env.ref('base.group_user')
        regular_user = self.env['res.users'].create({
            'name': 'Regular Employee',
            'login': 'reg_emp',
            'email': 'reg_emp@test.com',
            'groups_id': [(6, 0, [group_user.id])],
        })

        # Create task without dates (as admin)
        task = self.env['project.task'].create({
            'name': 'Test Locked Fields Task',
            'project_id': self.project.id,
        })

        # As regular user, we should be able to set the dates initially
        task_as_user = task.with_user(regular_user)
        task_as_user.write({
            'start_date': '2026-07-01',
            'end_date': '2026-07-10',
            'date_deadline': '2026-07-15',
        })
        self.assertEqual(task.start_date, fields.Date.to_date('2026-07-01'))
        self.assertEqual(task.end_date, fields.Date.to_date('2026-07-10'))
        self.assertEqual(task.date_deadline, fields.Date.to_date('2026-07-15'))

        # As regular user, trying to modify any of these fields should raise ValidationError
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            task_as_user.write({'start_date': '2026-07-02'})

        with self.assertRaises(ValidationError):
            task_as_user.write({'end_date': '2026-07-11'})

        with self.assertRaises(ValidationError):
            task_as_user.write({'date_deadline': '2026-07-16'})

        with self.assertRaises(ValidationError):
            task_as_user.write({'start_date': False})

        # As admin, modifying these fields should work fine
        task.write({
            'start_date': '2026-07-05',
            'end_date': '2026-07-12',
            'date_deadline': '2026-07-20',
        })
        self.assertEqual(task.start_date, fields.Date.to_date('2026-07-05'))
        self.assertEqual(task.end_date, fields.Date.to_date('2026-07-12'))
        self.assertEqual(task.date_deadline, fields.Date.to_date('2026-07-20'))

