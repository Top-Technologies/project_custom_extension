from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, AccessError


from odoo.addons.mail.tests.common import mail_new_test_user

class TestProjectClientAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.normal_user = mail_new_test_user(
            cls.env, name='Standard User', login='standard_user_client_test', email='standard_user_client_test@example.com', groups='base.group_user,project.group_project_user,project.group_project_manager'
        )

        cls.admin_user = mail_new_test_user(
            cls.env, name='Admin User', login='admin_user_client_test', email='admin_user_client_test@example.com', groups='base.group_user,base.group_system'
        )

        # Create Client Project
        cls.client_project = cls.env['project.project'].create({
            'name': 'Test Client Project',
            'x_project_type': 'client',
            'x_project_status': 'new',
            'privacy_visibility': 'employees',
            'user_id': cls.normal_user.id,
        })

        # Create Internal Project
        cls.internal_project = cls.env['project.project'].create({
            'name': 'Test Internal Project',
            'x_project_type': 'internal',
            'x_project_status': 'new',
            'privacy_visibility': 'employees',
            'user_id': cls.normal_user.id,
        })

    def test_client_project_date_locking_for_normal_user(self):
        """ Normal user can set dates initially, but cannot edit them after saving. """
        task = self.env['project.task'].create({
            'name': 'Client Task',
            'project_id': self.client_project.id,
        })

        task_as_user = task.with_user(self.normal_user)

        # 1. Initial write of dates as normal user should succeed
        task_as_user.write({
            'start_date': '2026-09-01',
            'end_date': '2026-09-10',
            'date_deadline': '2026-09-15',
        })
        self.assertEqual(task.start_date, fields.Date.to_date('2026-09-01'))
        self.assertEqual(task.end_date, fields.Date.to_date('2026-09-10'))

        # 2. Subsequent write to locked dates as normal user must raise ValidationError
        with self.assertRaises(ValidationError):
            task_as_user.write({'start_date': '2026-09-02'})

        with self.assertRaises(ValidationError):
            task_as_user.write({'end_date': '2026-09-12'})

        with self.assertRaises(ValidationError):
            task_as_user.write({'date_deadline': '2026-09-20'})

        # 3. Admin user should be able to edit dates at any time
        task_as_admin = task.with_user(self.admin_user)
        task_as_admin.write({
            'start_date': '2026-09-05',
            'end_date': '2026-09-15',
        })
        self.assertEqual(task.start_date, fields.Date.to_date('2026-09-05'))

    def test_internal_project_dates_unrestricted(self):
        """ Dates on Internal projects are not locked for normal users. """
        task = self.env['project.task'].create({
            'name': 'Internal Task',
            'project_id': self.internal_project.id,
            'start_date': '2026-09-01',
        })

        task_as_user = task.with_user(self.normal_user)
        task_as_user.write({'start_date': '2026-09-05'})
        self.assertEqual(task.start_date, fields.Date.to_date('2026-09-05'))

    def test_top_project_status_restriction(self):
        """ Normal user cannot change project status on Client projects, Admin can. """
        proj_as_user = self.client_project.with_user(self.normal_user)
        with self.assertRaises(ValidationError):
            proj_as_user.write({'x_project_status': 'in_progress'})

        proj_as_admin = self.client_project.with_user(self.admin_user)
        proj_as_admin.write({'x_project_status': 'done'})
        self.assertEqual(self.client_project.x_project_status, 'done')
        # Completion date should auto-fill
        self.assertEqual(self.client_project.date, fields.Date.context_today(self.client_project))

    def test_top_task_status_restriction(self):
        """ Normal user cannot change top task status on Client projects, Admin can. """
        top_task = self.env['project.task'].create({
            'name': 'Top Level Task',
            'project_id': self.client_project.id,
            'state': '01_in_progress',
        })

        top_as_user = top_task.with_user(self.normal_user)
        with self.assertRaises(ValidationError):
            top_as_user.write({'state': '1_done'})

        top_as_admin = top_task.with_user(self.admin_user)
        top_as_admin.write({'state': '1_done'})
        self.assertEqual(top_task.state, '1_done')
        self.assertEqual(top_task.completed_date, fields.Date.context_today(top_task))

    def test_subtask_done_allowed_and_autofills_completed_date(self):
        """ Normal user CAN mark a subtask as Done, and line-level completed_date is auto-filled. """
        parent_task = self.env['project.task'].create({
            'name': 'Parent Task',
            'project_id': self.client_project.id,
        })

        subtask = self.env['project.task'].create({
            'name': 'Subtask Line',
            'project_id': self.client_project.id,
            'parent_id': parent_task.id,
            'state': '01_in_progress',
        })

        subtask_as_user = subtask.with_user(self.normal_user)
        # Normal user marks subtask as Done
        subtask_as_user.write({'state': '1_done'})

        self.assertEqual(subtask.state, '1_done')
        self.assertEqual(subtask.completed_date, fields.Date.context_today(subtask))
