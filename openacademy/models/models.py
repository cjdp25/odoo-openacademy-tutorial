# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, exceptions, fields, models

STATE_DRAFT = 'draft'

STATE_CONFIRMED = 'confirmed'

STATE_DONE = 'done'

STATE_CHOICES = [
    (STATE_DRAFT, 'Draft'),
    (STATE_CONFIRMED, 'Confirmed'),
    (STATE_DONE, 'Done'),
]


class Course(models.Model):
    _name = 'openacademy.course'

    name = fields.Char(string='Title', required=True)
    description = fields.Text()

    responsible_id = fields.Many2one('res.users', ondelete='set null', string='Responsible', index=True)
    session_ids = fields.One2many('openacademy.session', inverse_name='course_id', string='Sessions')

    @api.multi
    def copy(self, default=None):
        default = dict(default or {})

        copied_count = self.search_count(
            [('name', '=like', _(u'Copy of {}%').format(self.name))]
        )

        if not copied_count:
            new_name = _(u'Copy of {}').format(self.name)
        else:
            new_name = _(u'Copy of {} ({})').format(self.name, copied_count)

        default['name'] = new_name
        return super(Course, self).copy(default)

    _sql_constraints = [
        ('name_description_check',
         'CHECK(name != description)',
         'The title of the course should not be same as the description.'),

        ('name_unique',
         'UNIQUE(name)',
         'The course title must be unique.'),
    ]


class Session(models.Model):
    _name = 'openacademy.session'

    name = fields.Char(required=True)
    start_date = fields.Date(default=fields.Date.today)
    duration = fields.Float(digits=(6, 2), help='Duration in days.')
    end_date = fields.Date(string='End date', store=True, compute='_get_end_date', inverse='_set_end_date')
    seats = fields.Integer(string='Number of seats')
    active = fields.Boolean(default=True)
    color = fields.Integer()

    instructor_id = fields.Many2one('res.partner', string='Instructor',
                                    domain=[
                                        '|',
                                        ('instructor', '=', True),
                                        ('category_id.name', 'ilike', 'Teacher')
                                    ])
    course_id = fields.Many2one('openacademy.course', ondelete='cascade', string='Course', required=True)
    attendee_ids = fields.Many2many('res.partner', string='Attendees')

    taken_seats = fields.Float(string='Taken seats', compute='_taken_seats')

    attendees_count = fields.Integer(string='Attendees count', compute='_get_attendees_count', store=True)

    state = fields.Selection(selection=STATE_CHOICES, default=STATE_DRAFT)

    @api.multi
    def action_draft(self):
        self.state = STATE_DRAFT

    @api.multi
    def action_confirm(self):
        self.state = STATE_CONFIRMED

    @api.multi
    def action_done(self):
        self.state = STATE_DONE

    @api.depends('seats', 'attendee_ids')
    def _taken_seats(self):
        for record in self:
            if not record.seats:
                record.taken_seats = 0.0
            else:
                record.taken_seats = 100.0 * len(record.attendee_ids) / record.seats

    @api.onchange('seats', 'attendee_ids')
    def _verify_valid_seats(self):
        if self.seats < 0:
            return {
                'warning': {
                    'title': _('Incorrect "seats" value'),
                    'message': _('The number of available seats may not be negative.')
                }
            }
        if self.seats < len(self.attendee_ids):
            return {
                'warning': {
                    'title': _('Too many attendees'),
                    'message': _('Increase seats or remove attendees.'),
                }
            }

    @api.depends('attendee_ids')
    def _get_attendees_count(self):
        for record in self:
            record.attendees_count = len(record.attendee_ids)

    @api.constrains('instructor_id', 'attendee_ids')
    def _check_instructor_not_in_attendees(self):
        for record in self:
            if record.instructor_id and record.instructor_id in record.attendee_ids:
                raise exceptions.ValidationError(_('Instructor can not be attendee.'))

    @api.depends('start_date', 'duration')
    def _get_end_date(self):
        for record in self:
            if not (record.start_date and record.duration):
                record.end_date = record.start_date
                continue

            # Add duration to start_date; Monday + 5days = Saturday - 1second = Friday
            start = fields.Datetime.from_string(record.start_date)
            duration = timedelta(days=record.duration, seconds=-1)
            record.end_date = start + duration

    def _set_end_date(self):
        for record in self:
            if not (record.start_date and record.end_date):
                continue

            # Compute dates; Friday - Monday = 4days + 1day = 5days
            start_date = fields.Datetime.from_string(record.start_date)
            end_date = fields.Datetime.from_string(record.end_date)
            record.duration = (end_date - start_date).days + 1
