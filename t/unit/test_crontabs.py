from __future__ import absolute_import, unicode_literals

from unittest import TestCase

from django.core.exceptions import ValidationError

from django_celery_beat import validators


class MinuteTests(TestCase):
    def test_good(self):
        try:
            validators.minute_validator('*')
            validators.minute_validator('0')
            validators.minute_validator('1')
            validators.minute_validator('54')
            validators.minute_validator('59')

            validators.minute_validator('1,2,59')
            validators.minute_validator('43,2')
            validators.minute_validator('5,20,25,43')

            validators.minute_validator('1-4')
            validators.minute_validator('1-29')

            validators.minute_validator('45-59')
            validators.minute_validator('*/4')
            validators.minute_validator('*/43')
            validators.minute_validator('1-2/43')
        except ValidationError as e:
            self.fail(e)

    def test_space(self):
        with self.assertRaises(ValidationError):
            validators.minute_validator('1, 2')

    def test_big_number(self):
        with self.assertRaises(ValidationError):
            validators.minute_validator('60')
        with self.assertRaises(ValidationError):
            validators.minute_validator('420')
        with self.assertRaises(ValidationError):
            validators.minute_validator('100500')

    def test_text(self):
        with self.assertRaises(ValidationError):
            validators.minute_validator('fsd')
        with self.assertRaises(ValidationError):
            validators.minute_validator('.')
        with self.assertRaises(ValidationError):
            validators.minute_validator('432a')

    def test_out_range(self):
        with self.assertRaises(ValidationError):
            validators.minute_validator('0-432')
        with self.assertRaises(ValidationError):
            validators.minute_validator('342-432')
        with self.assertRaises(ValidationError):
            validators.minute_validator('4-60')

    def test_bad_range(self):
        with self.assertRaises(ValidationError):
            validators.minute_validator('10-4')

    def test_bad_slice(self):
        with self.assertRaises(ValidationError):
            validators.minute_validator('*/100')
        with self.assertRaises(ValidationError):
            validators.minute_validator('10/30')
        with self.assertRaises(ValidationError):
            validators.minute_validator('10-20/100')


class HourTests(TestCase):
    def test_good(self):
        try:
            validators.hour_validator('*')
            validators.hour_validator('0')
            validators.hour_validator('1')
            validators.hour_validator('22')
            validators.hour_validator('23')

            validators.hour_validator('1,2,23')
            validators.hour_validator('23,2')
            validators.hour_validator('5,20,21,22')

            validators.hour_validator('1-4')
            validators.hour_validator('1-23')

            validators.hour_validator('*/4')
            validators.hour_validator('*/22')
            validators.hour_validator('1-2/5')
        except ValidationError as e:
            self.fail(e)

    def test_space(self):
        with self.assertRaises(ValidationError):
            validators.hour_validator('1, 2')

    def test_big_number(self):
        with self.assertRaises(ValidationError):
            validators.hour_validator('24')
        with self.assertRaises(ValidationError):
            validators.hour_validator('420')
        with self.assertRaises(ValidationError):
            validators.hour_validator('100500')

    def test_text(self):
        with self.assertRaises(ValidationError):
            validators.hour_validator('fsd')
        with self.assertRaises(ValidationError):
            validators.hour_validator('.')
        with self.assertRaises(ValidationError):
            validators.hour_validator('432a')

    def test_out_range(self):
        with self.assertRaises(ValidationError):
            validators.hour_validator('0-24')
        with self.assertRaises(ValidationError):
            validators.hour_validator('342-432')
        with self.assertRaises(ValidationError):
            validators.hour_validator('4-25')

    def test_bad_range(self):
        with self.assertRaises(ValidationError):
            validators.hour_validator('10-4')

    def test_bad_slice(self):
        with self.assertRaises(ValidationError):
            validators.hour_validator('*/100')
        with self.assertRaises(ValidationError):
            validators.hour_validator('10/30')
        with self.assertRaises(ValidationError):
            validators.hour_validator('10-20/100')


class DayOfMonthTests(TestCase):
    def test_good(self):
        try:
            validators.day_of_month_validator('*')
            validators.day_of_month_validator('1')
            validators.day_of_month_validator('29')
            validators.day_of_month_validator('31')

            validators.day_of_month_validator('1,2,31')
            validators.day_of_month_validator('30,2')
            validators.day_of_month_validator('5,20,25,31')

            validators.day_of_month_validator('1-4')
            validators.day_of_month_validator('1-30')

            validators.day_of_month_validator('*/4')
            validators.day_of_month_validator('*/22')
            validators.day_of_month_validator('1-2/5')
        except ValidationError as e:
            self.fail(e)

    def test_space(self):
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('1, 2')

    def test_zero(self):
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('0')

    def test_big_number(self):
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('32')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('420')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('100500')

    def test_text(self):
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('fsd')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('.')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('432a')

    def test_out_range(self):
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('0-32')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('342-432')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('4-33')

    def test_bad_range(self):
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('10-4')

    def test_bad_slice(self):
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('*/100')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('10/30')
        with self.assertRaises(ValidationError):
            validators.day_of_month_validator('10-20/100')


class MonthTests(TestCase):
    def test_good(self):
        try:
            validators.month_of_year_validator('*')
            validators.month_of_year_validator('1')
            validators.month_of_year_validator('10')
            validators.month_of_year_validator('12')

            validators.month_of_year_validator('1,2,12')
            validators.month_of_year_validator('12,2')
            validators.month_of_year_validator('5,10,11,12')

            validators.month_of_year_validator('1-4')
            validators.month_of_year_validator('1-12')

            validators.month_of_year_validator('*/4')
            validators.month_of_year_validator('*/12')
            validators.month_of_year_validator('1-2/12')
        except ValidationError as e:
            self.fail(e)

    def test_good_month_name(self):
        try:
            validators.month_of_year_validator('jan')
            validators.month_of_year_validator('feb')
            validators.month_of_year_validator('mar')
            validators.month_of_year_validator('apr')
            validators.month_of_year_validator('may')
            validators.month_of_year_validator('jun')
            validators.month_of_year_validator('jul')
            validators.month_of_year_validator('aug')
            validators.month_of_year_validator('sep')
            validators.month_of_year_validator('oct')
            validators.month_of_year_validator('nov')
            validators.month_of_year_validator('dec')
        except ValidationError as e:
            self.fail(e)

    def test_good_month_name_case(self):
        try:
            validators.month_of_year_validator('jan')
            validators.month_of_year_validator('JAN')
            validators.month_of_year_validator('JaN')
        except ValidationError as e:
            self.fail(e)

    def test_space(self):
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('1, 2')

    def test_zero(self):
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('0')

    def test_big_number(self):
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('13')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('420')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('100500')

    def test_text(self):
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('fsd')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('.')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('432a')

    def test_out_range(self):
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('0-13')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('342-432')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('4-14')

    def test_bad_range(self):
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('10-4')

    def test_bad_slice(self):
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('*/13')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('10/30')
        with self.assertRaises(ValidationError):
            validators.month_of_year_validator('10-20/100')


class DayOfWeekTests(TestCase):
    def test_good(self):
        try:
            validators.day_of_week_validator('*')
            validators.day_of_week_validator('1')
            validators.day_of_week_validator('6')
            validators.day_of_week_validator('7')

            validators.day_of_week_validator('1,2,6')
            validators.day_of_week_validator('6,2')
            validators.day_of_week_validator('5,6,4,6')

            validators.day_of_week_validator('1-4')
            validators.day_of_week_validator('1-7')

            validators.day_of_week_validator('*/4')
            validators.day_of_week_validator('*/6')
            validators.day_of_week_validator('2-7/5')
        except ValidationError as e:
            self.fail(e)

    def test_good_month_name(self):
        try:
            validators.day_of_week_validator('sun')
            validators.day_of_week_validator('mon')
            validators.day_of_week_validator('tue')
            validators.day_of_week_validator('wed')
            validators.day_of_week_validator('thu')
            validators.day_of_week_validator('fri')
            validators.day_of_week_validator('sat')
        except ValidationError as e:
            self.fail(e)

    def test_good_month_name_case(self):
        try:
            validators.day_of_week_validator('mon')
            validators.day_of_week_validator('MoN')
            validators.day_of_week_validator('MON')
        except ValidationError as e:
            self.fail(e)

    def test_space(self):
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('1, 2')

    def test_big_number(self):
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('8')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('420')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('100500')

    def test_text(self):
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('fsd')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('.')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('432a')

    def test_out_range(self):
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('0-32')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('342-432')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('4-33')

    def test_bad_range(self):
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('10-4')

    def test_bad_slice(self):
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('*/8')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('10/30')
        with self.assertRaises(ValidationError):
            validators.day_of_week_validator('10-20/100')
